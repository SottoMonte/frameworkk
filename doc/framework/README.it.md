# Framework Layer

Il layer `framework` è il collante del sistema. Gestisce il flusso di esecuzione, l'orchestrazione e definisce i contratti (Porte) che l'infrastruttura deve rispettare.

## Responsabilità
*   **Orchestrazione**: Coordinare l'esecuzione delle Action (`Manager`).
*   **Astrazione**: Definire le interfacce per l'infrastruttura (`Port`).
*   **Servizi**: Fornire servizi di utilità condivisi (`Service`).

## Concetto Chiave: Inversione delle Dipendenze
Il framework non dipende dall'infrastruttura. Definisce le interfacce (`Port`) che l'infrastruttura *deve implementare*. A runtime, il framework riceve le istanze concrete (Dependency Injection).
