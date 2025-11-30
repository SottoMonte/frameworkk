import asyncio
import functools
from typing import Any, Callable, Dict, List, Optional, Union
#from framework.service.language import get

async def pipe(initial_data: Any, *functions: Callable) -> Dict[str, Any]:
    """
    Esegue una catena di funzioni asincrone in sequenza.
    Si ferma al primo errore (Short-circuit) basandosi sullo schema result.json.
    
    Args:
        initial_data: Il dato di input per la prima funzione.
        *functions: Una sequenza di funzioni asincrone da eseguire.
        
    Returns:
        Un dizionario conforme a result.json.
    """
    current_data = initial_data
    
    for func in functions:
        # Esegue la funzione
        # Gestisce sia funzioni async che sync
        if asyncio.iscoroutinefunction(func):
            outcome = await func(current_data)
        else:
            outcome = func(current_data)
        
        # Controllo automatico basato su result.json
        # Se l'output non è un dizionario, assumiamo che sia un dato grezzo e proseguiamo
        # (ma per il ROP puro, dovremmo aspettarci sempre un result/transaction)
        if isinstance(outcome, dict):
            if not outcome.get('ok', True): # Default a True se 'ok' manca, per flessibilità
                return outcome # Ritorna subito l'errore
            
            # Passa il 'data' pulito al prossimo step se presente, altrimenti l'intero outcome
            current_data = outcome.get('data', outcome)
        else:
            current_data = outcome
        
    return {"ok": True, "data": current_data, "error": None}

async def safe(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Esegue una funzione e converte eccezioni in schema di errore standard (result.json).
    
    Args:
        func: La funzione da eseguire.
        *args, **kwargs: Argomenti per la funzione.
        
    Returns:
        Un dizionario conforme a result.json.
    """
    try:
        if asyncio.iscoroutinefunction(func):
            data = await func(*args, **kwargs)
        else:
            data = func(*args, **kwargs)
            
        # Se la funzione ritorna già un result.json (ha 'ok' e 'data'), lo restituiamo così com'è
        if isinstance(data, dict) and 'ok' in data and 'data' in data:
            return data
            
        return {"ok": True, "data": data, "error": None}
    except Exception as e:
        return {
            "ok": False, 
            "data": None, 
            "error": {"type": type(e).__name__, "message": str(e)}
        }

async def match_result(outcome: Dict[str, Any], on_success: Callable, on_failure: Callable) -> Any:
    """
    Instrada il flusso basandosi sul campo 'ok' del risultato (result.json).
    
    Args:
        outcome: Il dizionario risultato da analizzare.
        on_success: Funzione da chiamare se ok=True (riceve outcome['data']).
        on_failure: Funzione da chiamare se ok=False (riceve outcome['error']).
        
    Returns:
        Il risultato della funzione chiamata (on_success o on_failure).
    """
    if outcome.get('ok') is True:
        if asyncio.iscoroutinefunction(on_success):
            return await on_success(outcome.get('data'))
        return on_success(outcome.get('data'))
    else:
        if asyncio.iscoroutinefunction(on_failure):
            return await on_failure(outcome.get('error'))
        return on_failure(outcome.get('error'))

async def smart_retry(func: Callable, max_attempts: int = 3, retryable_errors: List[str] = None, *args, **kwargs) -> Dict[str, Any]:
    """
    Esegue una funzione che ritorna 'transaction.json'.
    Se 'success' è False, analizza gli errori e decide se riprovare.
    
    Args:
        func: La funzione da eseguire (deve ritornare transaction.json).
        max_attempts: Numero massimo di tentativi.
        retryable_errors: Lista di stringhe (sottostringhe) che identificano errori transitori.
                          Se None, riprova su tutto tranne errori logici ovvi.
        *args, **kwargs: Argomenti per la funzione.
        
    Returns:
        L'ultimo transaction.json ottenuto.
    """
    last_transaction = None
    
    # Default errori riprovabili se non specificati
    if retryable_errors is None:
        retryable_errors = ['timeout', 'connection', 'network', 'busy', 'unavailable']
        
    for attempt in range(max_attempts):
        if asyncio.iscoroutinefunction(func):
            transaction = await func(*args, **kwargs)
        else:
            transaction = func(*args, **kwargs)
            
        last_transaction = transaction
        
        # Lo schema transaction.json garantisce che 'success' esista
        if transaction.get('success'):
            return transaction
            
        # Analisi degli errori
        errors = transaction.get('errors', [])
        errors_str = str(errors).lower()
        
        is_retryable = any(err in errors_str for err in retryable_errors)
        
        if not is_retryable:
            break # Errore non recuperabile, usciamo subito
            
        # Backoff esponenziale semplice opzionale (qui solo print per ora)
        # await asyncio.sleep(0.1 * (2 ** attempt)) 
        
    return last_transaction

def lift_io(io_outcome: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trasforma automaticamente un 'io.json' (Infrastructure) in un 'result.json' (Application).
    
    Args:
        io_outcome: Dizionario conforme a io.json.
        
    Returns:
        Dizionario conforme a result.json.
    """
    status_code = io_outcome.get('status_code', 500)
    
    if 200 <= status_code < 300:
        return {
            "ok": True,
            "data": io_outcome.get('payload'),
            "error": None
        }
    else:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": status_code,
                "message": "Errore infrastruttura",
                "details": io_outcome.get('metadata', {})
            }
        }

def map_data(outcome: Dict[str, Any], mapping_rules: Dict[str, str]) -> Dict[str, Any]:
    """
    Trasforma i dati usando un dizionario di regole dichiarative.
    
    Args:
        outcome: Un result.json o io.json contenente i dati sorgente.
        mapping_rules: Dizionario {chiave_destinazione: percorso_sorgente}.
                       Es. {"name": "user.details.nome"}
                       
    Returns:
        Un result.json con i dati mappati.
    """
    # Determina dove sono i dati sorgente
    source = None
    if 'data' in outcome:
        source = outcome['data']
    elif 'payload' in outcome:
        source = outcome['payload']
    else:
        source = outcome # Fallback, usa l'intero oggetto
        
    # Se l'operazione precedente è fallita, propaga l'errore
    if isinstance(outcome, dict) and not outcome.get('ok', True) and 'error' in outcome:
        return outcome

    new_data = {}
    
    for target_key, source_path in mapping_rules.items():
        # Usa la funzione get di language.py per supportare dot notation
        value = get(source, source_path)
        new_data[target_key] = value
        
    return {"ok": True, "data": new_data, "error": None}

async def gather_results(functions_list: List[Callable]) -> Dict[str, Any]:
    """
    Esegue N funzioni in parallelo e aggrega i risultati.
    
    Args:
        functions_list: Lista di funzioni (o coroutine) da eseguire.
        
    Returns:
        Un result.json aggregato. 'ok' è True solo se TUTTE hanno successo.
    """
    # Avvia le coroutine
    coroutines = []
    for f in functions_list:
        if asyncio.iscoroutinefunction(f):
            coroutines.append(f())
        else:
            # Wrap sync function in coroutine
            async def wrapper(func=f):
                return func()
            coroutines.append(wrapper())
            
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    
    successes = []
    failures = []
    
    for r in results:
        if isinstance(r, Exception):
            failures.append({"type": type(r).__name__, "message": str(r)})
            continue
            
        if isinstance(r, dict):
            if r.get('ok', True): # Assume successo se non specificato diversamente
                successes.append(r.get('data', r))
            else:
                failures.append(r.get('error'))
        else:
            successes.append(r)
    
    return {
        "ok": len(failures) == 0,
        "data": successes,
        "error": failures if failures else None
    }

async def guard(condition: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Verifica una pre-condizione usando MistQL.
    
    Args:
        condition: La condizione MistQL da valutare (stringa).
        data: I dati su cui valutare la condizione MistQL.
        error_message: Messaggio di errore personalizzato se la condizione fallisce.
        
    Returns:
        Un result.json di errore se la condizione è False, altrimenti None.
    """
    import mistql
    
    try:
        # Esegue la query MistQL sui dati forniti
        result = mistql.query(condition, data)
        
        # Se il risultato è truthy, la condizione è soddisfatta
        if result:
            return {
                "success": True, 
                "results": data, 
                "error": None
            }
        else:
            # Condizione non soddisfatta
            return {
                "success": False, 
                "results": None, 
                "error": {
                    "message": error_message,
                    "condition": condition,
                    "evaluated_result": result
                }
            }
    except Exception as e:
        # Errore nell'esecuzione della query MistQL
        return {
            "success": False,
            "results": None,
            "error": {
                "message": f"Errore nella valutazione MistQL: {str(e)}",
                "condition": condition,
                "exception": type(e).__name__
            }
        }

async def fallback(primary_func: Callable, secondary_func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Esegue una funzione secondaria se la primaria fallisce.
    
    Args:
        primary_func: Funzione principale.
        secondary_func: Funzione di fallback.
        *args, **kwargs: Argomenti passati a entrambe.
        
    Returns:
        Il risultato della prima che ha successo, o l'errore della seconda.
    """
    # Prova primaria
    try:
        if asyncio.iscoroutinefunction(primary_func):
            res = await primary_func(*args, **kwargs)
        else:
            res = primary_func(*args, **kwargs)
            
        if isinstance(res, dict) and res.get('ok'):
            return res
    except Exception:
        pass # Ignora eccezioni nella primaria, vai al fallback
        
    # Prova secondaria
    if asyncio.iscoroutinefunction(secondary_func):
        return await secondary_func(*args, **kwargs)
    else:
        return secondary_func(*args, **kwargs)

async def switch(value: Any, cases: Union[Dict[Any, Callable], List[tuple]], default: Optional[Callable] = None) -> Any:
    """
    Esegue una funzione basata su una condizione corrispondente al valore di input.
    Simile a un pattern matching o switch-case funzionale.

    Args:
        value: Il valore da valutare.
        cases: Un dizionario {valore_statico: funzione} o una lista di tuple [(condizione, funzione)].
               Se la condizione è un callable, viene eseguita con 'value'. Se ritorna True, si esegue la funzione associata.
               Se la condizione è statica, si usa l'uguaglianza (==).
        default: Funzione opzionale da eseguire se nessun caso corrisponde.

    Returns:
        Il risultato della funzione eseguita.
    """
    # Normalizza cases in una lista di tuple per iterazione uniforme
    case_list = []
    if isinstance(cases, dict):
        case_list = list(cases.items())
    else:
        case_list = cases

    for condition, func in case_list:
        success = await guard(condition, value).get("success", False)
        
        if success:
            if asyncio.iscoroutinefunction(func):
                return await func(value)
            return func(value)

    # Nessun match
    if default:
        if asyncio.iscoroutinefunction(default):
            return await default(value)
        return default(value)
    
    return None
