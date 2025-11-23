# Application Layer

The `application` layer is the heart of the system. All business logic resides here, independent of external frameworks, databases, or user interfaces.

## Responsibilities
*   Define use cases (`Action`).
*   Define domain models (`Model`).
*   Define interfaces for data access (`Repository`).
*   Implement business rules (`Policy`).

## Golden Rules
1.  **No external dependencies**: This layer must not import anything from `infrastructure` or `framework` (except perhaps pure utilities).
2.  **Purity**: Functions should be as pure as possible, delegating side effects to ports.
3.  **Testability**: Everything here must be unit-testable without complex mocks of databases or servers.
