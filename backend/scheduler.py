# Automated periodic scheduled alerts

from apscheduler.schedulers.background import BackgroundScheduler
from alerts import send_slack_alert
from ai_agent import generate_trend_analysis, find_common_issues
from database import users_collection
from pydantic_ai import RunContext
import time


def send_trend_summary():
    try:
        print("📤 Sending scheduled trend report...")

        class MockCtx:
            def __init__(self):
                self.deps = {"name": "Admin", "state": {}}

        ctx = MockCtx()

        trend = generate_trend_analysis(ctx)
        issues = find_common_issues(ctx)

        summary = (
            f"📢 *Scheduled Feedback Summary:*\n\n"
            f"{trend}\n"
            f"🔁 *Top Recurring Issues:*\n" + "\n".join(issues)
        )

        send_slack_alert(summary)

    except Exception as e:
        print(f" Error sending scheduled trend summary: {str(e)}")


def start_scheduler():
    scheduler = BackgroundScheduler()

    # Daily at 9 AM (can adjust with cron or interval)
    # scheduler.add_job(send_trend_summary, "cron", hour=9, minute=0)
    scheduler.add_job(
        send_trend_summary, "interval", minutes=5
    )  # Runs every minute for testing

    scheduler.start()
    print("⏰ Scheduler started for daily trend summary")
