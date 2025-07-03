# alerts.py - Slack integration for critical feedback alerts
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
    """
    Send critical feedback alert to Slack with action buttons

    Args:
        feedback (dict): Feedback document from MongoDB
        alert_message (str): Description of the critical issue
    """
    try:
        if not client.token:
            print("❌ Slack bot token not configured")
            return False

        feedback_id = str(feedback.get("_id", "unknown"))
        patient_name = feedback.get("patient_name", "Unknown")

        print(f"🔍 Attempting to send Slack alert for feedback ID: {feedback_id}")
        print(f"🔍 Patient: {patient_name}, Issue: {alert_message}")
        print(f"🔍 Channel: {SLACK_ALERT_CHANNEL}")

        slack_message = (
            f"🚨 *Critical Feedback Alert:*\n"
            f"> *Patient:* {patient_name}\n"
            f"> *Issue:* {alert_message}\n"
            f"> *Rating:* {feedback.get('satisfaction_rating', 'N/A')}/5\n"
            f"> *Category:* {feedback.get('category', 'N/A')}"
        )

        response = client.chat_postMessage(
            channel=SLACK_ALERT_CHANNEL,
            text="🚨 Critical Feedback Alert",
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
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject"},
                            "value": feedback_id,
                            "action_id": "reject_alert_modal",
                            "style": "danger",
                        },
                    ],
                },
            ],
        )

        print(
            f"✅ Slack critical alert sent successfully. Message TS: {response['ts']}"
        )
        return True

    except SlackApiError as e:
        error_code = e.response["error"]
        print(f"❌ Slack API error: {error_code}")

        if error_code == "not_in_channel":
            print(
                f"🔧 Bot is not in channel {SLACK_ALERT_CHANNEL}. Please invite the bot:"
            )
            print(f"   1. Go to {SLACK_ALERT_CHANNEL} channel")
            print(f"   2. Type: /invite @your-bot-name")
            print(f"   3. Or add bot via channel settings")
        elif error_code == "channel_not_found":
            print(
                f"🔧 Channel {SLACK_ALERT_CHANNEL} not found. Check channel name in .env"
            )
        elif error_code == "invalid_auth":
            print(f"🔧 Invalid bot token. Check SLACK_BOT_TOKEN in .env")

        return False
    except Exception as e:
        print(f"❌ Error sending Slack alert: {str(e)}")
        return False


def send_slack_alert(message: str):
    """
    Send simple text alert to Slack (for scheduled reports)

    Args:
        message (str): Message to send
    """
    try:
        if not client.token:
            print("❌ Slack bot token not configured")
            return False

        print(f"🔍 Sending message to channel: {SLACK_ALERT_CHANNEL}")

        response = client.chat_postMessage(channel=SLACK_ALERT_CHANNEL, text=message)

        print(f"✅ Slack alert sent successfully. Message TS: {response['ts']}")
        return True

    except SlackApiError as e:
        error_code = e.response["error"]
        print(f"❌ Slack API error: {error_code}")

        if error_code == "not_in_channel":
            print(
                f"🔧 Bot is not in channel {SLACK_ALERT_CHANNEL}. Please invite the bot:"
            )
            print(f"   1. Go to {SLACK_ALERT_CHANNEL} channel")
            print(f"   2. Type: /invite @your-bot-name")
        elif error_code == "channel_not_found":
            print(
                f"🔧 Channel {SLACK_ALERT_CHANNEL} not found. Check channel name in .env"
            )

        return False
    except Exception as e:
        print(f"❌ Error sending Slack message: {str(e)}")
        return False


def test_slack_connection():
    """Test Slack connection and permissions"""
    try:
        response = client.auth_test()
        print(f"✅ Slack connection successful! Bot: {response['user']}")
        return True
    except SlackApiError as e:
        print(f"❌ Slack connection failed: {e.response['error']}")
        return False
