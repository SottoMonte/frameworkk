# Persistence Adapters

Gli adattatori di persistenza (`src/infrastructure/persistence/`) implementano le logiche di salvataggio e recupero dati.

## SQL Adapter (`sql.py`)
Utilizza SQLAlchemy per interagire con database relazionali (PostgreSQL, MySQL, SQLite).
*   Mappa i modelli dell'applicazione su tabelle SQL.
*   Gestisce le transazioni.

## Redis Adapter (`redis.py`)
Utilizza Redis per caching o storage veloce key-value.

## FileSystem Adapter (`fs.py`)
Salva i dati su file locali (utile per sviluppo o configurazioni semplici).

## Configurazione
La scelta dell'adapter da usare viene fatta nel file `pyproject.toml`.

```toml
[persistence.session]
adapter = "sql"
# ... configurazione specifica SQL ...
```
