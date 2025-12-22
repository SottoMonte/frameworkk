import sys
import logging

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        SimpleSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

class adapter:
    """
    OpenTelemetry adapter for the SottoMonte framework.
    Provides tracing capabilities with graceful degradation if OTel is not installed.
    """
    def __init__(self, config=None):
        self.config = config or {}
        self.service_name = self.config.get('project', 'sottomonte-app')
        self.tracer = None
        
        if OTEL_AVAILABLE:
            self._setup_otel()
        else:
            logging.warning("⚠️ OpenTelemetry non installato. Tracing disabilitato (Mock attivo).")

    def _setup_otel(self):
        resource = Resource(attributes={
            "service.name": self.service_name
        })
        provider = TracerProvider(resource=resource)
        processor = SimpleSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(__name__)
        logging.info("⭐ OpenTelemetry Core Initialized (Console Exporter active)")

    def start_span(self, name, attributes=None):
        if self.tracer:
            return self.tracer.start_as_current_span(name, attributes=attributes)
        return MockSpan(name)

class MockSpan:
    """A minimal mock span for when OTel is not available."""
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def set_attribute(self, key, value):
        pass
    def add_event(self, name, attributes=None):
        pass
