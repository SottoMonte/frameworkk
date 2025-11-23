# Infrastructure Layer

The `infrastructure` layer contains technical details and concrete implementations. Here the code "touches" the real world: databases, file systems, networks, external APIs.

## Responsibilities
*   Implement interfaces (`Port`) defined in the framework.
*   Manage technology-specific configuration (e.g., SQL connection strings).
*   Adapt data from external formats to internal application formats.

## Organization
Each subfolder corresponds to a type of adapter or technical service.
