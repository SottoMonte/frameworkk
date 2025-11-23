# Actions

`Action`s represent system use cases. Each file in `src/application/action/` corresponds to a specific operation the user can request.

## Structure
An Action is typically an asynchronous function or a class with an `execute` method.

```python
# src/application/action/create_user.py

async def create_user(repository, mailer, **kwargs):
    """
    Creates a new user.
    
    Args:
        repository: Persistence port (injected).
        mailer: Email sending port (injected).
        kwargs: Input data (e.g., username, email).
    """
    user_data = kwargs.get('data')
    
    # 1. Validation
    if not user_data.get('email'):
        return {"error": "Email required"}
        
    # 2. Business Logic
    user = await repository.save(user_data)
    
    # 3. Side Effects (via ports)
    await mailer.send_welcome(user['email'])
    
    return user
```

## Best Practices
*   **Explicit Names**: Use verbs in the filename (e.g., `save.py`, `delete.py`, `calculate_tax.py`).
*   **Dependency Injection**: Never instantiate databases or services directly. Expect them to be passed as arguments.
*   **Input/Output**: Receive dictionaries or simple DTOs, return dictionaries or simple DTOs.
