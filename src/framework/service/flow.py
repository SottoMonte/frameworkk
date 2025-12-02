import asyncio
import functools
from typing import Any, Callable, Dict, List, Optional, Union
#from framework.service.language import get

'''
Orchestrazione: pipe

Controllo: switch

Resilienza: catch, retry, timeout

Iterazione/Parallelismo: foreach, fan_out

Stato: set, get, select

Validazione: guard

I/O (Punto di Ingresso): trigger,data

'''

def step(func, *args, **kwargs):
    return (func, args, kwargs)

async def pipe(initial_data, *stages):
    """
    Orchestra un flusso dichiarativo, chiamando le funzioni in sequenza.
    Ogni stage deve essere fornito nel formato: (funzione, args_tuple, kwargs_dict).
    Le sorgenti supportate sono: 'input', 'output' o valori letterali.
    """
    context = {
        'input': initial_data,
        'outputs': [],
    }
    stage_index = 0
    final_output = None
    
    for stage_tuple in stages:
        stage_index += 1
        func = stage_tuple[0]
        pos_sources = stage_tuple[1] # Tupla per args posizionali
        kw_sources = stage_tuple[2]  # Dizionario per kwargs
        
        # --- Funzione Helper per Risolvere la Sorgente ---
        def resolve_source(source, is_kwarg) -> Any:
            if source == 'outputs':
                if not context['outputs']:
                    scope = "Kwarg" if is_kwarg else "Arg"
                    raise ValueError(f"Stage {stage_index} {scope} richiede 'output', ma non ci sono stage precedenti.")
                return context['outputs'][-1]

            elif source == 'input':
                return context['input']
            
            else:
                # Argomento letterale
                return source 

        # 1. Risoluzione Argomenti Posizionali (call_args)
        call_args = [resolve_source(source, is_kwarg=False) for source in pos_sources]
        

        # 2. Risoluzione Argomenti per Parola Chiave (call_kwargs)
        call_kwargs = {}
        for key, source in kw_sources.items():
            call_kwargs[key] = resolve_source(source, is_kwarg=True)

        # 3. Esecuzione della Funzione
        try:
            #print(f"Stage {stage_index}: Chiamata a {func.__name__}(args={call_args}, kwargs={call_kwargs})")
            if asyncio.iscoroutinefunction(func):
                outcome = await func(*call_args, **call_kwargs)
            else:
                outcome = func(*call_args, **call_kwargs)

        except Exception as e:
            print(f"ERRORE nello stage {stage_index} ({func.__name__}): {e}")
            return {"ok": False, "error": str(e), "stage": stage_index}

        # 4. Aggiornamento del Contesto di Stato (Logica ROP)
        
        if isinstance(outcome, dict) and outcome.get('ok') is True and 'data' in outcome:
            data_to_pass = outcome['data']
        else:
            data_to_pass = outcome
        
        # Aggiorna il contesto e l'output per i prossimi stage
        final_output = data_to_pass
        context['outputs'].append(data_to_pass)
        
    return final_output

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
        if type(data) not in [str, int, float, bool,dict,list]:
            data = str(data)
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
                    #"message": error_message,
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

async def switch(value, cases):
    """
    Esegue una funzione (creata con step) basata su una condizione corrispondente.
    """
    case_list = []
    if isinstance(cases, dict):
        # Se dizionario: [(valore_statico, action_step)]
        case_list = list(cases.items())
    else:
        # Se lista: [(condizione, action_step)]
        case_list = cases

    for condition, action_step in case_list:
        
        # 1. Valuta la condizione
        guard_result = await guard(condition, value)
        print(guard_result)
        success = guard_result.get("success", False)
        
        if success:
            # 2. Decostruisci l'output di step (func, args, kwargs)
            if not isinstance(action_step, tuple) or len(action_step) < 2:
                raise TypeError("L'azione nel case deve essere un output di step (funzione, args, kwargs).")
            
            fun = action_step[0]
            args = action_step[1] if len(action_step) > 1 else ()
            kwargs = action_step[2] if len(action_step) > 2 else {}
            aaa = []
            for arg in args:
                if arg == "@":
                    aaa.append(value)
                else:
                    aaa.append(arg)
            args = tuple(aaa)
            #print(f"Chiamata a {fun.__name__}(args={args}, kwargs={kwargs})")
            # 3. Esegui la funzione
            if asyncio.iscoroutinefunction(fun):
                return await fun(*args, **kwargs)
            return fun(*args, **kwargs)

async def catch(try_step, catch_step):
    """
    Esegue il primo step. Se il risultato è un oggetto errore (dizionario con 'ok': False), 
    esegue il secondo step come fallback.
    """
    # Usiamo una versione interna di 'pipe' per eseguire un singolo step
    # Per semplicità, la chiameremo _execute_step
    
    # 1. Tenta di eseguire lo step principale
    outcome = await _execute_step_internal(try_step)
    
    # 2. Verifica se è un oggetto errore ROP
    if isinstance(outcome, dict) and outcome.get('ok') is False:
        print(f"ATTENZIONE: Fallimento nello step. Esecuzione del fallback: {outcome.get('error')}")
        
        # Puoi anche passare l'errore al catch_step, ma per semplicità lo eseguiamo direttamente
        # Esegue lo step di fallback
        return await _execute_step_internal(catch_step)
    
    return outcome

async def foreach(input_list, step_to_run) -> List[Any]:
    """
    Esegue uno step o un pipe su ogni elemento di una lista in modo sequenziale.
    Ogni elemento della lista diventa l'initial_data per lo step_to_run.
    """
    results = []

    # Se l'input_list è una tupla, la convertiamo in lista per l'iterazione, se necessario.
    if isinstance(input_list, tuple):
        input_list = list(input_list)
        
    if not isinstance(input_list, list):
        raise TypeError(f"foreach si aspetta una lista o una tupla come primo argomento, ricevuto: {type(input_list)}")
        
    for item in input_list:
        # Esegue lo step usando 'item' come initial_data del sub-flow
        result = await pipe(item, step_to_run)
        results.append(result)
        
    return results

async def _execute_step_internal(action_step) -> Any:
    """
    Esegue un'azione (funzione, args, kwargs) fornita da 'step', 
    senza il contesto completo del pipe.
    """
    if not isinstance(action_step, tuple) or len(action_step) < 2 or not callable(action_step[0]):
        raise TypeError("L'azione fornita non è un formato step valido.")
        
    fun = action_step[0]
    args = action_step[1] if len(action_step) > 1 else ()
    kwargs = action_step[2] if len(action_step) > 2 else {}
    
    try:
        if asyncio.iscoroutinefunction(fun):
            return await fun(*args, **kwargs)
        return fun(*args, **kwargs)
    except Exception as e:
        # Implementazione minimale ROP per gli errori
        return {"ok": False, "error": str(e), "function": fun.__name__}

async def fan_out(*steps_to_run) -> List[Any]:
    """
    Esegue una lista di step o pipe in parallelo (con asyncio.gather).
    """
    tasks = []
    
    for action_step in steps_to_run:
        if not isinstance(action_step, tuple) or not action_step:
            raise TypeError("Gli argomenti di fan_out devono essere step validi (tuple).")
            
        # Creiamo un'attività asincrona per eseguire lo step
        # Nota: Eseguiamo lo step con pipe(None, action_step) assumendo che non richieda 'input'
        # Questo è un'assunzione, se gli step hanno bisogno di input, questa logica va adattata.
        task = asyncio.create_task(_execute_step_internal(action_step))
        tasks.append(task)
    
    # Attendiamo che tutti i task in parallelo completino
    return await asyncio.gather(*tasks)

async def retry(action_step, attempts = 3, delay = 1.0) -> Any:
    """
    Esegue uno step, riprovando in caso di fallimento fino a un massimo di tentativi.
    """
    last_outcome = None
    
    for attempt in range(attempts):
        print(f"Tentativo {attempt + 1}/{attempts} per lo step...")
        
        # Esegue lo step usando l'helper interno
        outcome = await _execute_step_internal(action_step)
        last_outcome = outcome
        
        # Logica di successo (non è un oggetto errore ROP)
        if not (isinstance(outcome, dict) and outcome.get('ok') is False):
            print(f"Step completato al tentativo {attempt + 1}.")
            return outcome
        
        # Se siamo all'ultimo tentativo, non aspettare e restituisci l'errore
        if attempt < attempts - 1:
            print(f"Fallimento. Attesa di {delay} secondi prima di riprovare.")
            await asyncio.sleep(delay)
            # Logica per l'aumento del delay (ritardo esponenziale)
            # delay *= 2 # Esempio di ritardo esponenziale

    print(f"Fallimento definitivo dopo {attempts} tentativi.")
    return last_outcome

async def timeout(action_step, max_seconds = 30.0) -> Any:
    """
    Esegue uno step e lo annulla se supera il tempo limite specificato.
    """
    # Usiamo il meccanismo di timeout di asyncio
    try:
        # Crea un Task che esegue lo step
        task = asyncio.create_task(_execute_step_internal(action_step))
        
        # Attende il completamento del Task con un timeout
        return await asyncio.wait_for(task, timeout=max_seconds)
        
    except asyncio.TimeoutError:
        # Il Task è scaduto: restituisce un errore ROP
        return {
            "ok": False,
            "error": f"Timeout superato: lo step non è stato completato entro {max_seconds} secondi.",
            "type": "TimeoutError"
        }
    except Exception as e:
        # Gestisce altri errori generici durante l'esecuzione del task
        return {
            "ok": False,
            "error": f"Errore interno durante il timeout: {e}",
            "type": "ExecutionError"
        }

async def select(source, path) -> Any:
    """
    Estrae un valore da una sorgente complessa (dizionario o lista) usando una 'path'
    separata da punti (es. 'user.profile.id' o 'data.0.value').

    Args:
        source: L'oggetto dati di partenza (normalmente risolto come 'output' o 'input').
        path: La stringa di navigazione separata da punti.
    """
    
    # 1. Risolvi la sorgente
    # ATTENZIONE: Se 'select' è usato come step nel pipe, 
    # la risoluzione della sorgente ('output', 'input') deve avvenire 
    # nello step precedente o in un wrapper, non qui. 
    # Qui assumiamo che 'source' sia già l'oggetto dati di Python.
    
    # 2. Navigazione
    current_data = source
    path_segments = path.split('.')
    
    for segment in path_segments:
        try:
            if isinstance(current_data, dict):
                current_data = current_data[segment]
            
            elif isinstance(current_data, list):
                # Gestione degli indici di lista (es. 'data.0.value')
                index = int(segment)
                current_data = current_data[index]
            
            else:
                # La navigazione è fallita perché il tipo di dato non è navigabile
                return {
                    "ok": False,
                    "error": f"Impossibile navigare in '{segment}': il dato è di tipo {type(current_data).__name__}.",
                    "path": path
                }
                
        except (KeyError, IndexError, ValueError):
            # La chiave non esiste o l'indice non è valido
            return {
                "ok": False,
                "error": f"Chiave o indice non trovato: '{segment}' nel percorso '{path}'.",
                "path": path
            }
        
    return current_data

async def throttle(action_step, rate_limit_ms = 1000) -> Any:
    """
    Esegue uno step solo se è trascorso abbastanza tempo (rate_limit_ms) 
    dall'ultima esecuzione di quello stesso step. 
    Se non è trascorso abbastanza tempo, l'esecuzione viene ritardata.
    
    Args:
        action_step: Lo step da eseguire.
        rate_limit_ms: Il ritardo minimo in millisecondi tra le chiamate.
    """
    
    # 1. Identifica l'azione
    fun = action_step[0]
    action_id = fun.__name__ # Usa il nome della funzione come ID per la limitazione
    
    # Tempo minimo in secondi
    rate_limit_s = rate_limit_ms / 1000.0 
    current_time = time.time()
    
    # 2. Verifica lo stato precedente
    last_execution_time = _throttle_state.get(action_id, 0)
    time_since_last_call = current_time - last_execution_time
    
    if time_since_last_call < rate_limit_s:
        # 3. Se il limite è superato, calcola il tempo di attesa e aspetta
        wait_time = rate_limit_s - time_since_last_call
        print(f"THROTTLE: Limite raggiunto per {action_id}. Attesa di {wait_time:.3f}s...")
        await asyncio.sleep(wait_time)
        
    # 4. Aggiorna lo stato e esegui l'azione
    _throttle_state[action_id] = time.time()
    
    return await _execute_step_internal(action_step)

async def trigger(event_name, **params) -> Dict[str, Any]:
    """
    Sospende l'esecuzione del flow fino a quando l'evento con il nome specificato non viene 
    attivato esternamente tramite la funzione 'activate_trigger'.

    Args:
        event_name: Il nome univoco dell'evento (es. 'webhook_order_complete').
        params: Parametri di configurazione (ignorati in attesa).

    Returns:
        Il payload (data) ricevuto al momento dell'attivazione dell'evento.
    """
    print(f"TRIGGER: Stage '{event_name}' in attesa di attivazione esterna...")
    
    # 1. Crea o recupera l'oggetto Event
    if event_name not in _active_events:
        _active_events[event_name] = asyncio.Event()
    
    event_obj = _active_events[event_name]

    # 2. Sospende l'esecuzione in modo non bloccante
    await event_obj.wait()

    # 3. L'evento è avvenuto. Estrai il payload e pulisci.
    payload = _event_payloads.pop(event_name, {"data": "Dati non disponibili o mancanti."})
    _active_events.pop(event_name, None)

    print(f"TRIGGER: Stage '{event_name}' attivato. Payload ricevuto.")
    
    # Restituisce il payload, che alimenta lo stage successivo del pipe.
    return {
        "ok": True, 
        "data": payload
    }