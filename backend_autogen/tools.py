from textblob import TextBlob
from database import (
    feedback_collection,
)  # Assuming 'database' module handles MongoDB connection
from collections import Counter
import time
import asyncio
from typing import Union
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


def quick_sentiment_check(feedback_text: str) -> str:
    """
    Determines sentiment from feedback using TextBlob.
    Returns a concise string indicating sentiment and polarity.
    The agent will interpret this into an empathetic response.

    Args:
        feedback_text (str): The feedback text to analyze

    Returns:
        str: Sentiment analysis result with polarity score
    """
    with tracer.start_as_current_span("Tool.quick_sentiment_check"):
        if not feedback_text:
            return "Sentiment: Neutral (no feedback provided), Polarity: 0.00"

        blob = TextBlob(feedback_text)
        polarity = blob.sentiment.polarity

        if polarity > 0.2:
            sentiment = "Positive"
        elif polarity < -0.2:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        return f"Sentiment: {sentiment}, Polarity: {polarity:.2f}"


def start_feedback_rating_prompt(patient_name: str = "there") -> str:
    """
    Initiates interactive feedback collection by requesting satisfaction rating.

    Args:
        patient_name (str): Name of the patient (defaults to "there")

    Returns:
        str: Standardized rating request prompt
    """
    with tracer.start_as_current_span("Tool.start_feedback_rating_prompt"):
        return (
            f"Alright {patient_name}, I'd like to collect your feedback. "
            "On a scale from 1 to 5, how would you rate your experience?"
        )


def ask_for_feedback_comments(rating: Union[int, str]) -> str:
    """
    Generates a context-appropriate prompt for detailed comments based on the satisfaction rating.
    The agent will directly convey this prompt to the user.

    Args:
        rating (Union[int, str]): Satisfaction rating from 1-5

    Returns:
        str: Context-appropriate prompt for detailed feedback
    """
    with tracer.start_as_current_span("Tool.ask_for_feedback_comments"):
        try:
            rating = int(rating)
            if rating >= 4:
                return "Thank you for that rating! Could you share some specific details about what went well during your experience? This helps us understand what we're doing right and continue to provide excellent care."
            elif rating == 3:
                return "Thank you for your rating. It sounds like your experience was okay but perhaps there's room for improvement. Could you tell me more about what happened and what we could do better?"
            else:  # rating <= 2
                return "I'm truly sorry to hear your experience was not satisfactory. Your feedback is important. Could you please share more details about what went wrong? This will help us address these issues directly."
        except (ValueError, TypeError):
            # Handle cases where the rating is not a valid integer
            return "Please provide a valid numeric rating (1-5). Could you tell me more about your experience?"


def categorize_feedback(comments: str) -> str:
    """
    Classifies feedback into categories based on keywords.
    Returns the identified category name as a string.
    The agent will use this category for saving feedback.

    Args:
        comments (str): Feedback comments to categorize

    Returns:
        str: Category classification result
    """
    with tracer.start_as_current_span("Tool.categorize_feedback"):
        if not comments:
            return "Other"  # Default category if no comments provided

        categories = {
            "Billing": [
                "bill",
                "invoice",
                "payment",
                "charge",
                "cost",
                "expensive",
                "insurance",
                "price",
                "refund",
            ],
            "Staff": [
                "nurse",
                "doctor",
                "receptionist",
                "staff",
                "rude",
                "friendly",
                "helpful",
                "attitude",
                "behavior",
            ],
            "Wait Time": [
                "wait",
                "delay",
                "hours",
                "slow",
                "time",
                "appointment",
                "queue",
                "schedule",
            ],
            "Facilities": [
                "clean",
                "dirty",
                "bathroom",
                "room",
                "parking",
                "facility",
                "equipment",
                "noise",
            ],
            "Treatment": [
                "medicine",
                "procedure",
                "treatment",
                "diagnosis",
                "prescription",
                "care",
                "pain",
                "surgery",
            ],
            "Communication": [
                "explain",
                "told",
                "information",
                "informed",
                "understand",
                "clarity",
                "confused",
            ],
            "Other": [],  # Catch-all for comments not fitting other categories
        }

        feedback_lower = comments.lower()
        match_counts = {}

        # Count keyword matches for each category
        for category, keywords in categories.items():
            count = sum(1 for keyword in keywords if keyword in feedback_lower)
            match_counts[category] = count

        # Determine the best category based on the highest match count
        if not any(match_counts.values()):
            return "Other"

        best_category = max(match_counts.items(), key=lambda x: x[1])[0]
        return best_category if match_counts[best_category] > 0 else "Other"


def find_common_issues() -> str:
    """
    Retrieves and summarizes top recurring issues from all feedback comments in the database.
    Returns a formatted string listing common issues or a message if no feedback is found.

    Returns:
        str: Summary of common issues or no data message
    """
    with tracer.start_as_current_span("Tool.find_common_issues"):
        try:
            all_feedback = list(
                feedback_collection.find({})
            )  # Fetch all feedback documents

            if not all_feedback:
                return "No feedback records found yet in the database."

            # Concatenate all comments into a single lowercased string for keyword matching
            all_comments = " ".join(f.get("comments", "") for f in all_feedback).lower()

            # Define keywords and their corresponding common issue descriptions
            issue_keywords = {
                "wait": "Long waiting times",
                "delay": "Long waiting times",
                "billing": "Billing and insurance issues",
                "bill": "Billing and insurance issues",
                "rude": "Staff communication concerns",
                "attitude": "Staff communication concerns",
                "dirty": "Facility cleanliness issues",
                "clean": "Facility cleanliness issues",
                "parking": "Parking difficulties",
                "confusion": "Communication clarity issues",
                "explain": "Communication clarity issues",
                "medication": "Medication issues",
                "prescription": "Medication issues",
                "diagnosis": "Diagnosis accuracy",
                "appointment": "Appointment scheduling",
                "schedule": "Appointment scheduling",
            }

            issue_counts = {}
            # Count occurrences of each keyword to tally issues
            for keyword, description in issue_keywords.items():
                count = all_comments.count(keyword)
                if count > 0:
                    issue_counts[description] = issue_counts.get(description, 0) + count

            if not issue_counts:
                return (
                    "No common issues identified from current feedback in the database."
                )

            # Sort issues by count in descending order and get the top 3
            top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]

            # Format the result with better markdown formatting
            result = (
                "**📝 Here are the top issues our team is actively working on:**\n\n"
            )
            for i, (issue, count) in enumerate(top_issues, 1):
                result += f"{i}. **{issue}**\n"

            result += "\n_We appreciate your feedback as it helps us prioritize these improvements._"
            return result.strip()

        except Exception as e:
            return f"Error retrieving common issues from database: {str(e)}"


def detect_critical_issues(comments: str) -> str:
    """
    Analyzes feedback comments for critical keywords that indicate urgent issues requiring immediate attention.
    Returns a formatted alert if critical issues are detected, or empty string if none found.

    Args:
        comments (str): Feedback comments to analyze for critical issues

    Returns:
        str: Critical issue alert with icon and description, or empty string
    """
    with tracer.start_as_current_span("Tool.detect_critical_issues"):
        if not comments:
            return ""

        # Critical keywords with their descriptions
        critical_keywords = {
            "emergency": "Emergency response concerns",
            "died": "Potential mortality incident",
            "death": "Potential mortality incident",
            "mistake": "Potential medical error",
            "error": "Potential medical error",
            "wrong medication": "Medication error",
            "wrong medicine": "Medication error",
            "allergic reaction": "Adverse reaction",
            "fall": "Patient safety incident",
            "fell": "Patient safety incident",
            "infection": "Infection control issue",
            "contamination": "Infection control issue",
            "unsanitary": "Infection control issue",
            "neglect": "Patient neglect concern",
            "ignored": "Patient neglect concern",
            "lawsuit": "Legal concern raised",
            "sue": "Legal concern raised",
            "legal": "Legal concern raised",
            "blood": "Blood urgency or lack of Blood",
            "urgent": "Immediate action or medication",
            "unresponsive": "Unresponsive patient care or staff negligence",
            "bleeding": "Excessive or unmanaged bleeding reported",
            "overdose": "Medication overdose incident",
            "unattended": "Patient left unattended for a long period",
            "contagious": "Possible contagious condition not isolated",
            "fracture": "Injury/fracture due to negligence",
            "icu delay": "Delay in moving critical patient to ICU",
            "misdiagnosed": "Potential misdiagnosis incident",
            "collapsed": "Physical collapse or serious deterioration",
            "oxygen problem": "Oxygen supply issue",
        }

        comments_lower = comments.lower()
        detected_issues = []

        # Check for critical keywords
        for keyword, description in critical_keywords.items():
            if keyword in comments_lower:
                detected_issues.append(description)

        if detected_issues:
            # Remove duplicates and format the alert
            unique_issues = list(set(detected_issues))

            # Create formatted critical alert with icon
            alert = "🚨 **CRITICAL** 🚨\n\n"
            # alert += "⚠️ _This feedback contains indicators of urgent issues that require immediate attention:_\n\n"

            for issue in unique_issues[:3]:  # Show max 3 critical issues
                alert += f"• **{issue}**\n"

            alert += "\n🔔 _Your feedback has been flagged for priority review by our healthcare team._"
            return alert

        return ""  # No critical issues detected


def save_feedback_to_database(
    name: str, nhs_number: str, rating: Union[int, str], comments: str, category: str
) -> str:
    """
    Saves feedback details to a MongoDB collection.
    Returns a success message with the inserted ID or a specific error message.

    Args:
        name (str): Patient's name
        nhs_number (str): Patient's NHS number
        rating (Union[int, str]): Satisfaction rating (1-5)
        comments (str): Detailed feedback comments
        category (str): Categorized feedback type

    Returns:
        str: Success message with ID or error message
    """
    with tracer.start_as_current_span("Tool.save_feedback_to_database"):

        # Validate that all essential fields are provided before attempting to save
        if not all([name, nhs_number, comments, category is not None]):
            missing_fields = []
            if not name:
                missing_fields.append("name")
            if not nhs_number:
                missing_fields.append("nhs_number")
            if not comments:
                missing_fields.append("comments")
            if category is None:
                missing_fields.append("category")
            return f"Error: Missing required fields for saving feedback: {', '.join(missing_fields)}. Feedback not saved."

        try:
            # Convert rating to integer if it's a string
            rating_int = int(rating) if isinstance(rating, str) else rating

            feedback_doc = {
                "patient_name": name,
                "nhs_number": nhs_number,
                "satisfaction_rating": rating_int,
                "comments": comments,
                "category": category,
                "timestamp": time.time(),  # Record the timestamp when feedback was saved
            }

            result = feedback_collection.insert_one(feedback_doc)

            if result.inserted_id:
                # Return a simple, parseable success message for the agent
                return f"Feedback saved successfully. ID: {str(result.inserted_id)}"
            else:
                return "Error: Failed to save feedback to database."

        except (ValueError, TypeError) as e:
            return (
                f"Error: Invalid rating format. Rating must be a number 1-5. {str(e)}"
            )
        except Exception as e:
            # Catch any exceptions during database operation and return an informative error message
            return f"Error saving feedback to database: {str(e)}"


def save_feedback_and_show_insights(
    name: str, nhs_number: str, rating: Union[int, str], comments: str, category: str
) -> str:
    """
    Combined function that saves feedback to database AND shows common issues in one response.
    This provides a better user experience with a single, comprehensive response.

    Args:
        name (str): Patient's name
        nhs_number (str): Patient's NHS number
        rating (Union[int, str]): Satisfaction rating (1-5)
        comments (str): Detailed feedback comments
        category (str): Categorized feedback type

    Returns:
        str: Combined response with save confirmation and common issues
    """
    with tracer.start_as_current_span("Tool.save_feedback_and_show_insights"):

        # First, save the feedback
        save_result = save_feedback_to_database(
            name, nhs_number, rating, comments, category
        )

        # Check if save was successful
        if "successfully" not in save_result.lower():
            # If save failed, return the error
            return save_result

        # If save was successful, get common issues
        common_issues = find_common_issues()

        # Create combined response
        combined_response = f"Thank you, {name}! Your feedback has been successfully saved and will help us improve our healthcare services.\n\n"

        # Add common issues section
        if (
            "No feedback records" not in common_issues
            and "No common issues" not in common_issues
        ):
            combined_response += f"{common_issues}\n\n"
            combined_response += "Your feedback is valuable in helping us address these priority areas and enhance patient care."
        else:
            combined_response += "Your feedback is the first in our system and will help us start tracking improvement areas."

        return combined_response


def generate_trend_analysis() -> str:
    """
    Generates a summary report of feedback trends.
    Can be used by admin or scheduler to understand overall feedback quality.

    Returns:
        str: Comprehensive trend analysis report
    """
    with tracer.start_as_current_span("Tool.generate_trend_analysis"):
        try:
            feedback_docs = list(feedback_collection.find())
            if not feedback_docs:
                return "No feedback records found yet."

            ratings = [
                f["satisfaction_rating"]
                for f in feedback_docs
                if "satisfaction_rating" in f
            ]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            rating_distribution = {i: ratings.count(i) for i in range(1, 6)}

            categories = [f.get("category", "Unknown") for f in feedback_docs]
            category_counts = {}
            for cat in categories:
                category_counts[cat] = category_counts.get(cat, 0) + 1

            top_category = (
                max(category_counts.items(), key=lambda x: x[1])[0]
                if category_counts
                else "None"
            )

            report = (
                f"📊 **Feedback Trend Summary:**\n"
                f"• Total feedback received: {len(ratings)}\n"
                f"• Average satisfaction rating: {avg_rating:.2f}/5\n"
                f"• Most discussed category: {top_category}\n"
                f"• Rating distribution:\n"
            )
            for rating, count in sorted(rating_distribution.items()):
                report += f"   - {rating}: {count}\n"

            return report

        except Exception as e:
            return f"Error generating trend analysis: {str(e)}"


def save_feedback_and_show_insights(
    name: str, nhs_number: str, rating: Union[int, str], comments: str, category: str
) -> str:
    """
    Combined function that saves feedback to database AND shows common issues in one response.
    This provides a better user experience with a single, comprehensive response.

    Args:
        name (str): Patient's name
        nhs_number (str): Patient's NHS number
        rating (Union[int, str]): Satisfaction rating (1-5)
        comments (str): Detailed feedback comments
        category (str): Categorized feedback type

    Returns:
        str: Combined response with save confirmation and common issues
    """
    with tracer.start_as_current_span("Tool.save_feedback_and_show_insights"):

        # First, save the feedback
        save_result = save_feedback_to_database(
            name, nhs_number, rating, comments, category
        )

        # Check if save was successful
        if "successfully" not in save_result.lower():
            # If save failed, return the error
            return save_result

        # If save was successful, get common issues
        common_issues = find_common_issues()

        # Create combined response
        combined_response = f"Thank you, {name}! Your feedback has been successfully saved and will help us improve our healthcare services.\n\n"

        # Add common issues section
        if (
            "No feedback records" not in common_issues
            and "No common issues" not in common_issues
        ):
            combined_response += f"{common_issues}\n\n"
            combined_response += "Your feedback is valuable in helping us address these priority areas and enhance patient care."
        else:
            combined_response += "Your feedback is the first in our system and will help us start tracking improvement areas."

        return combined_response


# Async wrapper functions (if needed for future async database operations)
async def async_save_feedback_to_database(
    name: str, nhs_number: str, rating: Union[int, str], comments: str, category: str
) -> str:
    """
    Async wrapper for save_feedback_to_database.
    Currently just calls the sync version, but ready for async database operations.
    """
    return save_feedback_to_database(name, nhs_number, rating, comments, category)


async def async_find_common_issues() -> str:
    """
    Async wrapper for find_common_issues.
    Currently just calls the sync version, but ready for async database operations.
    """
    return find_common_issues()
