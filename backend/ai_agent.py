from pydantic_ai import Agent, RunContext
from openai import OpenAI
from collections import Counter
import time
import logging
import logfire
from textblob import TextBlob
from dotenv import load_dotenv
import os
from database import users_collection, feedback_collection


load_dotenv()

# Configure Logfire
logfire.configure()

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(logfire.LogfireLoggingHandler())

# Configure Uvicorn logger(to logfire)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.INFO)
uvicorn_logger.handlers = [logfire.LogfireLoggingHandler()]


# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Define AI Agent
feedback_agent = Agent(
    model="openai:gpt-4o-mini",
    system_prompt="""
You are a healthcare feedback assistant responsible for collecting and analyzing patient experiences using a tool-based workflow. You must guide the user through the full loop from greeting → rating → comment → save → close.

Always follow the steps in strict order and use the appropriate tool at each step. Do not skip or reorder steps.

Conversation Flow:

1. Greet the user and ask about their recent experience.
2. When the user shares initial feedback, immediately run `quick_sentiment_check` on it.
3. If feedback is vague/short ( unclear), use `ask_follow_up_question`.
4. Based on sentiment:
    - If Positive: Thank the user and end the conversation.
    - If Negative: Express empathy, then ask for satisfaction rating (1–5).
5. When the user replies with a number between 1–5 after being asked for rating, store it as `satisfaction_rating`.Now,
    - If rating ≥ 3: Acknowledge and ask for details(comments) which made them to rate that number.
    - If rating ≤ 2: Express concern, and gently ask for more details(comments).
6. After rating, run `ask_for_feedback_comments` to gather structured comments.
7. Run `categorize_feedback` on the comments.
8. Run `save_feedback_to_database` using name, NHS number, rating, category, and comments.
9. Use `find_common_issues` to show 2–3 issues and close by thanking the user by name.
10. After feedback collection is complete (feedback_saved = True), use `handle_general_response` for any follow-up messages.

Tool usage is mandatory. Do not respond manually if a tool exists for the action. Be concise, empathetic, and structured.

Variables to track:
- `satisfaction_rating` (from user)
- `comments` (from user)
- `category` (from tool)
- `feedback_saved` (True when feedback has been saved)
- `conversation_complete` (True when the entire feedback flow is finished)



""",
)


# 1. sentiment analysis
@feedback_agent.tool
def quick_sentiment_check(ctx: RunContext, feedback_text: str) -> str:
    """Determines sentiment for feedback using TextBlob."""
    try:
        state = ctx.deps.get("state", {})
        blob = TextBlob(feedback_text)
        polarity = blob.sentiment.polarity
        sentiment = (
            "Positive"
            if polarity > 0.2
            else "Negative" if polarity < -0.2 else "Neutral"
        )
        state["sentiment"] = sentiment
        return sentiment
    except Exception as e:
        uvicorn_logger.error(
            "Error in quick sentiment analysis", extra={"error": str(e)}
        )
        return "error"


# 2. follow up questions
@feedback_agent.tool
def ask_follow_up_question(ctx: RunContext, feedback_text: str) -> str:
    """Generates a clarifying question to get more detailed feedback."""
    uvicorn_logger.info(" Generating follow-up question...")
    name = ctx.deps.get("name", "the patient")
    try:
        response = client.chat.completions.create(
            model="openai:gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You're a helpful assistant trying to get more context from short or vague feedback from a patient named {name}.",
                },
                {
                    "role": "user",
                    "content": f"The feedback was: '{feedback_text}'. What follow-up question would you ask to understand it better?",
                },
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        uvicorn_logger.error(
            "Error generating follow-up question", extra={"error": str(e)}
        )
        return "error"


# 3.start taking feedback
@feedback_agent.tool
def start_feedback_form_interaction(ctx: RunContext) -> str:
    """Initiates interactive feedback collection (satisfaction rating)."""
    state = ctx.deps.get("state", {})
    name = ctx.deps.get("name", "there")

    # Check if feedback flow is already complete
    if state.get("conversation_complete"):
        return f"Thanks {name}, I've already collected your feedback. Is there anything else I can help you with?"

    # Prevent asking again if already rated
    if state.get("satisfaction_rating"):
        return f"Thanks {name}, I’ve already noted your rating of {state['satisfaction_rating']}."

    state["awaiting_rating"] = True
    return (
        f"Alright {name}, I’d like to collect your feedback. "
        "On a scale from 1 to 5, how would you rate your experience?"
    )


# 4.start taking feedback (part2)
@feedback_agent.tool
def ask_for_feedback_comments(ctx: RunContext) -> str:
    """Asks the user to describe their negative experience in detail."""
    state = ctx.deps.get("state", {})
    name = ctx.deps.get("name", "there")

    # Check if feedback flow is already complete
    if state.get("conversation_complete"):
        return f"Thanks {name}, I've already collected your feedback. Is there anything else I can help you with?"

    if state.get("comments"):
        return f"Thanks!, you've already shared your comments: \"{state['comments']}\"."

    rating = state.get("satisfaction_rating")
    if not rating:
        return f"Before we proceed, please let me know how you'd rate your experience on a scale of 1 to 5."
    state["awaiting_comments"] = True
    return (
        f"Thanks for the rating, {name}. "
        "Could you please describe what happened in a few words?"
    )


# 5. categorize the feedback comments of user
@feedback_agent.tool
def categorize_feedback(ctx: RunContext, comments: str) -> str:
    """Classifies feedback into predefined categories."""
    uvicorn_logger.info(
        "🔍 Categorizing feedback...", extra={"feedback_preview": comments[:50]}
    )
    start_time = time.time()
    state = ctx.deps.get("state", {})
    if state.get("category"):
        return f"{state['category']}."

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
        ],
        "Staff": [
            "nurse",
            "doctor",
            "receptionist",
            "staff",
            "employee",
            "rude",
            "friendly",
            "helpful",
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
            "bed",
            "chair",
            "building",
            "parking",
            "facility",
            "environment",
        ],
        "Treatment": [
            "medicine",
            "procedure",
            "treatment",
            "diagnosis",
            "prescription",
            "care",
            "pain",
            "healing",
        ],
        "Communication": [
            "explain",
            "told",
            "information",
            "informed",
            "understand",
            "clarity",
            "communication",
        ],
        "Other": [],
    }

    feedback_lower = comments.lower()
    match_counts = {
        category: sum(keyword in feedback_lower for keyword in keywords)
        for category, keywords in categories.items()
    }

    best_category = max(match_counts.items(), key=lambda x: x[1])[0]
    if match_counts[best_category] == 0:
        best_category = "Other"

    uvicorn_logger.info(
        "Categorization done",
        extra={"category": best_category, "time": f"{time.time() - start_time:.2f}s"},
    )

    state["category"] = best_category
    return best_category


# 6. save the data to db
@feedback_agent.tool
def save_feedback_to_database(ctx: RunContext) -> str:
    """Saves structured feedback into MongoDB from the context."""
    try:
        state = ctx.deps.get("state", {})
        name = ctx.deps.get("name")
        nhs_number = ctx.deps.get("nhs_number")
        rating = state.get("satisfaction_rating")
        comments = state.get("comments")
        category = state.get("category")

        if not all([name, nhs_number, rating, comments]):
            return "⚠Some required fields (name, rating, or comments) are missing. Please complete the feedback."

        category = categorize_feedback(ctx, comments)

        feedback_doc = {
            "patient_name": name,
            "nhs_number": nhs_number,
            "satisfaction_rating": int(rating),
            "comments": comments,
            "category": category,
        }

        feedback_collection.insert_one(feedback_doc)
        state["feedback_saved"] = True
        # Mark the conversation as complete after saving feedback
        state["conversation_complete"] = True

        return f"✅ Thanks {name}, your feedback has been saved. We’ll use this to improve our service!"
    except Exception as e:
        return f"❌ Error saving feedback: {str(e)}"


# 4 Identify Recurring Issues
@feedback_agent.tool
def find_common_issues(ctx: RunContext) -> list:
    """Returns top recurring issues based on feedback comment keywords."""
    name = ctx.deps.get("name", "there")
    state = ctx.deps.get("state", {})
    all_feedback = feedback_collection.find()
    all_comments = " ".join(f.get("comments", "") for f in all_feedback).lower()

    issue_keywords = {
        "wait": "Long waiting times",
        "delay": "Long waiting times",
        "hours": "Long waiting times",
        "billing": "Billing and insurance issues",
        "bill": "Billing and insurance issues",
        "insurance": "Billing and insurance issues",
        "payment": "Billing and insurance issues",
        "rude": "Staff communication and attitude concerns",
        "attitude": "Staff communication and attitude concerns",
        "communication": "Staff communication and attitude concerns",
        "cleanliness": "Facility cleanliness and comfort",
        "dirty": "Facility cleanliness and comfort",
        "clean": "Facility cleanliness and comfort",
        "explain": "Lack of clear medical explanations",
        "understanding": "Lack of clear medical explanations",
        "information": "Lack of clear medical explanations",
        "parking": "Parking and accessibility issues",
        "access": "Parking and accessibility issues",
    }

    issue_counts = {}
    for keyword, description in issue_keywords.items():
        count = all_comments.count(keyword)
        if description in issue_counts:
            issue_counts[description] += count
        else:
            issue_counts[description] = count

    top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    if not top_issues:
        return [f"No common issues found, {name}."]

    # Set conversation as completed once we reach this step
    state["conversation_complete"] = True

    return [f"• {desc} ({count} mentions)" for desc, count in top_issues]


# NEW TOOL: Handle general responses after feedback is complete
@feedback_agent.tool
def handle_general_response(ctx: RunContext, message: str) -> str:
    """Handles general responses after the feedback collection is complete."""
    state = ctx.deps.get("state", {})
    name = ctx.deps.get("name", "there")

    if not state.get("feedback_saved"):
        return None

    gratitude_keywords = [
        "thank",
        "thanks",
        "thx",
        "appreciate",
        "grateful",
        "thankyou",
        "Thank you",
    ]
    if any(keyword in message.lower() for keyword in gratitude_keywords):
        return f"You're welcome, {name}! Your feedback helps us improve our services. If you have any other questions or concerns in the future, please don't hesitate to reach out."

    goodbye_keywords = ["bye", "goodbye", "see you", "farewell"]
    if any(keyword in message.lower() for keyword in goodbye_keywords):
        return f"Goodbye, {name}! Thank you for your time and feedback. Have a wonderful day!"

    # Handle general follow-up
    return f"Thank you for your engagement, {name}. Your feedback has been recorded. Is there anything else you'd like to discuss about our healthcare services?"


# 5 Trend Analysis
@feedback_agent.tool
def generate_trend_analysis(ctx: RunContext) -> str:
    """Generates a summary report of feedback trends."""
    feedback_docs = list(feedback_collection.find())
    name = ctx.deps.get("name", "there")

    if not feedback_docs:
        return f"No feedback records found yet, {name}."

    # 1. Satisfaction ratings
    ratings = [
        f["satisfaction_rating"] for f in feedback_docs if "satisfaction_rating" in f
    ]
    avg_rating = sum(ratings) / len(ratings)

    # 2. Rating distribution
    rating_distribution = {i: ratings.count(i) for i in range(1, 6)}

    # 3. Category analysis
    categories = [f.get("category", "Unknown") for f in feedback_docs]
    category_counts = {}
    for cat in categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1
    top_category = max(category_counts.items(), key=lambda x: x[1])[0]

    # Format report
    report = (
        f"📊 **Feedback Trend Summary for {name}:**\n"
        f"• Total feedback received: {len(ratings)}\n"
        f"• Average satisfaction rating: {avg_rating:.2f}/5\n"
        f"• Most discussed category: {top_category}\n"
        f"• Rating distribution:\n"
    )
    for rating, count in rating_distribution.items():
        report += f"   - {rating}: {count}\n"

    return report


# 6 Critical Issue Alerts
@feedback_agent.tool
def detect_critical_issues(ctx: RunContext) -> list:
    """Scans comments for critical incidents and alerts."""
    name = ctx.deps.get("name", "there")

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
    }

    critical_issues = []
    for feedback in feedback_collection.find():
        comment = feedback.get("comments", "").lower()
        nhs = feedback.get("nhs_number", "unknown")

        for keyword, description in critical_keywords.items():
            if keyword in comment:
                critical_issues.append(f"⚠️ {description} reported (NHS: {nhs})")

    if not critical_issues:
        return [f"No critical issues detected at the moment, {name}."]
    return critical_issues


# 7. Check conversation state to determine if we need to start a new feedback flow
@feedback_agent.tool
def check_conversation_state(ctx: RunContext) -> str:
    """Checks the current state of the conversation to determine next actions."""
    state = ctx.deps.get("state", {})
    name = ctx.deps.get("name", "there")

    # If we've already completed the feedback flow
    if state.get("conversation_complete"):
        return f"feedback_flow_complete"

    # If we're in the middle of the feedback flow
    if state.get("awaiting_rating"):
        return "awaiting_rating"
    elif state.get("awaiting_comments"):
        return "awaiting_comments"
    elif state.get("feedback_saved"):
        return "feedback_saved"

    # Default - new conversation
    return "new_conversation"


# Function to run the agent
async def run_agent(user_input: str, user_context: dict = None) -> str:
    """Run the agent with a query and return the response."""
    try:
        if user_context is None:
            user_context = {}

        response = await feedback_agent.run(user_input, deps=user_context)

        if hasattr(response, "data"):
            return str(response.data)
        return str(response)
    except Exception as e:
        print(f"Error running agent: {str(e)}")
        return "Sorry, I encountered an error while processing your request."


# Terminal interface for the agent
def main():
    print("=" * 50)
    print("Digital Patient Feedback & Experience Agent")
    print("=" * 50)
    print("Type 'exit' to quit, 'help' for available commands")
    print()
    while True:
        try:
            user_input = input("Patient > ")

            if user_input.lower() == "exit":
                print("Thank you for using our feedback system. Goodbye!")
                break

            elif user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  help            - Show this help message")
                print("  exit            - Exit the program")
                print("  analyze         - Analyze existing feedback")
                print("  trends          - Generate trend analysis")
                print("  issues          - Find common issues")
                print("  critical        - Detect critical issues")
                print("  Or just type your feedback to get started")
                print()
                continue

            elif user_input.lower() == "analyze":
                print("\nAnalyzing existing feedback...")
                # Call specific tools directly
                issues = find_common_issues(RunContext())
                print("\nCommon Issues Found:")
                for issue in issues:
                    print(f"- {issue}")
                print()
                continue

            elif user_input.lower() == "trends":
                print("\nGenerating trend analysis...")
                trend_report = generate_trend_analysis(RunContext())
                print(f"\n{trend_report}\n")
                continue

            elif user_input.lower() == "issues":
                print("\nFinding common issues...")
                issues = find_common_issues(RunContext())
                print("\nCommon Issues Found:")
                for issue in issues:
                    print(f"- {issue}")
                print()
                continue

            elif user_input.lower() == "critical":
                print("\nDetecting critical issues...")
                critical = detect_critical_issues(RunContext())
                print("\nCritical Issues Found:")
                for issue in critical:
                    print(f"- {issue}")
                print()
                continue
            response = run_agent(user_input)
            print(f"\nAgent: {response}\n")
        except KeyboardInterrupt:
            print("\nExiting the program. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {str(e)}\n")


if __name__ == "__main__":
    main()
