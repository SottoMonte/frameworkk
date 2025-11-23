# Authorization Adapters

Authorization adapters (`src/infrastructure/authorization/`) implement logic to decide "who can do what".

## Verdict
The `Verdict` system evaluates requests based on predefined rules.
*   Analyzes the current user (from token or session).
*   Checks permissions required by the action.
*   Issues a "verdict": Permission granted or denied.

## Integration
Authorization is typically invoked by the `Defender` (in the framework) before executing an action.
