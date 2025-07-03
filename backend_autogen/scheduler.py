# scheduler.py - Automated periodic scheduled alerts
from apscheduler.schedulers.background import BackgroundScheduler
from alerts import send_slack_alert
from tools import find_common_issues, generate_trend_analysis  # Import from our tools
from admin_alerts import scan_critical_issues_and_alert, send_critical_feedback_summary
from database import feedback_collection
import time
from datetime import datetime, timedelta


def send_trend_summary():
    """
    Generate and send scheduled trend analysis to Slack
    """
    try:
        print("📤 Sending scheduled trend report...")

        # Get trend analysis from our existing tools
        trend_report = generate_trend_analysis()
        common_issues = find_common_issues()

        # Get recent feedback count (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        recent_feedback_count = feedback_collection.count_documents(
            {"_id": {"$gte": ObjectId.from_datetime(yesterday)}}
        )

        # Format the summary message
        summary = (
            f"📢 *Daily Feedback Trend Analysis - {datetime.now().strftime('%Y-%m-%d')}*\n\n"
            f" *Recent Activity:*\n"
            f"• New feedback in last 24h: {recent_feedback_count}\n\n"
            f" *Trend Analysis:*\n"
            f"{trend_report}\n\n"
            f" *Top Issues:*\n"
            f"{common_issues}\n\n"
        )

        # Send to Slack
        success = send_slack_alert(summary)

        if success:
            print("✅ Scheduled trend summary sent successfully")
        else:
            print("❌ Failed to send scheduled trend summary")

        return success

    except Exception as e:
        print(f"❌ Error sending scheduled trend summary: {str(e)}")
        return False


class FeedbackScheduler:
    """
    Manages all scheduled tasks for the feedback system
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def add_jobs(self):
        """Add all scheduled jobs"""

        # Daily trend summary at 9 AM
        self.scheduler.add_job(
            send_trend_summary, "cron", hour=9, minute=0, id="daily_trend_summary"
        )

        # Weekly summary on Mondays at 10 AM
        # self.scheduler.add_job(
        #     send_weekly_summary,
        #     "cron",
        #     day_of_week="mon",
        #     hour=10,
        #     minute=0,
        #     id="weekly_summary",
        # )

        # For testing: Run trend summary every 5 minutes (comment out in production)
        self.scheduler.add_job(
            send_trend_summary, "interval", minutes=5, id="test_trend_summary"
        )

        print("📅 Scheduled jobs configured:")
        print("  • Daily trend summary: 9:00 AM")
        print("  • Critical issue scan: Every 15 minutes")
        print("  • Weekly summary: Mondays 10:00 AM")

    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.add_jobs()
            self.scheduler.start()
            self.is_running = True
            print("⏰ Scheduler started successfully")
        else:
            print("⚠️ Scheduler is already running")

    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            print("⏰ Scheduler stopped")
        else:
            print("⚠️ Scheduler is not running")

    def get_jobs(self):
        """Get list of scheduled jobs"""
        return self.scheduler.get_jobs()

    def run_job_now(self, job_id: str):
        """Manually trigger a specific job"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.func()
                print(f"✅ Manually executed job: {job_id}")
                return True
            else:
                print(f"❌ Job not found: {job_id}")
                return False
        except Exception as e:
            print(f"❌ Error running job {job_id}: {str(e)}")
            return False


# Global scheduler instance
feedback_scheduler = FeedbackScheduler()


def start_scheduler():
    """Start the global scheduler (for backward compatibility)"""
    feedback_scheduler.start()


def stop_scheduler():
    """Stop the global scheduler"""
    feedback_scheduler.stop()


# Import ObjectId for datetime operations
from bson.objectid import ObjectId
