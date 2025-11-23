# Models

I `Model` definiscono la struttura dei dati e le entità del dominio. Possono essere semplici definizioni JSON o classi Python (es. Pydantic o dataclasses).

## Definizione JSON
Spesso usiamo JSON per definire lo schema in modo agnostico dal linguaggio.

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

## Utilizzo
I modelli vengono usati da:
1.  **Repository**: Per sapere come mappare i dati sul database.
2.  **Action**: Per validare l'input.
3.  **Presentation**: Per formattare l'output.
