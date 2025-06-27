from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv
from datetime import datetime
from bson.objectid import ObjectId

# Assuming models.py and database.py are correctly set up and contain necessary definitions
from models import RegisterRequest, LoginRequest
from database import users_collection, feedback_collection, notifications_collection
from tracing_config import setup_enhanced_tracing, get_tracing_config
import asyncio
import os, time, hmac, hashlib, json

# Import the updated FeedbackSession class and create_feedback_assistant function from agent_autogen
from agent_autogen import FeedbackSession, create_feedback_assistant

# Load environment variables (e.g., MongoDB URI, API keys)
load_dotenv()

# Setup enhanced tracing
tracing_config = setup_enhanced_tracing()
tracer = tracing_config.tracer
app = FastAPI()

# FastAPI Middleware for Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sample NHS data for user registration and login validation
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
    "1234567894": {
        "age": 25,
        "gender": "Male",
        "date_of_treatment": "2025-06-05",
        "health_issue": "Intestinal issues",
    },
    "1234567895": {
        "age": 25,
        "gender": "Male",
        "date_of_treatment": "2025-06-10",
        "health_issue": "Breathing/lungs issue",
    },
}

# Persistent session store: maps NHS number (string) to a UserSession instance
user_sessions: dict[str, "UserSession"] = {}


class UserSession:
    """
    Manages a single user's conversation session with the new Tool-Equipped Feedback Agent.
    Each UserSession holds an instance of `FeedbackSession` with async support.
    """

    def __init__(self, user_context: dict):
        self.user_context = user_context
        # Create a new FeedbackSession instance with personalized context
        self.feedback_session: FeedbackSession = self._create_feedback_session()

        # Store conversation history for display or logging purposes
        self.conversation_history: list[dict] = []

        # Track if session is initialized
        self._initialized = False

    def _create_feedback_session(self) -> FeedbackSession:
        """
        Helper method to construct the personalized context string
        and create a `FeedbackSession` instance.
        """
        personal_context = f"""
User Information:
- Name: {self.user_context['name']}
- NHS Number: {self.user_context['nhs_number']}
- Age: {self.user_context['age']}
- Gender: {self.user_context['gender']}
- Health Issue: {self.user_context['health_issue']}
- Treatment Date: {self.user_context['date_of_treatment']}

"""
        return create_feedback_assistant(personal_context)

    async def ensure_initialized(self):
        """Ensure the feedback session is properly initialized"""
        if not self._initialized:
            try:
                await self.feedback_session.initialize()
                self._initialized = True
            except Exception as e:
                print(f"Error initializing feedback session: {str(e)}")
                raise

    async def process_message(self, message: str) -> str:
        """
        Processes a user message by forwarding it to the async FeedbackSession
        and returns the agent's reply.
        """
        with tracer.start_as_current_span("UserSession.process_message"):
            try:
                # Ensure session is initialized
                await self.ensure_initialized()

                # Process the message through the async feedback session
                response = await self.feedback_session.process_message(message)

                # Store the exchange in the session's history
                self.conversation_history.append(
                    {"user": message, "assistant": response}
                )
                return response

            except Exception as e:
                # Log the error and reset the conversation
                print(
                    f"Error in UserSession.process_message for NHS: {self.user_context.get('nhs_number', 'Unknown')}: {str(e)}"
                )
                await self.reset_conversation()
                return "I encountered an issue while processing your request. I have restarted our conversation. How was your recent healthcare experience?"

    async def reset_conversation(self):
        """
        Resets the internal feedback session and clears the session's history.
        """
        try:
            if self._initialized:
                await self.feedback_session.reset()
            self.conversation_history = []
            self._initialized = False
            print(
                f"Reset conversation for NHS: {self.user_context.get('nhs_number', 'Unknown')}"
            )
        except Exception as e:
            print(f"Error resetting conversation: {str(e)}")
            # Create a new session if reset fails
            self.feedback_session = self._create_feedback_session()
            self._initialized = False
            self.conversation_history = []

    async def cleanup(self):
        """Clean up session resources"""
        try:
            if self._initialized and self.feedback_session:
                await self.feedback_session.cleanup()
            self._initialized = False
        except Exception as e:
            print(f"Error during UserSession cleanup: {str(e)}")


# Root endpoint to confirm API is running
@app.get("/")
async def root():
    return {"message": "Patient Feedback Agent API", "status": "running"}


@app.post("/register")
def register_user(payload: RegisterRequest):
    """
    Endpoint for user registration. Validates NHS number and checks for existing users.
    """
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
    """
    Endpoint for user login. Validates NHS number and password.
    """
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time, stateful patient feedback conversations.
    Updated to handle async feedback sessions.
    """
    await websocket.accept()
    print("✅ WebSocket connection established")

    current_session: UserSession | None = None

    try:
        while True:
            data_raw = await websocket.receive_text()
            with tracer.start_as_current_span("WebSocket.message_received"):
                print(f"🧠 Received: {data_raw}")

                try:
                    data = json.loads(data_raw)

                    # Handle session initialization or retrieval
                    if data.get("type") == "init" and "nhsNumber" in data:
                        with tracer.start_as_current_span("WebSocket.init_session"):
                            nhs_number = data["nhsNumber"]
                            print(f"🔄 Initializing session for NHS: {nhs_number}")

                            user = users_collection.find_one(
                                {"nhs number.number": nhs_number}
                            )

                            if user:
                                user_context = {
                                    "name": user["name"],
                                    "nhs_number": nhs_number,
                                    "age": user["nhs number"]["age"],
                                    "gender": user["nhs number"]["gender"],
                                    "date_of_treatment": user["nhs number"][
                                        "date_of_treatment"
                                    ],
                                    "health_issue": user["nhs number"]["health_issue"],
                                }

                                # Create a new session if one doesn't exist
                                if nhs_number not in user_sessions:
                                    user_sessions[nhs_number] = UserSession(
                                        user_context
                                    )

                                current_session = user_sessions[nhs_number]

                                # Send initial greeting
                                initial_greeting = (
                                    f"Hello {user['name']}! I'm here to help collect your feedback about your recent healthcare experience. "
                                    f"How are you feeling about your {user['nhs number']['health_issue']} treatment on {user['nhs number']['date_of_treatment']}?"
                                )
                                await websocket.send_text(initial_greeting)
                                print(f"🤖 Sent initial greeting: {initial_greeting}")
                            else:
                                await websocket.send_text("❌ NHS number not found.")
                            continue

                    # Handle request to start a new chat (reset conversation)
                    elif data.get("type") == "new_chat":
                        with tracer.start_as_current_span("WebSocket.new_chat"):
                            if current_session:
                                await current_session.reset_conversation()
                                await websocket.send_text(
                                    f"Hi {current_session.user_context['name']}! Let's start fresh. "
                                    "How was your recent healthcare experience?"
                                )
                                print(
                                    f"🤖 Sent new chat greeting for {current_session.user_context['name']}"
                                )
                            else:
                                await websocket.send_text(
                                    "❌ Please initialize session first by sending an 'init' message."
                                )
                            continue

                    # Process regular user messages
                    elif data.get("type") == "message":
                        with tracer.start_as_current_span("WebSocket.process_message"):
                            message_content = data.get("content", "")

                            if not current_session:
                                await websocket.send_text(
                                    "❌ Please initialize your session first by providing your NHS number via an 'init' message."
                                )
                                continue

                            if not message_content.strip():
                                await websocket.send_text(
                                    "I didn't receive any message. Could you please try again?"
                                )
                                continue

                            print(
                                f"💬 Processing message: '{message_content}' for NHS: {current_session.user_context['nhs_number']}"
                            )

                            # Process the message through the async session
                            response = await current_session.process_message(
                                message_content
                            )
                            print(f"🤖 Response: {response}")

                            await websocket.send_text(response)

                except json.JSONDecodeError:
                    with tracer.start_as_current_span("WebSocket.process_raw"):
                        # Handle raw text messages (non-JSON)
                        if current_session:
                            print(
                                f"💬 Processing raw message: '{data_raw}' for NHS: {current_session.user_context['nhs_number']}"
                            )
                            response = await current_session.process_message(data_raw)
                            await websocket.send_text(response)
                        else:
                            await websocket.send_text(
                                "❌ Please initialize your session first by providing your NHS number in JSON format (e.g., {'type': 'init', 'nhsNumber': '123...'})."
                            )

                except Exception as e:
                    # Generic error handling for unexpected issues
                    print(f"❌ Error processing message in WebSocket: {str(e)}")
                    await websocket.send_text(
                        "I encountered an error. Please try again."
                    )

    except Exception as e:
        # Error handling for WebSocket connection issues
        print(f"❌ WebSocket connection error: {str(e)}")
    finally:
        # Cleanup when WebSocket connection is closed
        print("🔌 WebSocket connection closed")
        if current_session:
            try:
                await current_session.cleanup()
            except Exception as e:
                print(f"Error during session cleanup: {str(e)}")


# Cleanup handler for application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all user sessions on application shutdown"""
    print("🔄 Cleaning up user sessions...")
    cleanup_tasks = []

    for nhs_number, session in user_sessions.items():
        try:
            cleanup_tasks.append(session.cleanup())
        except Exception as e:
            print(f"Error creating cleanup task for {nhs_number}: {str(e)}")

    if cleanup_tasks:
        try:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    print("✅ Cleanup completed")
