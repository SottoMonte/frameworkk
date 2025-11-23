# System Architecture

## Directory Structure

The project structure follows a layered architecture, designed to keep code clean, testable, and independent of infrastructure details.

### `src/application` (Core)
This folder contains business logic and domain models. It is independent of any external framework.
*   **`action/`**: Contains use cases (e.g., `save.py`). Each file represents a single action the system can perform.
*   **`model/`**: Defines entities and data structures (often in JSON format or Python classes).
*   **`repository/`**: Interfaces for data access. They define *what* to do, not *how*.
*   **`policy/`**: Specific business rules.

### `src/framework` (Orchestration)
Connects the application to the infrastructure.
*   **`manager/`**: Flow managers (e.g., `Executor` for actions, `Actuator` for effects).
*   **`port/`**: Interfaces (contracts) that the infrastructure must satisfy.
*   **`service/`**: Shared domain services.

### `src/infrastructure` (Adapters)
Concrete implementations of technologies.
*   **`persistence/`**: Adapters for databases (SQL, Redis, FileSystem).
*   **`presentation/`**: Adapters for user interface or APIs (Web, CLI).
*   **`authentication/`**, **`authorization/`**: Security management.

## Data Flow and Dependencies

The fundamental principle is that **dependencies point inwards**.
*   `Infrastructure` depends on `Framework`.
*   `Framework` depends on `Application`.
*   `Application` depends on no one (or only standard libraries).

### Example: Saving Data

1.  **Presentation** (Infra) receives an HTTP request.
2.  Calls the **Executor** (Framework).
3.  The Executor loads the `save` **Action** (Application).
4.  The Action processes data and calls the **Repository** port (Framework).
5.  At runtime, the port is implemented by a **SQL Adapter** (Infrastructure), which executes the query.

This design allows changing the database (e.g., from SQL to Mongo) by only changing the adapter in `infrastructure`, without touching the business logic in `application`.
