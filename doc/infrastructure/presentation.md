# Presentation Adapters

Gli adattatori di presentazione (`src/infrastructure/presentation/`) gestiscono l'interfaccia verso l'esterno. Sono il punto di ingresso delle richieste.

## Web Adapter
Espone l'applicazione via HTTP (es. REST API o HTML).
*   Riceve la richiesta HTTP.
*   Estrae i parametri.
*   Chiama l'`Executor` del framework.
*   Formatta la risposta (JSON, HTML) e la invia al client.

## CLI Adapter
Permette di usare l'applicazione da riga di comando.

## WebSocket Adapter
Gestisce connessioni in tempo reale.
