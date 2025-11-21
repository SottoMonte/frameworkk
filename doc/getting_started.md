# Guida Introduttiva

Questa guida ti aiuterà a configurare e avviare un progetto basato su questo framework.

## Prerequisiti

*   Python 3.9 o superiore
*   `pip` (gestore pacchetti Python)
*   Accesso a un database (opzionale per l'avvio base, ma necessario per molte funzionalità)

## Installazione

1.  Clona il repository:
    ```bash
    git clone <url-repository>
    cd <nome-cartella>
    ```

2.  Crea un ambiente virtuale:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Su Linux/Mac
    # venv\Scripts\activate  # Su Windows
    ```

3.  Installa le dipendenze:
    ```bash
    pip install -r requirements.txt
    ```

## Configurazione

Il file principale di configurazione è `pyproject.toml`. Qui puoi definire:

*   **Database**: Configura la sezione `[persistence.session]` o simili con le credenziali del tuo database (es. Redis, SQL).
*   **Messaggistica**: Configura `[amessage]` per i log e la comunicazione.
*   **Autenticazione**: Configura `[authentication]` per i provider (es. Supabase, GitHub).

Esempio di configurazione minima per i log su console:
```toml
[amessage.log]
adapter = "console"
level = "debug"
```

## Avvio dell'Applicazione

L'applicazione può essere avviata utilizzando il comando (esempio basato su `Procfile` o script comuni):

```bash
python src/main.py
# Oppure, se usi un server web come uvicorn/gunicorn:
# uvicorn src.main:app --reload
```
*(Nota: Verifica il file `Procfile` o la documentazione specifica del progetto per il comando esatto di avvio)*

## Esecuzione dei Test

Per eseguire i test unitari:

```bash
python -m unittest discover src -p "*.test.py"
```
Oppure esegui un test specifico:
```bash
python src/infrastructure/authorization/verdict.test.py
```
