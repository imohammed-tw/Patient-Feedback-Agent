from fastapi import FastAPI, HTTPException, WebSocket
from models import RegisterRequest, LoginRequest
from database import users_collection
from fastapi.middleware.cors import CORSMiddleware
from ai_agent import feedback_agent
import json
from pydantic_ai import RunContext

app = FastAPI()

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
}


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
