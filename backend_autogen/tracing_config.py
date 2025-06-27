# tracing_config.py - Simple Console + File Tracing
import os
import time
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

# Only core OpenTelemetry imports (minimal)
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Configure logging for better visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileTraceExporter:
    """Custom file exporter for detailed trace logging"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize the log file with header
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"PATIENT FEEDBACK AGENT TRACE LOG\n")
            f.write(f"Session started: {datetime.now().isoformat()}\n")
            f.write(f"{'='*80}\n\n")

    def export(self, span_data):
        """Export span data to file"""
        try:
            timestamp = datetime.now().isoformat()
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {span_data}\n")
        except Exception as e:
            logger.error(f"Failed to write trace to file: {e}")


class SimpleTracingConfig:
    """Simple tracing configuration focused on detailed console + file output"""

    def __init__(self, service_name="PatientFeedbackAgent", service_version="1.0.0"):
        self.service_name = service_name
        self.service_version = service_version
        self.tracer = None

        # Simple counters for metrics
        self.metrics = {
            "llm_calls": 0,
            "tool_executions": 0,
            "total_tokens": 0,
            "total_conversations": 0,
            "errors": 0,
        }

        # File exporters
        self.trace_file_exporter = None
        self.metrics_file = None

        self.setup_tracing()
        self.setup_file_exporters()

    def setup_tracing(self):
        """Setup simple console tracing"""
        try:
            # Create resource with service information
            resource = Resource.create(
                {
                    "service.name": self.service_name,
                    "service.version": self.service_version,
                    "environment": os.getenv("ENVIRONMENT", "development"),
                }
            )

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Add console exporter
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            provider.add_span_processor(console_processor)

            # Set global tracer provider
            trace.set_tracer_provider(provider)
            self.tracer = trace.get_tracer(self.service_name, self.service_version)

            logger.info("✅ Simple console tracing enabled")

        except Exception as e:
            logger.error(f"❌ Failed to setup tracing: {e}")
            # Create a dummy tracer that does nothing
            self.tracer = DummyTracer()

    def setup_file_exporters(self):
        """Setup file exporters for traces and metrics"""
        try:
            # Create logs directory
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)

            # Setup trace file exporter
            trace_file = logs_dir / f"traces_{datetime.now().strftime('%Y%m%d')}.log"
            self.trace_file_exporter = FileTraceExporter(trace_file)

            # Setup metrics file path
            self.metrics_file = (
                logs_dir / f"metrics_{datetime.now().strftime('%Y%m%d')}.json"
            )

            logger.info(f"✅ File exporters enabled: {logs_dir}")

        except Exception as e:
            logger.error(f"❌ Failed to setup file exporters: {e}")

    def trace_llm_call(self, model_name: str, messages_count: int):
        """Context manager for tracing LLM calls"""
        return LLMCallTracer(
            self.tracer,
            self.metrics,
            self.trace_file_exporter,
            model_name,
            messages_count,
        )

    def trace_tool_execution(self, tool_name: str):
        """Context manager for tracing tool executions"""
        return ToolExecutionTracer(
            self.tracer, self.metrics, self.trace_file_exporter, tool_name
        )

    def trace_conversation(self, user_id: str):
        """Context manager for tracing entire conversations"""
        return ConversationTracer(
            self.tracer, self.metrics, self.trace_file_exporter, user_id
        )

    def record_error(self, error_type: str, component: str):
        """Record error with simple logging"""
        self.metrics["errors"] += 1
        error_msg = f"🚨 ERROR [{component}]: {error_type} | Total errors: {self.metrics['errors']}"
        logger.error(error_msg)

        # Log error to file
        if self.trace_file_exporter:
            self.trace_file_exporter.export(f"ERROR: {error_msg}")

        # Update metrics file
        self.save_metrics_to_file()

    def save_metrics_to_file(self):
        """Save current metrics to JSON file"""
        if not self.metrics_file:
            return

        try:
            metrics_data = {
                "timestamp": datetime.now().isoformat(),
                "service": self.service_name,
                "metrics": self.metrics.copy(),
                "session_info": {
                    "avg_tokens_per_call": (
                        self.metrics["total_tokens"] / self.metrics["llm_calls"]
                        if self.metrics["llm_calls"] > 0
                        else 0
                    ),
                    "tools_per_conversation": (
                        self.metrics["tool_executions"]
                        / self.metrics["total_conversations"]
                        if self.metrics["total_conversations"] > 0
                        else 0
                    ),
                },
            }

            # Read existing data
            existing_data = []
            if self.metrics_file.exists():
                try:
                    with open(self.metrics_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []

            # Append new data
            existing_data.append(metrics_data)

            # Keep only last 100 entries to prevent file from growing too large
            if len(existing_data) > 100:
                existing_data = existing_data[-100:]

            # Write back to file
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save metrics to file: {e}")

    def print_metrics_summary(self):
        """Print current metrics summary"""
        print("\n" + "=" * 60)
        print("📊 FEEDBACK AGENT METRICS SUMMARY")
        print("=" * 60)
        print(f"🤖 LLM Calls: {self.metrics['llm_calls']}")
        print(f"🛠️  Tool Executions: {self.metrics['tool_executions']}")
        print(f"🎯 Total Tokens Used: {self.metrics['total_tokens']:,}")
        print(f"💬 Conversations: {self.metrics['total_conversations']}")
        print(f"🚨 Errors: {self.metrics['errors']}")
        if self.metrics["llm_calls"] > 0:
            avg_tokens = self.metrics["total_tokens"] / self.metrics["llm_calls"]
            print(f"📈 Average Tokens per LLM Call: {avg_tokens:.1f}")
        print("=" * 60 + "\n")

        # Save metrics to file
        self.save_metrics_to_file()


class DummyTracer:
    """Dummy tracer that does nothing if setup fails"""

    def start_span(self, *args, **kwargs):
        return DummySpan()


class DummySpan:
    """Dummy span that does nothing"""

    def set_attribute(self, *args, **kwargs):
        pass

    def set_status(self, *args, **kwargs):
        pass

    def end(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class LLMCallTracer:
    """Simple context manager for tracing LLM API calls"""

    def __init__(self, tracer, metrics, file_exporter, model_name, messages_count):
        self.tracer = tracer
        self.metrics = metrics
        self.file_exporter = file_exporter
        self.model_name = model_name
        self.messages_count = messages_count
        self.span = None
        self.start_time = None
        self.call_id = f"llm_{int(time.time()*1000)}"

    def __enter__(self):
        self.start_time = time.time()
        self.metrics["llm_calls"] += 1

        console_msg = f"\n🚀 LLM CALL STARTED [{self.call_id}]"
        print(console_msg)
        print(f"   ├── Model: {self.model_name}")
        print(f"   ├── Messages in context: {self.messages_count}")
        print(f"   └── Started at: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

        # Log to file
        if self.file_exporter:
            file_msg = f"LLM_CALL_START | ID: {self.call_id} | Model: {self.model_name} | Messages: {self.messages_count}"
            self.file_exporter.export(file_msg)

        if self.tracer:
            try:
                self.span = self.tracer.start_span(
                    "llm_api_call",
                    attributes={
                        "llm.vendor": "openai",
                        "llm.model": self.model_name,
                        "llm.messages.count": self.messages_count,
                        "call.id": self.call_id,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to start LLM span: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        status = "❌ FAILED" if exc_type else "✅ SUCCESS"
        console_msg = f"\n{status} LLM CALL COMPLETED [{self.call_id}]"
        print(console_msg)
        print(f"   ├── Duration: {duration:.3f}s")
        print(f"   ├── Status: {'Error' if exc_type else 'Success'}")
        if exc_type:
            print(f"   ├── Error: {exc_type.__name__}: {exc_val}")
        print(f"   └── Total LLM calls: {self.metrics['llm_calls']}")

        # Log to file
        if self.file_exporter:
            status_text = "FAILED" if exc_type else "SUCCESS"
            file_msg = f"LLM_CALL_END | ID: {self.call_id} | Status: {status_text} | Duration: {duration:.3f}s"
            if exc_type:
                file_msg += f" | Error: {exc_type.__name__}: {exc_val}"
            self.file_exporter.export(file_msg)

        if self.span:
            try:
                self.span.set_attribute("llm.duration_seconds", duration)
                if exc_type:
                    self.span.set_attribute("error", True)
                    self.span.set_attribute("error.type", exc_type.__name__)
                    self.span.set_attribute("error.message", str(exc_val))
                self.span.end()
            except Exception as e:
                logger.warning(f"Failed to end LLM span: {e}")

    def record_token_usage(
        self, prompt_tokens: int, completion_tokens: int, total_tokens: int
    ):
        """Record and display token usage"""
        self.metrics["total_tokens"] += total_tokens

        console_msg = f"\n💰 TOKEN USAGE [{self.call_id}]"
        print(console_msg)
        print(f"   ├── Prompt tokens: {prompt_tokens:,}")
        print(f"   ├── Completion tokens: {completion_tokens:,}")
        print(f"   ├── Total this call: {total_tokens:,}")
        print(f"   └── Grand total tokens: {self.metrics['total_tokens']:,}")

        # Log to file
        if self.file_exporter:
            file_msg = f"TOKEN_USAGE | ID: {self.call_id} | Prompt: {prompt_tokens} | Completion: {completion_tokens} | Total: {total_tokens} | Grand Total: {self.metrics['total_tokens']}"
            self.file_exporter.export(file_msg)

        if self.span:
            try:
                self.span.set_attribute("llm.usage.prompt_tokens", prompt_tokens)
                self.span.set_attribute(
                    "llm.usage.completion_tokens", completion_tokens
                )
                self.span.set_attribute("llm.usage.total_tokens", total_tokens)
            except Exception:
                pass


class ToolExecutionTracer:
    """Simple context manager for tracing tool executions"""

    def __init__(self, tracer, metrics, file_exporter, tool_name):
        self.tracer = tracer
        self.metrics = metrics
        self.file_exporter = file_exporter
        self.tool_name = tool_name
        self.span = None
        self.start_time = None
        self.execution_id = f"tool_{int(time.time()*1000)}"

    def __enter__(self):
        self.start_time = time.time()
        self.metrics["tool_executions"] += 1

        console_msg = f"\n🛠️  TOOL EXECUTION STARTED [{self.execution_id}]"
        print(console_msg)
        print(f"   ├── Tool: {self.tool_name}")
        print(f"   └── Started at: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

        # Log to file
        if self.file_exporter:
            file_msg = f"TOOL_START | ID: {self.execution_id} | Tool: {self.tool_name}"
            self.file_exporter.export(file_msg)

        if self.tracer:
            try:
                self.span = self.tracer.start_span(
                    f"tool_execution.{self.tool_name}",
                    attributes={
                        "tool.name": self.tool_name,
                        "execution.id": self.execution_id,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to start tool span: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        status = "❌ FAILED" if exc_type else "✅ SUCCESS"
        console_msg = f"\n{status} TOOL EXECUTION COMPLETED [{self.execution_id}]"
        print(console_msg)
        print(f"   ├── Tool: {self.tool_name}")
        print(f"   ├── Duration: {duration:.3f}s")
        print(f"   ├── Status: {'Error' if exc_type else 'Success'}")
        if exc_type:
            print(f"   ├── Error: {exc_type.__name__}: {exc_val}")
        print(f"   └── Total tool executions: {self.metrics['tool_executions']}")

        # Log to file
        if self.file_exporter:
            status_text = "FAILED" if exc_type else "SUCCESS"
            file_msg = f"TOOL_END | ID: {self.execution_id} | Tool: {self.tool_name} | Status: {status_text} | Duration: {duration:.3f}s"
            if exc_type:
                file_msg += f" | Error: {exc_type.__name__}: {exc_val}"
            self.file_exporter.export(file_msg)

        if self.span:
            try:
                self.span.set_attribute("tool.duration_seconds", duration)
                if exc_type:
                    self.span.set_attribute("error", True)
                    self.span.set_attribute("error.type", exc_type.__name__)
                self.span.end()
            except Exception:
                pass


class ConversationTracer:
    """Simple context manager for tracing entire conversations"""

    def __init__(self, tracer, metrics, file_exporter, user_id):
        self.tracer = tracer
        self.metrics = metrics
        self.file_exporter = file_exporter
        self.user_id = user_id
        self.span = None
        self.start_time = None
        self.conversation_id = f"conv_{int(time.time()*1000)}"

    def __enter__(self):
        self.start_time = time.time()
        self.metrics["total_conversations"] += 1

        console_msg = f"\n🎯 CONVERSATION STARTED [{self.conversation_id}]"
        print(console_msg)
        print(f"   ├── User: {self.user_id}")
        print(f"   └── Started at: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

        # Log to file
        if self.file_exporter:
            file_msg = f"CONVERSATION_START | ID: {self.conversation_id} | User: {self.user_id}"
            self.file_exporter.export(file_msg)

        if self.tracer:
            try:
                self.span = self.tracer.start_span(
                    "patient_conversation",
                    attributes={
                        "user.id": self.user_id,
                        "conversation.id": self.conversation_id,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to start conversation span: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        status = "❌ FAILED" if exc_type else "✅ COMPLETED"
        console_msg = f"\n{status} CONVERSATION [{self.conversation_id}]"
        print(console_msg)
        print(f"   ├── User: {self.user_id}")
        print(f"   ├── Duration: {duration:.1f}s")
        print(f"   ├── Status: {'Error' if exc_type else 'Success'}")
        if exc_type:
            print(f"   ├── Error: {exc_type.__name__}")
        print(f"   └── Total conversations: {self.metrics['total_conversations']}")

        # Log to file
        if self.file_exporter:
            status_text = "FAILED" if exc_type else "SUCCESS"
            file_msg = f"CONVERSATION_END | ID: {self.conversation_id} | User: {self.user_id} | Status: {status_text} | Duration: {duration:.1f}s"
            if exc_type:
                file_msg += f" | Error: {exc_type.__name__}"
            self.file_exporter.export(file_msg)

        if self.span:
            try:
                self.span.set_attribute("conversation.duration_seconds", duration)
                if exc_type:
                    self.span.set_attribute("error", True)
                    self.span.set_attribute("error.type", exc_type.__name__)
                self.span.end()
            except Exception:
                pass


# Global tracing instance
tracing_config: Optional[SimpleTracingConfig] = None


def get_tracing_config() -> SimpleTracingConfig:
    """Get or create the global tracing configuration"""
    global tracing_config
    if tracing_config is None:
        tracing_config = SimpleTracingConfig()
    return tracing_config


def setup_enhanced_tracing() -> SimpleTracingConfig:
    """Setup simple enhanced tracing - call this at application startup"""
    config = get_tracing_config()
    print("\n🎉 PATIENT FEEDBACK AGENT TRACING INITIALIZED")
    print("=" * 50)
    print("📊 Metrics will be displayed in real-time")
    print("🔍 Detailed traces shown for all operations")
    print("📁 Traces and metrics saved to logs/ directory")
    print("=" * 50 + "\n")
    return config
