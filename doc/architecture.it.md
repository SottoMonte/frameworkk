# Architettura del Sistema

## Struttura delle Directory

La struttura del progetto segue un'architettura a strati, progettata per mantenere il codice pulito, testabile e indipendente dai dettagli dell'infrastruttura.

### `src/application` (Core)
Questa cartella contiene la logica di business e i modelli di dominio. È indipendente da qualsiasi framework esterno.
*   **`action/`**: Contiene i casi d'uso (es. `save.py`). Ogni file rappresenta una singola azione che il sistema può compiere.
*   **`model/`**: Definisce le entità e le strutture dati (spesso in formato JSON o classi Python).
*   **`repository/`**: Interfacce per l'accesso ai dati. Definiscono *cosa* fare, non *come*.
*   **`policy/`**: Regole di business specifiche.

### `src/framework` (Orchestration)
Collega l'applicazione all'infrastruttura.
*   **`manager/`**: Gestori del flusso (es. `Executor` per le azioni, `Actuator` per gli effetti).
*   **`port/`**: Interfacce (contratti) che l'infrastruttura deve soddisfare.
*   **`service/`**: Servizi di dominio condivisi.

### `src/infrastructure` (Adapters)
Implementazioni concrete delle tecnologie.
*   **`persistence/`**: Adattatori per database (SQL, Redis, FileSystem).
*   **`presentation/`**: Adattatori per l'interfaccia utente o API (Web, CLI).
*   **`authentication/`**, **`authorization/`**: Gestione sicurezza.

## Flusso dei Dati e Dipendenze

Il principio fondamentale è che **le dipendenze puntano verso l'interno**.
*   `Infrastructure` dipende da `Framework`.
*   `Framework` dipende da `Application`.
*   `Application` non dipende da nessuno (o solo da librerie standard).

### Esempio: Salvataggio di un Dato

1.  **Presentation** (Infra) riceve una richiesta HTTP.
2.  Chiama l'**Executor** (Framework).
3.  L'Executor carica l'**Action** `save` (Application).
4.  L'Action elabora i dati e chiama la porta **Repository** (Framework).
5.  A runtime, la porta è implementata da un **Adapter SQL** (Infrastructure), che esegue la query.

Questo design permette di cambiare il database (es. da SQL a Mongo) cambiando solo l'adapter in `infrastructure`, senza toccare la logica di business in `application`.
