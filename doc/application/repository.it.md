# Repositories

I `Repository` in `src/application/repository/` sono **interfacce** (o contratti astratti) che definiscono come l'applicazione accede ai dati.

## Scopo
Disaccoppiare la logica di business dalla tecnologia di persistenza. L'applicazione sa *che* può salvare un utente, ma non sa *se* finisce su MySQL, Mongo o un file di testo.

## Esempio di Definizione

```python
# src/application/repository/users.py

class UserRepository:
    async def save(self, user: dict) -> dict:
        """Salva o aggiorna un utente."""
        raise NotImplementedError

    async def find_by_id(self, user_id: str) -> dict:
        """Trova un utente per ID."""
        raise NotImplementedError
```

## Implementazione
L'implementazione concreta di queste interfacce avviene nel layer `infrastructure` (es. `src/infrastructure/persistence/sql.py`).
