# Framework Layer

The `framework` layer is the glue of the system. It manages execution flow, orchestration, and defines the contracts (Ports) that the infrastructure must respect.

## Responsibilities
*   **Orchestration**: Coordinate the execution of Actions (`Manager`).
*   **Abstraction**: Define interfaces for the infrastructure (`Port`).
*   **Services**: Provide shared utility services (`Service`).

## Key Concept: Dependency Inversion
The framework does not depend on the infrastructure. It defines the interfaces (`Port`) that the infrastructure *must implement*. At runtime, the framework receives concrete instances (Dependency Injection).
