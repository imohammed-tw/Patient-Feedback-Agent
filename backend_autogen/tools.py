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

            # Format the result string
            result = "Top issues our team is actively working on:\n"
            for i, (issue, count) in enumerate(top_issues, 1):
                result += f"{i}. {issue} ({count} mentions)\n"

            return result.strip()  # Remove any trailing whitespace

        except Exception as e:
            return f"Error retrieving common issues from database: {str(e)}"


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
