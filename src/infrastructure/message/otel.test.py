import asyncio
from infrastructure.message.otel import adapter

class Testadapter:
    async def test_start_span(self):
        otel = adapter(config={'project': 'TestProject'})
        with otel.start_span("test_span") as span:
            span.set_attribute("key", "value")
        return True

exports = {
    'adapter': 'adapter'
}
