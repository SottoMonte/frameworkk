# Practical Guides (How-To)

## How to create a new Action

1.  Create a new file in `src/application/action/`.
2.  The filename should reflect the action (e.g., `create_user.py`).
3.  Define a function or class that implements the logic.
4.  Example:
    ```python
    async def create_user(repository, **kwargs):
        user_data = kwargs.get('data')
        # Validation...
        return await repository.save(user_data)
    ```

## How to add a new Model

1.  Add a JSON or Python file in `src/application/model/`.
2.  Define the data structure.
    ```json
    {
        "name": "user",
        "fields": {
            "username": "string",
            "email": "string"
        }
    }
    ```

## How to implement a new Adapter

If you want to support a new technology (e.g., a new database):

1.  Identify the corresponding `Port` in `src/framework/port/` (e.g., `persistence.py`).
2.  Create a new file in `src/infrastructure/persistence/` (e.g., `mongo.py`).
3.  Implement the class or functions required by the Port.
4.  Update `pyproject.toml` to use the new adapter.

## How to Debug

1.  Ensure logs are configured to `debug` in `pyproject.toml`.
2.  Check the console output or the configured log file.
3.  Use `print()` or a standard Python debugger if necessary, but remember the code is asynchronous (`async/await`).
