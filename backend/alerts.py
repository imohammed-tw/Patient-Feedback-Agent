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


def send_slack_alert_with_buttons(feedback: dict, alert_message: str):
    try:
        feedback_id = str(feedback.get("_id", "unknown"))

        slack_message = f"🚨 *Critical Feedback Alert:*\n" f"> *{alert_message}*"

        client.chat_postMessage(
            channel=SLACK_ALERT_CHANNEL,
            text="🚨 Critical feedback received",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn", "text": slack_message}},
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

