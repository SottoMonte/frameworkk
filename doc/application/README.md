# Application Layer

Il layer `application` è il cuore del sistema. Qui risiede tutta la logica di business, indipendente da framework esterni, database o interfacce utente.

## Responsabilità
*   Definire i casi d'uso (`Action`).
*   Definire i modelli di dominio (`Model`).
*   Definire le interfacce per l'accesso ai dati (`Repository`).
*   Implementare le regole di business (`Policy`).

## Regole d'Oro
1.  **Nessuna dipendenza esterna**: Questo layer non deve importare nulla da `infrastructure` o `framework` (eccetto forse utilità pure).
2.  **Purezza**: Le funzioni dovrebbero essere il più pure possibile, delegando gli effetti collaterali alle porte.
3.  **Testabilità**: Tutto qui deve essere testabile unitariamente senza mock complessi di database o server.
