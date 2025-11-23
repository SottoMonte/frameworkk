# Ports

Le `Port` (`src/framework/port/`) sono interfacce astratte. Definiscono i servizi di cui l'applicazione ha bisogno per funzionare.

## Esempio: Persistence Port

```python
# src/framework/port/persistence.py

class Port:
    def save(self, data):
        pass
    
    def delete(self, id):
        pass
```

## Perché usare le Porte?
*   **Testabilità**: Puoi creare "finti" adapter (Mock) per i test che implementano la porta senza usare un vero database.
*   **Flessibilità**: Puoi cambiare l'implementazione reale (es. da MySQL a PostgreSQL) senza toccare una riga di codice nell'applicazione.
