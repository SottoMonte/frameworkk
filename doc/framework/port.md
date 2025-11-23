# Ports

`Port`s (`src/framework/port/`) are abstract interfaces. They define the services the application needs to function.

## Example: Persistence Port

```python
# src/framework/port/persistence.py

class Port:
    def save(self, data):
        pass
    
    def delete(self, id):
        pass
```

## Why use Ports?
*   **Testability**: You can create "fake" adapters (Mock) for tests that implement the port without using a real database.
*   **Flexibility**: You can change the real implementation (e.g., from MySQL to PostgreSQL) without touching a line of code in the application.
