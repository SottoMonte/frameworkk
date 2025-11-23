# Framework Documentation

Welcome to the technical documentation. This guide is structured to mirror the source code architecture.

## Index

### 1. [Application Layer](application/README.md) (`src/application`)
The heart of business logic.
*   [Actions](application/action.md): How to write use cases.
*   [Models](application/model.md): Data definition.
*   [Repositories](application/repository.md): Data access interfaces.
*   [Policies](application/policy.md): Business rules.

### 2. [Framework Layer](framework/README.md) (`src/framework`)
The orchestration system.
*   [Managers](framework/manager.md): Executor, Actuator, etc.
*   [Ports](framework/port.md): Contracts for infrastructure.
*   [Services](framework/service.md): Shared domain services.

### 3. [Infrastructure Layer](infrastructure/README.md) (`src/infrastructure`)
Concrete implementations and technical details.
*   [Persistence](infrastructure/persistence.md): Databases (SQL, Redis, etc.).
*   [Presentation](infrastructure/presentation.md): Web APIs, CLI.
*   [Authorization](infrastructure/authorization.md): Security and permissions.

## Other Resources
*   [General Overview](overview.md)
*   [Getting Started Guide](getting_started.md)
*   [Architecture](architecture.md)
*   [Practical Guides](guides.md)
