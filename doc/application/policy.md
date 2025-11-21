# Policies

Le `Policy` incapsulano regole di business complesse o trasversali che non appartengono a una singola entità o azione.

## Esempi
*   **Calcolo Sconti**: Una logica complessa per determinare lo sconto applicabile.
*   **Approvazione**: Regole per determinare se un documento può essere approvato.
*   **Accesso**: Regole di dominio per chi può fare cosa (distinte dall'autorizzazione tecnica).

## Esempio

```python
# src/application/policy/discount.py

def calculate_discount(user, cart_total):
    if user['is_vip']:
        return cart_total * 0.20
    if cart_total > 100:
        return cart_total * 0.10
    return 0
```
