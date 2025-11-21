# Managers

I `Manager` sono componenti che orchestrano parti del sistema.

## Executor
L'`Executor` (`src/framework/manager/executor.py`) è responsabile dell'esecuzione delle Action.
*   Riceve una richiesta (nome dell'azione e parametri).
*   Carica dinamicamente il modulo dell'azione appropriata.
*   Inietta le dipendenze necessarie.
*   Esegue l'azione e restituisce il risultato.

## Actuator
L'`Actuator` (`src/framework/manager/actuator.py`) gestisce l'esecuzione di effetti collaterali o comandi verso sistemi esterni, spesso in modo asincrono o differito.

## Authenticator / Defender
Gestiscono la sicurezza, verificando le credenziali e i permessi prima che un'azione venga eseguita.
