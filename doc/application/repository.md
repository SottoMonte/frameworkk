# Repositories

`Repository`s in `src/application/repository/` are **interfaces** (or abstract contracts) that define how the application accesses data.

## Purpose
Decouple business logic from persistence technology. The application knows *that* it can save a user, but it doesn't know *if* it ends up in MySQL, Mongo, or a text file.

## Definition Example

```python
# src/application/repository/users.py

class UserRepository:
    async def save(self, user: dict) -> dict:
        """Saves or updates a user."""
        raise NotImplementedError

    async def find_by_id(self, user_id: str) -> dict:
        """Finds a user by ID."""
        raise NotImplementedError
```

## Implementation
The concrete implementation of these interfaces happens in the `infrastructure` layer (e.g., `src/infrastructure/persistence/sql.py`).
