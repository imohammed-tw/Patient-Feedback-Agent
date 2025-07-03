# admin_alerts.py - Critical/urgent/emergency alerts scanning and notification
from database import feedback_collection
from alerts import send_slack_alert_with_buttons
from bson.objectid import ObjectId


def scan_critical_issues_and_alert():
    """
    Scans recent feedback for critical incidents and sends Slack alerts.
    Not part of the AI agent tools. Meant to be called manually or via scheduler.
    """

    # Same critical keywords as in detect_critical_issues tool
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

    print("🔍 Scanning for critical feedback issues...")
    alerts_sent = 0

    try:
        # Find feedback that hasn't been acknowledged and doesn't have alert flags
        query = {
            "$and": [
                {"alert_acknowledged": {"$ne": True}},
                {"alert_rejected": {"$ne": True}},
                {
                    "slack_alert_sent": {"$ne": True}
                },  # New flag to prevent duplicate alerts
            ]
        }

        for feedback in feedback_collection.find(query):
            comment = feedback.get("comments", "").lower()
            matched_keywords = []

            # Check for all matching keywords
            for keyword, description in critical_keywords.items():
                if keyword in comment:
                    matched_keywords.append(description)

            if matched_keywords:
                # Use the first matched critical issue as the main alert message
                primary_alert = matched_keywords[0]

                # Add count if multiple issues detected
                if len(matched_keywords) > 1:
                    primary_alert += (
                        f" (+{len(matched_keywords)-1} other critical issues)"
                    )

                # Send Slack alert
                if send_slack_alert_with_buttons(feedback, primary_alert):
                    # Mark as alerted to prevent duplicate notifications
                    feedback_collection.update_one(
                        {"_id": feedback["_id"]},
                        {
                            "$set": {
                                "slack_alert_sent": True,
                                "critical_issues_detected": matched_keywords,
                                "alert_sent_timestamp": feedback["_id"].generation_time,
                            }
                        },
                    )
                    alerts_sent += 1
                    print(f"🚨 Alert sent for feedback ID: {feedback['_id']}")

    except Exception as e:
        print(f"❌ Error scanning critical issues: {str(e)}")
        return False

    print(f"✅ Critical issue scan complete. {alerts_sent} alerts sent.")
    return alerts_sent


def mark_feedback_as_critical(feedback_id: str, critical_issues: list):
    """
    Mark a feedback record as having critical issues

    Args:
        feedback_id (str): MongoDB ObjectId as string
        critical_issues (list): List of detected critical issue descriptions
    """
    try:
        result = feedback_collection.update_one(
            {"_id": ObjectId(feedback_id)},
            {
                "$set": {
                    "is_critical": True,
                    "critical_issues": critical_issues,
                    "critical_flagged_timestamp": ObjectId().generation_time,
                }
            },
        )

        if result.modified_count > 0:
            print(f"✅ Feedback {feedback_id} marked as critical")
            return True
        else:
            print(f"⚠️ Feedback {feedback_id} not found or already marked")
            return False

    except Exception as e:
        print(f"❌ Error marking feedback as critical: {str(e)}")
        return False


def get_unacknowledged_critical_feedback():
    """
    Get all critical feedback that hasn't been acknowledged

    Returns:
        list: List of critical feedback documents
    """
    try:
        query = {
            "$and": [
                {"alert_acknowledged": {"$ne": True}},
                {"alert_rejected": {"$ne": True}},
                {"is_critical": True},
            ]
        }

        critical_feedback = list(feedback_collection.find(query).sort("_id", -1))
        print(
            f"📊 Found {len(critical_feedback)} unacknowledged critical feedback items"
        )

        return critical_feedback

    except Exception as e:
        print(f"❌ Error retrieving critical feedback: {str(e)}")
        return []


def send_critical_feedback_summary():
    """
    Send a summary of all unacknowledged critical feedback to Slack
    """
    try:
        critical_items = get_unacknowledged_critical_feedback()

        if not critical_items:
            print("✅ No unacknowledged critical feedback found")
            return True

        summary_message = (
            f"📋 *Critical Feedback Summary* ({len(critical_items)} items)\n\n"
        )

        for item in critical_items[:10]:  # Limit to 10 most recent
            patient_name = item.get("patient_name", "Unknown")
            issues = item.get("critical_issues", ["Unknown issue"])
            primary_issue = issues[0] if issues else "Unknown issue"

            summary_message += f"• **{patient_name}**: {primary_issue}\n"

        if len(critical_items) > 10:
            summary_message += f"\n_...and {len(critical_items) - 10} more items_"

        summary_message += f"\n\n🔗 Use `/alerts scan` to process new critical feedback"

        from alerts import send_slack_alert

        return send_slack_alert(summary_message)

    except Exception as e:
        print(f"❌ Error sending critical feedback summary: {str(e)}")
        return False
