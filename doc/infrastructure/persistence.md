# Persistence Adapters

Persistence adapters (`src/infrastructure/persistence/`) implement data saving and retrieval logic.

## SQL Adapter (`sql.py`)
Uses SQLAlchemy to interact with relational databases (PostgreSQL, MySQL, SQLite).
*   Maps application models to SQL tables.
*   Manages transactions.

## Redis Adapter (`redis.py`)
Uses Redis for caching or fast key-value storage.

## FileSystem Adapter (`fs.py`)
Saves data to local files (useful for development or simple configurations).

## Configuration
The choice of adapter to use is made in the `pyproject.toml` file.

```toml
[persistence.session]
adapter = "sql"
# ... specific SQL configuration ...
```
