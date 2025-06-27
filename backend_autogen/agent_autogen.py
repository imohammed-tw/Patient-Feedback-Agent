import asyncio
import json
from dataclasses import dataclass
from typing import List, Dict, Any
from dotenv import load_dotenv
import os

# Import AutoGen Core components
from autogen_core import (
    AgentId,
    FunctionCall,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    message_handler,
)
from autogen_core.models import (
    ChatCompletionClient,
    LLMMessage,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    FunctionExecutionResultMessage,
    FunctionExecutionResult,
)
from autogen_core.tools import FunctionTool, Tool
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Import all tools from your tools.py file
from tools import (
    quick_sentiment_check,
    categorize_feedback,
    save_feedback_to_database,
    find_common_issues,
    ask_for_feedback_comments,
    start_feedback_rating_prompt,
)

# Enhanced OpenTelemetry Tracing Setup
from tracing_config import setup_enhanced_tracing, get_tracing_config

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Setup enhanced tracing
tracing_config = setup_enhanced_tracing()
tracer = tracing_config.tracer


@dataclass
class FeedbackMessage:
    """Message class for feedback agent communication"""

    content: str


class FeedbackAgent(RoutedAgent):
    """
    Tool-equipped patient feedback agent using RoutedAgent and OpenAIChatCompletionClient.
    Handles complete patient feedback collection workflow with direct tool execution.
    """

    def __init__(
        self,
        model_client: ChatCompletionClient,
        tools: List[Tool],
        personal_context: str = "",
    ):
        super().__init__("Patient Feedback Collection Agent")
        self.personal_context = personal_context
        self.model_client = model_client
        self.tools = tools

        # Session state to track collected information
        self.session_state = {
            "patient_name": "",
            "nhs_number": "",
            "satisfaction_rating": None,
            "comments": None,
            "category": None,
            "feedback_saved": False,
            "sentiment_checked": False,
        }

        # Conversation history to maintain context
        self.conversation_history: List[LLMMessage] = []

        # Extract personal context
        self._extract_personal_context()

        # Build system message with workflow
        self._system_messages = [SystemMessage(content=self._build_system_message())]

    def _extract_personal_context(self):
        """Extract patient information from personal context string"""
        if "Name: " in self.personal_context:
            self.session_state["patient_name"] = (
                self.personal_context.split("Name: ")[1].split("\n")[0].strip()
            )
        if "NHS Number: " in self.personal_context:
            self.session_state["nhs_number"] = (
                self.personal_context.split("NHS Number: ")[1].split("\n")[0].strip()
            )

    def _build_system_message(self) -> str:
        """Build comprehensive system message for the feedback agent"""
        patient_name = self.session_state.get("patient_name", "UNKNOWN_PATIENT")
        nhs_number = self.session_state.get("nhs_number", "UNKNOWN_NHS")

        return f"""
You are a healthcare feedback assistant. Your goal is to collect comprehensive patient feedback following this **EXACT, STRICTLY SEQUENTIAL workflow**. Always be empathetic, professional, and concise.

**Patient Context for Saving Data:**
- Patient's Name: {patient_name} (USE THIS EXACT VALUE FOR `name` PARAMETER IN `save_feedback_to_database`)
- Patient's NHS Number: {nhs_number} (USE THIS EXACT VALUE FOR `nhs_number` PARAMETER IN `save_feedback_to_database`)

**Workflow Steps - ADHERE TO THIS ORDER RIGOROUSLY:**

1. **GREETING & INITIAL INQUIRY (First Interaction Only)**:
   *Action*: Start by greeting the user personally and ask about their healthcare experience.

2. **HANDLING SIMPLE GREETINGS/ACKNOWLEDGMENTS (NO TOOLS HERE)**:
   *Condition*: If the user's message is a simple greeting (e.g., "hello", "hi", "ok", "thanks") or non-descriptive acknowledgment.
   *Action*: **DO NOT CALL ANY TOOLS**. Simply respond: "Hi {patient_name}! Please feel free to share any feedback you have about your recent healthcare experience. Every detail helps us improve."

3. **SENTIMENT ANALYSIS (Tool: `quick_sentiment_check`)**:
   *Condition*: When the user provides descriptive feedback comments (more than simple greetings).
   *Action*: Immediately use the `quick_sentiment_check` tool with the user's comments.
   *Response*: Respond empathetically based on sentiment results.

4. **RATING REQUEST (Tool: `start_feedback_rating_prompt`)**:
   *Condition*: After sentiment analysis, if sentiment is negative or neutral.
   *Action*: Use `start_feedback_rating_prompt` tool with patient name.
   *Response*: Ask for 1-5 satisfaction rating.

5. **DETAILED FEEDBACK PROMPT (Tool: `ask_for_feedback_comments`)**:
   *Condition*: When user provides a numeric rating (1-5). Look for SINGLE NUMBERS in user messages.
   *Action*: Use `ask_for_feedback_comments` tool with the exact numeric rating.
   *Response*: Prompt for detailed comments based on rating.
   *IMPORTANT*: If user says just "3" or "2" or any single digit 1-5, treat this as their satisfaction rating.

6. **CATEGORIZATION (Tool: `categorize_feedback`)**:
   *Condition*: When user provides detailed comments and you have a rating.
   *Action*: Use `categorize_feedback` tool with the detailed comments.
   *Response*: Acknowledge receiving detailed feedback.

7. **SAVE FEEDBACK (Tool: `save_feedback_to_database`)**:
   *Condition*: After categorization when all data is collected.
   *Action*: Use `save_feedback_to_database` with: name="{patient_name}", nhs_number="{nhs_number}", rating=user_rating, comments=user_comments, category=categorized_result.
   *Response*: Confirm feedback has been saved.

8. **SHOW INSIGHTS (Tool: `find_common_issues`)**:
   *Condition*: After successfully saving feedback.
   *Action*: Use `find_common_issues` tool to show recurring issues.
   *Response*: Present common issues to user.

9. **CLOSE CONVERSATION**:
   *Action*: Thank the user and confirm their feedback helps improve healthcare.

**General Rules:**
- Follow steps sequentially, don't skip or reorder
- Only call tools when ALL required parameters are available
- If information is missing, ask the user for it clearly
- Remember information from previous exchanges
- End conversation only after completing all 9 steps
"""

    @message_handler
    async def handle_feedback_message(
        self, message: FeedbackMessage, ctx: MessageContext
    ) -> FeedbackMessage:
        """Handle incoming feedback messages with tool execution and conversation state"""
        with tracing_config.trace_conversation(
            self.session_state.get("nhs_number", "unknown")
        ):
            with tracer.start_as_current_span("FeedbackAgent.handle_message") as span:
                span.set_attribute(
                    "patient.name", self.session_state.get("patient_name", "unknown")
                )
                span.set_attribute(
                    "message.content", message.content[:100]
                )  # First 100 chars
                span.set_attribute(
                    "conversation.turn", len(self.conversation_history) // 2 + 1
                )

                try:
                    # Add current user message to conversation history
                    self.conversation_history.append(
                        UserMessage(content=message.content, source="user")
                    )

                    # Create session with system message and full conversation history
                    session: List[LLMMessage] = (
                        self._system_messages + self.conversation_history
                    )

                    # Trace LLM call with enhanced metrics
                    with tracing_config.trace_llm_call(
                        "gpt-4o-mini", len(session)
                    ) as llm_tracer:
                        create_result = await self.model_client.create(
                            messages=session,
                            tools=self.tools,
                            cancellation_token=ctx.cancellation_token,
                        )

                        # Record token usage if available
                        if hasattr(create_result, "usage"):
                            usage = create_result.usage
                            llm_tracer.record_token_usage(
                                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                                completion_tokens=getattr(
                                    usage, "completion_tokens", 0
                                ),
                                total_tokens=getattr(usage, "total_tokens", 0),
                            )

                    # If no tool calls, return direct response
                    if isinstance(create_result.content, str):
                        # Add assistant response to conversation history
                        assistant_response = AssistantMessage(
                            content=create_result.content, source="assistant"
                        )
                        self.conversation_history.append(assistant_response)
                        span.set_attribute("response.type", "direct")
                        span.set_attribute(
                            "response.length", len(create_result.content)
                        )
                        return FeedbackMessage(content=create_result.content)

                    # Handle tool calls
                    assert isinstance(create_result.content, list) and all(
                        isinstance(call, FunctionCall) for call in create_result.content
                    )

                    span.set_attribute("response.type", "tool_calls")
                    span.set_attribute("tool_calls.count", len(create_result.content))

                    # Log tool calls
                    for i, call in enumerate(create_result.content):
                        span.set_attribute(f"tool_call.{i}.name", call.name)

                    # Add model response to session and conversation history
                    assistant_message = AssistantMessage(
                        content=create_result.content, source="assistant"
                    )
                    session.append(assistant_message)
                    self.conversation_history.append(assistant_message)

                    # Execute all tool calls with tracing
                    tool_results = []
                    for call in create_result.content:
                        with tracing_config.trace_tool_execution(call.name):
                            result = await self._execute_tool_call(
                                call, ctx.cancellation_token
                            )
                            tool_results.append(result)

                    # Add tool results to session
                    tool_message = FunctionExecutionResultMessage(content=tool_results)
                    session.append(tool_message)
                    self.conversation_history.append(tool_message)

                    # Get final response after tool execution with tracing
                    with tracing_config.trace_llm_call(
                        "gpt-4o-mini", len(session)
                    ) as final_llm_tracer:
                        final_result = await self.model_client.create(
                            messages=session,
                            cancellation_token=ctx.cancellation_token,
                        )

                        # Record token usage for final call
                        if hasattr(final_result, "usage"):
                            usage = final_result.usage
                            final_llm_tracer.record_token_usage(
                                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                                completion_tokens=getattr(
                                    usage, "completion_tokens", 0
                                ),
                                total_tokens=getattr(usage, "total_tokens", 0),
                            )

                    assert isinstance(final_result.content, str)

                    # Add final response to conversation history
                    final_assistant_message = AssistantMessage(
                        content=final_result.content, source="assistant"
                    )
                    self.conversation_history.append(final_assistant_message)

                    span.set_attribute(
                        "final_response.length", len(final_result.content)
                    )
                    span.set_attribute(
                        "conversation.total_messages", len(self.conversation_history)
                    )

                    return FeedbackMessage(content=final_result.content)

                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))

                    # Record error metric
                    tracing_config.record_error(type(e).__name__, "feedback_agent")

                    print(f"Error in FeedbackAgent.handle_feedback_message: {str(e)}")
                    self.reset()
                    return FeedbackMessage(
                        content=f"An error occurred: {str(e)}. I have reset our conversation. How was your recent healthcare experience?"
                    )

    async def _execute_tool_call(
        self, call: FunctionCall, cancellation_token
    ) -> FunctionExecutionResult:
        """Execute a single tool call and return the result"""
        with tracer.start_as_current_span("FeedbackAgent.execute_tool"):
            # Find the tool by name
            tool = next((tool for tool in self.tools if tool.name == call.name), None)
            if tool is None:
                return FunctionExecutionResult(
                    call_id=call.id,
                    content=f"Tool {call.name} not found",
                    is_error=True,
                    name=call.name,
                )

            try:
                # Parse arguments and execute tool
                arguments = json.loads(call.arguments)
                result = await tool.run_json(arguments, cancellation_token)

                return FunctionExecutionResult(
                    call_id=call.id,
                    content=tool.return_value_as_string(result),
                    is_error=False,
                    name=tool.name,
                )
            except Exception as e:
                return FunctionExecutionResult(
                    call_id=call.id, content=str(e), is_error=True, name=tool.name
                )

    def reset(self):
        """Reset session state for a fresh conversation"""
        self.session_state = {
            "patient_name": "",
            "nhs_number": "",
            "satisfaction_rating": None,
            "comments": None,
            "category": None,
            "feedback_saved": False,
            "sentiment_checked": False,
        }
        # Clear conversation history
        self.conversation_history = []
        self._extract_personal_context()


class FeedbackSession:
    """
    Manages a patient feedback session using the new Tool-Equipped Agent approach.
    Handles runtime creation and agent lifecycle.
    """

    def __init__(self, personal_context: str = ""):
        self.personal_context = personal_context
        self.runtime = None
        self.agent_id = None
        self.model_client = None
        self.feedback_agent = None
        self._tools = self._create_tools()

    def _create_tools(self) -> List[Tool]:
        """Create FunctionTool objects from our existing Python functions"""
        tools = [
            FunctionTool(
                quick_sentiment_check,
                description="Analyze the sentiment of feedback text. Input: feedback_text (str). Returns sentiment analysis.",
            ),
            FunctionTool(
                start_feedback_rating_prompt,
                description="Generate a standardized prompt for satisfaction rating. Input: patient_name (str). Returns rating request prompt.",
            ),
            FunctionTool(
                ask_for_feedback_comments,
                description="Generate follow-up questions based on satisfaction rating. Input: rating (int). Returns detailed comment prompt.",
            ),
            FunctionTool(
                categorize_feedback,
                description="Categorize feedback into predefined categories. Input: comments (str). Returns category classification.",
            ),
            FunctionTool(
                save_feedback_to_database,
                description="Save patient feedback to database. Input: name (str), nhs_number (str), rating (int), comments (str), category (str). Returns save confirmation.",
            ),
            FunctionTool(
                find_common_issues,
                description="Find recurring issues from all feedback. No input required. Returns common issues summary.",
            ),
        ]
        return tools

    async def initialize(self):
        """Initialize the runtime and register the agent"""
        with tracer.start_as_current_span("FeedbackSession.initialize"):
            # Create model client
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o-mini", api_key=OPENAI_API_KEY
            )

            # Create runtime
            self.runtime = SingleThreadedAgentRuntime()

            # Register the feedback agent
            await FeedbackAgent.register(
                self.runtime,
                "feedback_agent",
                lambda: FeedbackAgent(
                    model_client=self.model_client,
                    tools=self._tools,
                    personal_context=self.personal_context,
                ),
            )

            self.agent_id = AgentId("feedback_agent", "default")

            # Start the runtime
            self.runtime.start()

    async def process_message(self, message: str) -> str:
        """Process a user message and return the agent's response"""
        with tracer.start_as_current_span("FeedbackSession.process_message"):
            try:
                if not self.runtime:
                    await self.initialize()

                # Send message to agent
                response = await self.runtime.send_message(
                    FeedbackMessage(content=message), self.agent_id
                )

                return response.content

            except Exception as e:
                print(f"Error in FeedbackSession.process_message: {str(e)}")
                await self.reset()
                return f"An error occurred: {str(e)}. I have reset our conversation. How was your recent healthcare experience?"

    async def reset(self):
        """Reset the session for a fresh conversation"""
        with tracer.start_as_current_span("FeedbackSession.reset"):
            try:
                if self.runtime:
                    await self.runtime.stop()
                if self.model_client:
                    await self.model_client.close()

                # Reinitialize
                await self.initialize()

            except Exception as e:
                print(f"Error resetting FeedbackSession: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.runtime:
                await self.runtime.stop()
            if self.model_client:
                await self.model_client.close()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")


# Compatibility functions for main.py
def create_feedback_assistant(personal_context: str = "") -> FeedbackSession:
    """Create a new feedback session with the given context"""
    return FeedbackSession(personal_context)


async def process_feedback(user_message: str) -> str:
    """Process a single feedback message (for compatibility)"""
    session = FeedbackSession()
    try:
        response = await session.process_message(user_message)
        return response
    finally:
        await session.cleanup()
