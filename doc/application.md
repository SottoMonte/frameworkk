# Deep Dive Analysis: Application & Repository Layer

This section delves into the architecture of the `Application` and `Repository` layers of the framework, highlighting how they differ significantly from traditional patterns (such as MVC or Active Record).

## 1. The Application Layer

The `src/application` folder does not contain classic procedural business logic, but rather defines **rules, models, and interfaces** in a declarative way.

### Structure
*   **`model/`**: Defines the data structure (Schema).
*   **`repository/`**: Defines *how* and *where* to retrieve data, but does not *implement* the connection.
*   **`policy/`**: Configures system behavior (e.g., routing, permissions).

### Models (`src/application/model`)
Models are not Python classes (as in Django or SQLAlchemy), but **JSON** files. This suggests that the framework treats data as pure structures (dictionaries) rather than stateful objects.

**Example (`product.json`):**
```json
{
  "name": { "type": "string", "required": true },
  "price": { "type": "number", "required": true, "min": 0 }
}
```
*   **Advantage**: Extreme portability (the model is readable by any language/frontend).
*   **Function**: Acts as a validation contract (likely used by libraries like `cerberus` internal to the framework).

## 2. The Repository Layer

Here lies the main innovation. Instead of writing DAO (Data Access Object) classes or using an ORM, repositories are generated dynamically via a **Factory**.

### Declarative Definition
A repository is defined as a configuration passed to `factory.repository`.

**Example (`src/application/repository/products.py`):**
```python
repository = factory.repository(
    location = {'SUPABASE': ['products']},  # Data source
    model = product,                        # Validation schema
    mapper = {},                            # Field mapping (optional)
)
```
*   **`location`**: Tells the framework which **Adapter** to use (`SUPABASE`) and which resource to point to (`products` table).
*   **Agnosticism**: If tomorrow you want to move products to Redis, you only change `location` to `{'REDIS': ['products']}`. The rest of the app does not change.

### Complex Repositories (API as DB)
The `src/application/repository/repository.py` file shows that the "Repository" concept is abstracted to also include external APIs.

**Example (GitHub Repository):**
```python
repository = factory.repository(
    location = {'GITHUB': ["repos/{owner}/{name}"]},
    mapper = {
        'stars': {'GITHUB': 'stargazers_count'}, # Map API field -> Domain field
        'owner': {'GITHUB': 'owner.login'}
    },
    payloads = {
        'view': view_function # Custom function for specific logic
    }
)
```
In this case, the framework treats the GitHub API exactly like a database. `read/create` calls are translated into HTTP calls by the `infrastructure.persistence.api` adapter (or similar), but it is transparent to the application.

## 3. Connection with Infrastructure

The "glue" is the Dependency Injection system and the Managers (`storekeeper`).

1.  **Request**: The app asks for data from the `products` repository.
2.  **Factory**: Reads the config of `products.py`. Sees `location='SUPABASE'`.
3.  **Adapter**: Loads `src/infrastructure/persistence/supabase.py`.
4.  **Execution**: The adapter executes the actual query.

The analyzed `redis.py` adapter shows standard methods (`create`, `read`, `update`, `delete`) that accept generic constants. This forces all databases to behave the same way in the eyes of the application.

## 4. Critical Comparison

| Feature | Frameworkk (This) | Django | FastAPI (SQLAlchemy) |
| :--- | :--- | :--- | :--- |
| **Model Definition** | JSON Schema (Pure Data) | Python Classes (Active Record) | Pydantic Classes / SQLAlchemy |
| **Data Access** | Repository Factory (Declarative) | ORM (Methods on objects) | Session / Repository Pattern (Manual) |
| **Flexibility** | **High**: External APIs treated as DB | **Medium**: Tied to supported SQL DBs | **High**: But you have to write the code |
| **Complexity** | High abstraction (Magic) | Low (Explicit) | Medium (Explicit) |

### My Opinion
This approach to the Repository is very powerful for **microservices or hybrid architectures**, where data might come from a SQL DB, a NoSQL, or a third-party REST API.
*   **Pros**: Uniforms data access. It doesn't matter if you read from GitHub or Postgres, the application code is identical.
*   **Cons**: Loses specific DB features (e.g., complex SQL queries, optimized joins) unless bypassing the abstraction. It is a "Lowest Common Denominator".

In summary: **Application defines "What" (JSON/Config), Infrastructure defines "How" (Adapter), and the Framework joins them at runtime.**
