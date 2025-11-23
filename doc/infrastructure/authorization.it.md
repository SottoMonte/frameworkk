# Authorization Adapters

Gli adattatori di autorizzazione (`src/infrastructure/authorization/`) implementano le logiche per decidere "chi può fare cosa".

## Verdict
Il sistema `Verdict` valuta le richieste in base a regole predefinite.
*   Analizza l'utente corrente (dal token o sessione).
*   Controlla i permessi richiesti dall'azione.
*   Emette un "verdetto": Permesso concesso o negato.

## Integrazione
L'autorizzazione viene tipicamente invocata dal `Defender` (nel framework) prima di eseguire un'azione.
