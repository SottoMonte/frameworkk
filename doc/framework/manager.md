# Managers

`Manager`s are components that orchestrate parts of the system.

## Executor
The `Executor` (`src/framework/manager/executor.py`) is responsible for executing Actions.
*   Receives a request (action name and parameters).
*   Dynamically loads the appropriate action module.
*   Injects necessary dependencies.
*   Executes the action and returns the result.

## Actuator
The `Actuator` (`src/framework/manager/actuator.py`) manages the execution of side effects or commands towards external systems, often asynchronously or deferred.

## Authenticator / Defender
They manage security, verifying credentials and permissions before an action is executed.
