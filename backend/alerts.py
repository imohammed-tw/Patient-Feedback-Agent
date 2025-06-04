# alerts.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def send_slack_alert(message: str):
    if not SLACK_WEBHOOK_URL:
        print(" Slack webhook URL not set.")
        return

    payload = {"text": message}

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code != 200:
            print(f" Slack alert failed: {response.text}")
    except Exception as e:
        print(f" Exception in Slack alert: {str(e)}")
