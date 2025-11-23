# Panoramica del Framework

Benvenuto nella documentazione del framework. Questo framework è progettato per costruire applicazioni scalabili e manutenibili utilizzando un'architettura esagonale (o Clean Architecture).

## Concetti Chiave

Il framework si basa su una netta separazione delle responsabilità:

*   **Application (Core)**: Contiene la logica di business pura. Non dipende da database, framework web o altre tecnologie esterne. Qui risiedono i casi d'uso (`Action`) e i modelli di dominio.
*   **Framework (Orchestration)**: Gestisce il flusso dell'applicazione. Collega le azioni dell'applicazione con le implementazioni concrete dell'infrastruttura. Utilizza i `Manager` per coordinare le operazioni.
*   **Infrastructure (Adapters)**: Fornisce le implementazioni concrete per le interfacce definite nel framework. Include database, API esterne, sistemi di messaggistica, ecc.

## Terminologia

*   **Action**: Un'unità di lavoro o caso d'uso (es. "Salva Utente", "Invia Email").
*   **Manager**: Componenti che orchestrano le dipendenze e il flusso di esecuzione (es. `Executor`, `Actuator`).
*   **Port**: Un'interfaccia definita nel framework che l'infrastruttura deve implementare.
*   **Adapter**: L'implementazione concreta di una Port (es. un adattatore SQL per la persistenza).
*   **Verdict**: Un sistema per gestire le autorizzazioni e le decisioni di accesso.

## Flusso di Esecuzione Tipico

1.  Una richiesta arriva dall'esterno (es. via HTTP o WebSocket).
2.  L'infrastruttura di presentazione (`Presentation`) riceve la richiesta.
3.  La richiesta viene passata all'`Executor` nel framework.
4.  L'`Executor` carica l'`Action` appropriata dall'applicazione.
5.  L'`Action` esegue la logica di business, utilizzando le `Port` per accedere ai dati o servizi esterni.
6.  Le `Port` delegano alle implementazioni concrete (`Adapter`) nell'infrastruttura.
7.  Il risultato viene restituito attraverso la catena fino alla presentazione.
