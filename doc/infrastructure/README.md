# Infrastructure Layer

Il layer `infrastructure` contiene i dettagli tecnici e le implementazioni concrete. Qui il codice "tocca" il mondo reale: database, file system, rete, API esterne.

## Responsabilità
*   Implementare le interfacce (`Port`) definite nel framework.
*   Gestire la configurazione specifica delle tecnologie (es. connection string SQL).
*   Adattare i dati dal formato esterno a quello interno dell'applicazione.

## Organizzazione
Ogni sottocartella corrisponde a un tipo di adattatore o servizio tecnico.
