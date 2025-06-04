# alerts.py
import os
import requests
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_ALERT_CHANNEL = os.getenv("SLACK_ALERT_CHANNEL", "#alerts")

client = WebClient(token=SLACK_BOT_TOKEN)


def send_slack_alert_with_buttons(feedback: dict):
    try:
        feedback_id = str(feedback.get("_id", "unknown"))
        name = feedback.get("patient_name", "Unknown")
        nhs_number = feedback.get("nhs_number", "Unknown")
        rating = feedback.get("satisfaction_rating", "N/A")
        comments = feedback.get("comments", "No comment provided")
        category = feedback.get("category", "Uncategorized")

        message = (
            f"*Critical Feedback Alert*\n"
            f"*Patient:* {name}\n"
            f"*NHS Number:* {nhs_number}\n"
            f"*Rating:* {rating}/5\n"
            f"*Category:* {category}\n"
            f"*Feedback:* {comments}"
        )

        response = client.chat_postMessage(
            channel=SLACK_ALERT_CHANNEL,
            text=f"🚨 New critical feedback from {name}",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "👁️ View Patient"},
                            "value": feedback_id,
                            "action_id": "view_patient",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Acknowledge"},
                            "value": feedback_id,
                            "action_id": "acknowledge_alert",
                            "style": "primary",
                        },
                    ],
                },
            ],
        )
        print(f"✅ Slack critical alert sent for feedback ID: {feedback_id}")
    except SlackApiError as e:
        print(f"❌ Slack API error: {e.response['error']}")


def send_slack_alert(message: str):
    try:
        client.chat_postMessage(channel=SLACK_ALERT_CHANNEL, text=message)
        print("✅ Slack alert sent.")
    except SlackApiError as e:
        print(f"❌ Slack API error: {e.response['error']}")
