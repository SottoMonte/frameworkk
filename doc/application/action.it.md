# Actions

Le `Action` rappresentano i casi d'uso del sistema. Ogni file in `src/application/action/` corrisponde a un'operazione specifica che l'utente può richiedere.

## Struttura
Una Action è tipicamente una funzione asincrona o una classe con un metodo `execute`.

```python
# src/application/action/create_user.py

async def create_user(repository, mailer, **kwargs):
    """
    Crea un nuovo utente.
    
    Args:
        repository: Porta per la persistenza (iniettata).
        mailer: Porta per invio email (iniettata).
        kwargs: Dati di input (es. username, email).
    """
    user_data = kwargs.get('data')
    
    # 1. Validazione
    if not user_data.get('email'):
        return {"error": "Email required"}
        
    # 2. Logica di business
    user = await repository.save(user_data)
    
    # 3. Effetti collaterali (tramite porte)
    await mailer.send_welcome(user['email'])
    
    return user
```

## Best Practices
*   **Nomi espliciti**: Usa verbi nel nome del file (es. `save.py`, `delete.py`, `calculate_tax.py`).
*   **Iniezione delle dipendenze**: Non istanziare mai database o servizi direttamente. Aspettati che vengano passati come argomenti.
*   **Input/Output**: Ricevi dizionari o DTO semplici, restituisci dizionari o DTO semplici.
