# Guide Pratiche (How-To)

## Come creare una nuova Action

1.  Crea un nuovo file in `src/application/action/`.
2.  Il nome del file dovrebbe riflettere l'azione (es. `create_user.py`).
3.  Definisci una funzione o una classe che implementa la logica.
4.  Esempio:
    ```python
    async def create_user(repository, **kwargs):
        user_data = kwargs.get('data')
        # Validazione...
        return await repository.save(user_data)
    ```

## Come aggiungere un nuovo Modello

1.  Aggiungi un file JSON o Python in `src/application/model/`.
2.  Definisci la struttura dei dati.
    ```json
    {
        "name": "user",
        "fields": {
            "username": "string",
            "email": "string"
        }
    }
    ```

## Come implementare un nuovo Adapter

Se vuoi supportare una nuova tecnologia (es. un nuovo database):

1.  Identifica la `Port` corrispondente in `src/framework/port/` (es. `persistence.py`).
2.  Crea un nuovo file in `src/infrastructure/persistence/` (es. `mongo.py`).
3.  Implementa la classe o le funzioni richieste dalla Port.
4.  Aggiorna `pyproject.toml` per usare il nuovo adapter.

## Come eseguire il Debug

1.  Assicurati che i log siano configurati su `debug` in `pyproject.toml`.
2.  Controlla l'output della console o il file di log configurato.
3.  Usa `print()` o un debugger standard Python se necessario, ma ricorda che il codice è asincrono (`async/await`).
