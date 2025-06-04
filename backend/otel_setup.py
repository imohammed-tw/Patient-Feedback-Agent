# otel_setup.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


def setup_otel(app):
    # Use the default tracer provider to avoid Logfire conflicts
    tracer_provider = trace.get_tracer_provider()

    # Add Console exporter for local tracing
    console_exporter = ConsoleSpanExporter()
    processor = BatchSpanProcessor(console_exporter)
    tracer_provider.add_span_processor(processor)

    # Instrument FastAPI and outgoing HTTP requests
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()


# # otel_setup.py
# from opentelemetry import trace
# from opentelemetry.sdk.resources import Resource
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor
# from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
# from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
# from opentelemetry.instrumentation.requests import RequestsInstrumentor


# def setup_otel(app):
#     trace.set_tracer_provider(
#         TracerProvider(
#             resource=Resource.create(
#                 {
#                     "service.name": "patient-feedback-agent",
#                 }
#             )
#         )
#     )
#     tracer_provider = trace.get_tracer_provider()

#     otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
#     span_processor = BatchSpanProcessor(otlp_exporter)
#     tracer_provider.add_span_processor(span_processor)

#     # Instrument FastAPI and HTTP requests
#     FastAPIInstrumentor.instrument_app(app)
#     RequestsInstrumentor().instrument()
