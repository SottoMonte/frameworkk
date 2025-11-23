# Presentation Adapters

Presentation adapters (`src/infrastructure/presentation/`) manage the interface towards the outside world. They are the entry point for requests.

## Web Adapter
Exposes the application via HTTP (e.g., REST API or HTML).
*   Receives the HTTP request.
*   Extracts parameters.
*   Calls the framework's `Executor`.
*   Formats the response (JSON, HTML) and sends it to the client.

## CLI Adapter
Allows using the application from the command line.

## WebSocket Adapter
Manages real-time connections.
