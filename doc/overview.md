# Framework Overview

Welcome to the framework documentation. This framework is designed to build scalable and maintainable applications using a hexagonal architecture (or Clean Architecture).

## Key Concepts

The framework is based on a clear separation of responsibilities:

*   **Application (Core)**: Contains pure business logic. It does not depend on databases, web frameworks, or other external technologies. Use cases (`Action`) and domain models reside here.
*   **Framework (Orchestration)**: Manages the application flow. Connects application actions with concrete infrastructure implementations. Uses `Managers` to coordinate operations.
*   **Infrastructure (Adapters)**: Provides concrete implementations for interfaces defined in the framework. Includes databases, external APIs, messaging systems, etc.

## Terminology

*   **Action**: A unit of work or use case (e.g., "Save User", "Send Email").
*   **Manager**: Components that orchestrate dependencies and execution flow (e.g., `Executor`, `Actuator`).
*   **Port**: An interface defined in the framework that the infrastructure must implement.
*   **Adapter**: The concrete implementation of a Port (e.g., a SQL adapter for persistence).
*   **Verdict**: A system for managing authorizations and access decisions.

## Typical Execution Flow

1.  A request arrives from outside (e.g., via HTTP or WebSocket).
2.  The presentation infrastructure (`Presentation`) receives the request.
3.  The request is passed to the `Executor` in the framework.
4.  The `Executor` loads the appropriate `Action` from the application.
5.  The `Action` executes business logic, using `Ports` to access data or external services.
6.  The `Ports` delegate to concrete implementations (`Adapter`) in the infrastructure.
7.  The result is returned up the chain to the presentation.
