from fastapi import FastAPI, HTTPException, WebSocket, Request, APIRouter
from models import RegisterRequest, LoginRequest
from database import users_collection, feedback_collection
from fastapi.middleware.cors import CORSMiddleware
from ai_agent import feedback_agent
import json
from pydantic_ai import RunContext
import hmac, hashlib, os, time, json
from starlette.responses import JSONResponse
from slack_sdk.web import WebClient
from bson.objectid import ObjectId
from otel_setup import setup_otel
from opentelemetry import trace
from scheduler import start_scheduler
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = FastAPI()
setup_otel(app)
start_scheduler()


SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_NHS_NUMBERS = {
    "1234567890": {
        "age": 30,
        "gender": "Male",
        "date_of_treatment": "2024-04-10",
        "health_issue": "Hypertension",
    },
    "1234567891": {
        "age": 24,
        "gender": "Female",
        "date_of_treatment": "2025-04-26",
        "health_issue": "Leg Fracture",
    },
    "1234567892": {
        "age": 21,
        "gender": "Male",
        "date_of_treatment": "2025-05-02",
        "health_issue": "Gut issues",
    },
    "1234567893": {
        "age": 35,
        "gender": "Female",
        "date_of_treatment": "2025-05-10",
        "health_issue": "Chest pain",
    },
}


@app.post("/slack/interaction")
async def slack_interaction_handler(request: Request):
    # ✅ 1. Signature validation
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    slack_signature = request.headers.get("X-Slack-Signature")

    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=403, detail="Request too old")

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = (
        "v0="
        + hmac.new(
            SLACK_SIGNING_SECRET.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
    )

    if not hmac.compare_digest(my_signature, slack_signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    # ✅ 2. Parse payload
    form_data = await request.form()
    payload = json.loads(form_data["payload"])
    payload_type = payload.get("type")

    if payload_type == "block_actions":
        action_id = payload["actions"][0]["action_id"]
        feedback_id = payload["actions"][0]["value"]
        channel_id = payload["channel"]["id"]
        user = payload["user"]["username"]

        feedback = feedback_collection.find_one({"_id": ObjectId(feedback_id)})
        if not feedback:
            slack_client.chat_postMessage(
                channel=channel_id, text="❌ Feedback not found."
            )
            return JSONResponse(content={"ok": True})

        nhs_number = feedback.get("nhs_number", "unknown")
        user_doc = users_collection.find_one({"nhs number.number": nhs_number})
        nhs_data = user_doc.get("nhs number", {}) if user_doc else {}

        if action_id == "acknowledge_alert":
            feedback_collection.update_one(
                {"_id": ObjectId(feedback_id)}, {"$set": {"alert_acknowledged": True}}
            )

            notifications_collection.insert_one(
                {
                    "nhs_number": nhs_number,
                    "type": "acknowledged",
                    "message": "Your feedback was reviewed and acknowledged by the admin.",
                    "timestamp": datetime.utcnow(),
                    "read": False,
                    "feedback": {
                        "comment": feedback.get("comments"),
                        "category": feedback.get("category"),
                        "rating": feedback.get("satisfaction_rating"),
                    },
                }
            )

            # Update original message to disable buttons
            slack_client.chat_update(
                channel=channel_id,
                ts=payload["message"]["ts"],
                text="✅ Feedback acknowledged",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *{user}* acknowledged this feedback alert.",
                        },
                    }
                ],
            )

            slack_client.chat_postMessage(
                channel=channel_id,
                text=f"✅ *{user}* acknowledged alert for feedback `{feedback_id}`",
            )

        elif action_id == "view_patient":
            if not user_doc:
                slack_client.chat_postMessage(
                    channel=channel_id, text="❌ Patient not found."
                )
                return JSONResponse(content={"ok": True})

            feedback_time = feedback["_id"].generation_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            msg = (
                f"*👤 Patient Details:*\n"
                f"> *Name:* {user_doc.get('name', 'Unknown')}\n"
                f"> *NHS Number:* {nhs_number}\n"
                f"> *Age:* {nhs_data.get('age', 'N/A')}\n"
                f"> *Gender:* {nhs_data.get('gender', 'N/A')}\n"
                f"> *Health Issue:* {nhs_data.get('health_issue', 'N/A')}\n"
                f"> *Date of Treatment:* {nhs_data.get('date_of_treatment', 'N/A')}\n\n"
                f"*📝 Feedback Details:*\n"
                f"> *Submitted On:* {feedback_time}\n"
                f"> *Rating:* {feedback.get('satisfaction_rating', 'N/A')}/5\n"
                f"> *Category:* {feedback.get('category', 'N/A')}\n"
                f"> *Comment:* {feedback.get('comments', 'N/A')}"
            )

            slack_client.chat_postMessage(channel=channel_id, text=msg)
            

        elif action_id == "reject_alert_modal":
            # Open Slack modal with note input
            trigger_id = payload["trigger_id"]
            slack_client.views_open(
                trigger_id=trigger_id,
                view={
                    "type": "modal",
                    "callback_id": "submit_rejection_note",
                    "private_metadata": feedback_id,
                    "title": {"type": "plain_text", "text": "Reject Feedback"},
                    "submit": {"type": "plain_text", "text": "Submit"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "note_block",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "note_input",
                                "multiline": True,
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "Reason for rejection",
                            },
                        }
                    ],
                },
            )

    elif (
        payload_type == "view_submission"
        and payload["view"]["callback_id"] == "submit_rejection_note"
    ):
        feedback_id = payload["view"]["private_metadata"]
        note = payload["view"]["state"]["values"]["note_block"]["note_input"]["value"]
        user = payload["user"]["username"]

        feedback = feedback_collection.find_one({"_id": ObjectId(feedback_id)})
        nhs_number = feedback.get("nhs_number", "unknown")

        # Save to notifications
        notifications_collection.insert_one(
            {
                "nhs_number": nhs_number,
                "type": "rejected",
                "message": "Your feedback was reviewed and rejected by the admin.",
                "note": note,
                "timestamp": datetime.utcnow(),
                "read": False,
                "feedback": {
                    "comment": feedback.get("comments"),
                    "category": feedback.get("category"),
                    "rating": feedback.get("satisfaction_rating"),
                },
            }
        )

        # Mark as rejected
        feedback_collection.update_one(
            {"_id": ObjectId(feedback_id)}, {"$set": {"alert_rejected": True}}
        )

        # 📢 Public alert update in original message
        slack_client.chat_update(
            channel=payload["container"]["channel_id"],
            ts=payload["container"]["message_ts"],
            text="❌ Feedback rejected",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *{user}* rejected this feedback alert.\n> _{note}_",
                    },
                }
            ],
        )

        #  post it visibly in the channel
        slack_client.chat_postMessage(
            channel=os.getenv("SLACK_ALERT_CHANNEL", "#alerts"),
            text=f"❌ *{user}* rejected alert for feedback `{feedback_id}` with note:\n> {note}",
        )

        # Respond in Slack (private)
        # slack_client.chat_postMessage(
        #     channel=payload["user"]["id"],
        #     text=f"❌ You rejected feedback `{feedback_id}` with note:\n> {note}",
        # )

    return JSONResponse(content={"ok": True}, status_code=200)


@app.get("/notifications/{nhs_number}")
async def get_notifications(nhs_number: str):
    notifications = notifications_collection.find({"nhs_number": nhs_number})
    results = []

    for n in notifications:
        results.append(
            {
                "type": n.get("type"),
                "message": n.get("message"),
                "note": n.get("note", None),  # May not exist for acknowledgments
                "timestamp": (
                    n.get("timestamp").isoformat() if n.get("timestamp") else None
                ),
                "read": n.get("read", False),
                "feedback": n.get("feedback", {}),
            }
        )

    return {"notifications": results}


@app.post("/notifications/mark-read/{nhs_number}")
async def mark_all_as_read(nhs_number: str):
    result = notifications_collection.update_many(
        {"nhs_number": nhs_number, "read": False}, {"$set": {"read": True}}
    )
    return {"updated": result.modified_count}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket connection established")

    user_context = {}
    state = {}

    while True:
        try:
            data_raw = await websocket.receive_text()
            print(f"🧠 Received raw data: {data_raw}")

            try:
                data = json.loads(data_raw)

                if data.get("type") == "init" and "nhsNumber" in data:
                    nhs_number = data["nhsNumber"]
                    print(f"🔄 Initializing user with NHS number: {nhs_number}")

                    user = users_collection.find_one({"nhs number.number": nhs_number})
                    if user:
                        state = {}  # reset state for new session
                        user_context = {
                            "name": user["name"],
                            "nhs_number": user["nhs number"]["number"],
                            "age": user["nhs number"]["age"],
                            "gender": user["nhs number"]["gender"],
                            "date_of_treatment": user["nhs number"][
                                "date_of_treatment"
                            ],
                            "health_issue": user["nhs number"]["health_issue"],
                            "state": state,  # attach state
                        }
                        await websocket.send_text(
                            f"Hi {user['name']}! How can I assist you today? Is there anything you want to share about your recent experience with our healthcare services? I would be glad to hear them :)"
                        )

                    else:
                        await websocket.send_text("❌ NHS number not found.")
                    continue

                elif data.get("type") == "new_chat":
                    print("🔁 New chat requested")
                    state = {}  # Reset state
                    user_context["state"] = {}  # Clear state in context
                    await websocket.send_text(
                        f"🧠 Starting a new chat session, {user_context.get('name', 'there')}! How can I assist you today?"
                    )
                    continue
                # extract message content
                message_content = (
                    data.get("content", "") if isinstance(data, dict) else data_raw
                )
                print(f"💬 Processing: {message_content}")

                # state update logic
                if message_content.strip().isdigit():
                    rating = int(message_content.strip())
                    if 1 <= rating <= 5:
                        user_context["state"]["satisfaction_rating"] = rating
                        user_context["state"]["awaiting_rating"] = False
                        print(f"📥 Saved rating: {rating}")
                elif user_context["state"].get("awaiting_comments"):
                    user_context["state"]["comments"] = message_content
                    user_context["state"]["awaiting_comments"] = False
                    print("📥 Saved user comments.")

                # call the agent with context
                agent_result = await feedback_agent.run(
                    message_content, deps=user_context
                )

                if hasattr(agent_result, "data"):
                    result = str(agent_result.data)
                else:
                    result = str(agent_result)

                print(f"🤖 Agent response: {result}")
                await websocket.send_text(result)

            except Exception as e:
                print(f"❌ Error processing: {str(e)}")
                await websocket.send_text("An error occurred. Please try again.")

        except Exception as e:
            print(f"❌ WebSocket closed or errored: {str(e)}")
            break


@app.post("/register")
def register_user(payload: RegisterRequest):
    if payload.nhsNumber not in VALID_NHS_NUMBERS:
        raise HTTPException(status_code=400, detail="Invalid NHS Number")

    existing = users_collection.find_one({"name": payload.name})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    nhs_info = VALID_NHS_NUMBERS[payload.nhsNumber]

    new_user = {
        "name": payload.name,
        "password": payload.password,
        "nhs number": {"number": payload.nhsNumber, **nhs_info},
    }

    users_collection.insert_one(new_user)
    return {"message": "Registered successfully"}


@app.post("/login")
def login_user(payload: LoginRequest):
    user = users_collection.find_one(
        {"nhs number.number": payload.nhsNumber, "password": payload.password}
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "message": "Login successful",
        "user": {
            "name": user["name"],
            "nhsNumber": user["nhs number"]["number"],
            "age": user["nhs number"]["age"],
            "gender": user["nhs number"]["gender"],
            "date_of_treatment": user["nhs number"]["date_of_treatment"],
            "health_issue": user["nhs number"]["health_issue"],
        },
    }
