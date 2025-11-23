# Models

`Model`s define the data structure and domain entities. They can be simple JSON definitions or Python classes (e.g., Pydantic or dataclasses).

## JSON Definition
We often use JSON to define the schema in a language-agnostic way.

```json
// src/application/model/user.json
{
    "name": "user",
    "fields": {
        "id": "uuid",
        "username": "string",
        "email": "email",
        "created_at": "datetime"
    },
    "constraints": {
        "email": "unique"
    }
}
```

## Usage
Models are used by:
1.  **Repository**: To know how to map data to the database.
2.  **Action**: To validate input.
3.  **Presentation**: To format output.
