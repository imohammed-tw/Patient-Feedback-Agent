# critical/urgent/emergency alerts

from database import feedback_collection, alerted_feedbacks
from alerts import send_slack_alert
from bson.objectid import ObjectId
from datetime import datetime


def scan_critical_issues_and_alert():
    """
    Scans recent feedback for critical incidents and sends Slack alerts.
    Not part of the AI agent tools. Meant to be called manually.
    """
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
        "ICU Delay": "Delay in moving critical patient to ICU",
        "misdiagnosis": "Potential misdiagnosis incident",
        "collapsed": "Physical collapse or serious deterioration",
        "oxygen problem": "Oxygen supply issue",
    }

    critical_issues = []
    alerted_feedback_ids = set(
        str(entry["feedback_id"]) for entry in alerted_feedbacks.find()
    )

    for feedback in feedback_collection.find():
        feedback_id = str(feedback.get("_id"))
        nhs = feedback.get("nhs_number", "unknown")
        comment = feedback.get("comments", "").lower()

        if feedback_id in alerted_feedback_ids:
            continue  # already alerted, skip

        matched_keywords = [
            keyword for keyword in critical_keywords if keyword in comment
        ]

        if matched_keywords:
            for keyword in matched_keywords:
                description = critical_keywords[keyword]
                critical_issues.append(f"⚠️ {description} reported (NHS: {nhs})")

            # Save to cache to avoid re-alerting
            alerted_feedbacks.insert_one(
                {
                    "feedback_id": ObjectId(feedback_id),
                    "nhs_number": nhs,
                    "alerted_keywords": matched_keywords,
                    "alerted_at": datetime.utcnow(),
                }
            )

    if critical_issues:
        alert_msg = "*🚨 New Critical Patient Issues Detected:*\n" + "\n".join(
            critical_issues[:3]
        )  # Limit
        send_slack_alert(alert_msg)
