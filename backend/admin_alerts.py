# critical/urgent/emergency alerts

from database import feedback_collection, alerted_feedbacks
from alerts import send_slack_alert
from bson.objectid import ObjectId


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

    for feedback in feedback_collection.find({"alert_acknowledged": {"$ne": True}}):
        comment = feedback.get("comments", "").lower()
        matched_keyword = next((k for k in critical_keywords if k in comment), None)

        if matched_keyword:
            description = critical_keywords[matched_keyword]
            send_slack_alert_with_buttons(feedback, description)
