import asyncio
import functools
from typing import Any, Callable, Dict, List, Optional, Union
from framework.service.inspector import LogReportEncoder, framework_log, buffered_log, _load_resource, analyze_exception, _get_system_info, log_block
from framework.service.context import container
import uuid
import contextvars
import inspect
import json
import tomli
import hashlib
from jinja2 import Environment
from cerberus import Validator

'''
Orchestrazione: pipe

Controllo: switch

Resilienza: catch, retry, timeout

Iterazione/Parallelismo: foreach, fan_out

Stato: set, get, select

Validazione: guard

I/O (Punto di Ingresso): trigger,data

'''

mappa = {
    (str,dict,''): lambda v: v if isinstance(v, dict) else {},
    (str,dict,'json'): lambda v: json.loads(v) if isinstance(v, str) else {},
    (dict,str,'json'): lambda v: json.dumps(v,indent=4,cls=LogReportEncoder) if isinstance(v, dict) else '',
    (str,str,'hash'): lambda v: hashlib.sha256(v.encode('utf-8')).hexdigest() if isinstance(v, str) else '',
    (str,dict,'toml'): lambda content: tomli.loads(content) if isinstance(content, str) else {},
    (dict,str,'toml'): lambda data: tomli.dumps(data) if isinstance(data, dict) else '',
}

async def convert(target, output,input=''):
    try:
        return mappa[(type(target),output,input)](target)
    except KeyError:
        raise ValueError(f"Conversione non supportata: {type(target)} -> {type(output)} da {input}")
    except Exception as e:
        raise ValueError(f"Errore conversione: {e}")

def get(dictionary, domain, default=None):
    """Gets data from a dictionary using a dotted accessor-string, returning default only if path not found."""
    if not isinstance(dictionary, (dict, list)):
        raise TypeError("Il primo argomento deve essere un dizionario o una lista.")
    current_data = dictionary
    for chunk in domain.split('.'):
        if isinstance(current_data, list):
            try:
                index = int(chunk)
                current_data = current_data[index]
            except (IndexError, ValueError, TypeError):
                # Se l'indice non è valido o current_data non è una lista
                return default
        elif isinstance(current_data, dict):
            if chunk in current_data:
                current_data = current_data[chunk]
            else:
                # Se la chiave non è presente nel dizionario
                return default
        else:
            # Se current_data non è né un dizionario né una lista nel mezzo del percorso
            return default
    
    # Restituisce il valore trovato. Se il valore trovato è None, lo restituisce così com'è.
    return current_data 

async def format(target ,**constants):
    try:
        jinjaEnv = Environment()
        jinjaEnv.filters['get'] = lambda d, k, default=None: d.get(k, default) if isinstance(d, dict) else default
        template = jinjaEnv.from_string(target)
        return template.render(constants)
    except Exception as e:
        raise ValueError(f"Errore formattazione: {e}")

async def normalize(value,schema, mode='full'):
    """
    Convalida, popola, trasforma e struttura i dati utilizzando uno schema Cerberus.

    Args:
        schema (dict): Lo schema Cerberus da applicare ai dati.
        value (dict, optional): I dati da elaborare. Defaults a {}.
        mode (str, optional): Modalità di elaborazione (es. 'full'). Non completamente utilizzato qui,
                              ma mantenuto per coerenza se hai logiche esterne che lo usano.
        lang (str, optional): Lingua per il caricamento dinamico degli schemi (se implementato).

    Returns:
        dict: I dati elaborati e validati.

    Raises:
        ValueError: Se la validazione fallisce.
    """
    value = value or {}

    if not isinstance(schema, dict):
        raise TypeError("Lo schema deve essere un dizionario valido per Cerberus.",schema)
    if not isinstance(value, dict):
        raise TypeError("I dati devono essere un dizionario valido per Cerberus.",value)

    # 1. Popolamento e Trasformazione Iniziale (Default, Funzioni)
    # Cerberus gestisce i 'default', ma le 'functions' richiedono un pre-processing
    #processed_value = value.copy() # Lavora su una copia per non modificare l'originale
    #processed_value = copy.deepcopy(value)
    processed_value = value
    for key in schema.copy():
        item = schema[key]
        for field_name, field_rules in item.copy().items():
            if field_name.startswith('_'):
                schema.get(key).pop(field_name)


    for field_name, field_rules in schema.copy().items():
        #print(f"Processing field: {field_name} with rules: {field_rules}")
        if isinstance(field_rules, dict) and 'function' in field_rules:
            func_name = field_rules['function']
            if func_name == 'generate_identifier':
                # Applica solo se il campo non è già presente
                if field_name not in processed_value:
                    #processed_value[field_name] = generate_identifier()
                    pass
            elif func_name == 'time_now_utc':
                # Applica solo se il campo non è già presente
                if field_name not in processed_value:
                    #processed_value[field_name] = time_now_utc()
                    pass
            # Aggiungi altre funzioni qui

    # Cerberus Validation (Convalida, Tipi, Required, Regex, Default)
    # Crea un validatore Cerberus con lo schema fornito
    #print("##################",schema)
    v = Validator(schema,allow_unknown=True)
    # allow_unknown={'comment': True}

    # Permetti a Cerberus di gestire i valori di default durante la validazione
    # Cerberus gestirà 'type', 'required', 'default' e 'regex' direttamente
    if not v.validate(processed_value):
        # La validazione fallisce, Cerberus fornisce i messaggi di errore
        #errors_str = "; ".join([f"{k}: {', '.join(v)}" for k, v in v.errors.items()])
        framework_log("WARNING", f"Errore di validazione: {v.errors}", emoji="⚠️", data=processed_value)
        raise ValueError(f"⚠️ Errore di validazione: {v.errors} | data:{processed_value}")

    final_output = v.document

    return final_output

# =====================================================================
# --- Context Management ---
# =====================================================================

# Context var per propagare il transaction id nei flussi asincroni
_transaction_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('transaction_id', default=None)

def get_transaction_id() -> Optional[str]:
    """Restituisce il transaction id corrente dal contextvar, se presente."""
    return _transaction_id.get()

def set_transaction_id(tx: Optional[str]) -> contextvars.Token:
    """Imposta il transaction id corrente nel contextvar (pubblica API)."""
    if tx is None:
        return _transaction_id.set(None)
    
    if not isinstance(tx, str):
         # raise TypeError(f"Il Transaction ID deve essere una stringa, ricevuto {type(tx)}")
         tx = str(tx)
    
    return _transaction_id.set(tx)

# Context var per propagare i requirements dei servizi
_requirements: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar('requirements', default={})

def get_requirements() -> Dict[str, Any]:
    """Restituisce i requirements correnti dal contextvar."""
    return _requirements.get()

# =====================================================================
# =====================================================================
# --- Decorators ---
# =====================================================================

def _prepare_async_context(custom_filename, **constants):
    """Prepara requirements, inject e schema path per il decoratore."""
    known_params = {'managers', 'outputs', 'inputs'}
    requirements = {k: v for k, v in constants.items() if k not in known_params}
    
    inject = [getattr(container, manager)() for manager in constants.get('managers', []) if hasattr(container, manager)]
    
    output_schema_path = 'framework/scheme/transaction.json'
    if 'outputs' in constants and constants['outputs']:
         output_schema_path = constants['outputs']
         
    return requirements, inject, output_schema_path

def _setup_transaction_context():
    """Gestisce l'inizializzazione del Transaction ID."""
    current_tx_id = get_transaction_id()
    tx_token = None
    if not current_tx_id:
        current_tx_id = str(uuid.uuid4())
        tx_token = set_transaction_id(current_tx_id)
    return current_tx_id, tx_token

async def _execute_wrapper(function, args, kwargs, inject, current_tx_id):
    """Esegue la funzione wrappata e arricchisce il risultato."""
    args_inject = list(args) + inject
    step_tuple = (function, tuple(args_inject), kwargs)
    
    transaction = await _execute_step_internal(step_tuple)
    # print("INNNNNNNNN ASTNC---------------------", transaction) # Debug rimosso per pulizia, ripristinabile se necessario
    
    transaction['identifier'] = current_tx_id
    try:
        sys_info = _get_system_info()
        transaction['worker'] = f"{sys_info.get('hostname', 'unknown')}:{sys_info.get('process_id', '?')}"
    except Exception:
        pass
        
    return transaction

async def _normalize_wrapper(transaction, output_schema_path, wrapper_func, kwargs, current_tx_id):
    """Gestisce il caricamento dello schema e la normalizzazione."""
    target_schema = output_schema_path
    
    if isinstance(target_schema, str):
        try:
            schema_content = await _load_resource(path=target_schema)
            target_schema = json.loads(schema_content)
        except Exception as e:
            buffered_log("ERROR", f"Errore caricamento schema da {output_schema_path}: {e}")
            target_schema = None

    if target_schema and isinstance(target_schema, dict):
        try:
            meta = {
                "action": wrapper_func.__name__,
                "parameters": kwargs,
                "identifier": current_tx_id,
                "worker": transaction.get('worker', 'unknown')
            }
            return await normalize(meta | transaction, target_schema)
        except Exception as e:
            buffered_log("ERROR", f"Errore normalizzazione output in {wrapper_func.__name__}: {e}")
            return transaction
    
    return transaction

def _handle_wrapper_error(e, function, custom_filename, current_tx_id):
    """Gestisce le eccezioni e genera il report di errore."""
    error_details = str(e)
    try:
        source = inspect.getsource(function) if hasattr(function, '__code__') else ""
        report = analyze_exception(source, custom_filename)
        if report and 'EXCEPTION_DETAILS' in report:
            error_details = report['EXCEPTION_DETAILS']
    except Exception:
        pass 

    if not hasattr(container, 'messenger'):
        framework_log("ERROR", f"Eccezione in {function.__name__}: {e}", emoji="❌", exception=e)

    return {
        "success": False, 
        "errors": [error_details],
        "data": None,
        "action": function.__name__,
        "identifier": current_tx_id
    }

def asynchronous(custom_filename: str = __file__, app_context = None, **constants):
    requirements, inject, output_schema_path = _prepare_async_context(custom_filename, **constants)

    def decorator(function):
        @functools.wraps(function)
        async def wrapper(*args, **kwargs):
            wrapper._is_decorated = True
            
            # 1. Setup Context
            current_tx_id, tx_token = _setup_transaction_context()
            req_token = _requirements.set(requirements)
            
            try:
                # --- OpenTelemetry Hook ---
                telemetry_list = getattr(container, 'telemetry', lambda: [])()
                span_name = f"async:{function.__name__}"
                
                with MultiSpanContext(telemetry_list, span_name):
                    # 2. Execute & Enrich
                    transaction = await _execute_wrapper(function, args, kwargs, inject, current_tx_id)
                    
                    # 3. Normalize
                    return await _normalize_wrapper(transaction, output_schema_path, wrapper, kwargs, current_tx_id)

            except Exception as e:
                # 4. Error Handling
                return _handle_wrapper_error(e, function, custom_filename, current_tx_id)

            finally:
                # Cleanup
                _requirements.reset(req_token)
                if tx_token:
                    _transaction_id.reset(tx_token)

        return wrapper
    return decorator

def synchronous(custom_filename: str = __file__, app_context = None,**constants):
    
    inject = [getattr(container, manager)() for manager in constants.get('managers', []) if hasattr(container, manager)]
    output = constants.get('outputs', [])
    input = constants.get('inputs', [])
    
    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            wrapper._is_decorated = True
            try:
                args_inject = list(args) + inject
                if 'inputs' in constants:
                    outcome = function(*args_inject, **kwargs)
                else:
                    outcome = function(*args_inject, **kwargs)
                if 'outputs' in constants:
                    return outcome
                else:
                    return outcome
            except Exception:
                try:
                    source_code = inspect.getsource(function)
                except KeyboardInterrupt:
                    print("Interruzione da tastiera (Ctrl + C).")
                except (OSError, TypeError):
                    source_code = ""

            finally:
                set_transaction_id(None)
                pass
        return wrapper
    return decorator

def transform(data_dict, mapper, values, input, output):

    """ Trasforma un set di costanti in un output mappato. """
    def find_matching_keys(mapper, target_dict):
        """
        Trova la prima chiave del dizionario 'mapper' che è anche presente
        come chiave nel 'target_dict' (output o input).
        
        Args:
            mapper (dict): Il dizionario di mappatura.
            target_dict (dict): Il dizionario con cui confrontare le chiavi (e.g., output/input).
            
        Returns:
            str or None: La prima chiave corrispondente trovata, altrimenti None.
        """
        if not isinstance(mapper, dict) or not isinstance(target_dict, dict):
            # Gestione di base dell'errore se non sono dizionari
            return None
            
        # Crea un set delle chiavi del dizionario target per una ricerca efficiente
        target_keys = set(target_dict.keys())
        
        # Itera sulle chiavi del mapper e cerca la prima corrispondenza nel target
        for key in mapper.keys():
            if key in target_keys:
                return key
                
        return None
    translated = {}

    if not isinstance(data_dict, dict):
        raise TypeError("Il primo argomento deve essere un dizionario.")

    if not isinstance(mapper, dict):
        raise TypeError("'mapper' deve essere un dizionario.")

    if not isinstance(values, dict):
        raise TypeError("'values' deve essere un dizionario.")
    
    if not isinstance(input, dict):
        raise TypeError("'input' deve essere un dizionario.")
    
    if not isinstance(output, dict):
        raise TypeError("'output' deve essere un dizionario.")

    key = find_matching_keys(mapper,output) or find_matching_keys(mapper,input)
    #print(f"find_matching_keys: {key}######################")
    for k, v in mapper.items():
        
        n1 = get(data_dict, k)
        n2 = get(data_dict, v.get(key, None))
        
        if n1:
            output_key = v.get(key, None)
            value = n1
            translated |= put(translated, output_key, value, output)
        if n2:
            output_key = k
            value = n2
            translated |= put(translated, output_key, value, output)

        #print(f"translation: k:{k},key:{key} = {v},{data_dict}",n1,n2) 

    fieldsData = data_dict.keys()
    fieldsOutput = output.keys()


    for field in fieldsData:
        if field in fieldsOutput:
            value = get(data_dict, field)
            translated |= put(translated, field, value, output)

    return translated

def _get_next_schema(schema, key):
    if isinstance(schema, dict):
        if 'schema' in schema:
            if schema.get('type') == 'list': return schema['schema']
            if isinstance(schema['schema'], dict): return schema['schema'].get(key)
        return schema.get(key)
    return None

def put(data: dict, path: str, value: any, schema: dict) -> dict:
    if not isinstance(data, dict): raise TypeError("Il dizionario iniziale deve essere di tipo dict.")
    if not isinstance(path, str) or not path: raise ValueError("Il dominio deve essere una stringa non vuota.")
    if not isinstance(schema, dict) or not schema: raise ValueError("Lo schema deve essere un dizionario valido.")

    result = copy.deepcopy(data)
    node, sch = result, schema
    chunks = path.split('.')

    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        is_index = chunk.lstrip('-').isdigit()
        key = int(chunk) if is_index else chunk
        next_sch = _get_next_schema(sch, chunk)

        if isinstance(node, dict):
            if is_index:
                raise IndexError(f"Indice numerico '{chunk}' usato in un dizionario a livello {i}.")
            if is_last:
                if next_sch is None:
                    raise IndexError(f"Campo '{chunk}' non definito nello schema.")
                if not Validator({chunk: next_sch}, allow_unknown=False).validate({chunk: value}):
                    raise ValueError(f"Valore non valido per '{chunk}': {value}")
                node[key] = value
            else:
                node.setdefault(key, {} if next_sch and next_sch.get('type') == 'dict'
                                     else [] if next_sch and next_sch.get('type') == 'list'
                                     else None)
                if node[key] is None:
                    raise IndexError(f"Nodo intermedio '{chunk}' non valido nello schema.")
                node, sch = node[key], next_sch

        elif isinstance(node, list):
            if not is_index:
                raise IndexError(f"Chiave '{chunk}' non numerica usata in una lista a livello {i}.")
            if not isinstance(next_sch, dict) or 'type' not in next_sch:
                raise IndexError(f"Schema non valido per lista a livello {i}.")

            if key == -1:  # Append mode
                t = next_sch['type']
                new_elem = {} if t == 'dict' else [] if t == 'list' else None
                node.append(new_elem)
                key = len(node) - 1

            if key < 0:
                raise IndexError(f"Indice negativo '{chunk}' non valido in lista.")

            while len(node) <= key:
                t = next_sch['type']
                node.append({} if t == 'dict' else [] if t == 'list' else None)

            if is_last:
                if not Validator({chunk: next_sch}, allow_unknown=False).validate({chunk: value}):
                    raise ValueError(f"Valore non valido per indice '{chunk}': {value}")
                node[key] = value
            else:
                if node[key] is None or not isinstance(node[key], (dict, list)):
                    t = next_sch['type']
                    if t == 'dict': node[key] = {}
                    elif t == 'list': node[key] = []
                    else: raise IndexError(f"Tipo non contenitore '{t}' per nodo '{chunk}' in lista.")
                node, sch = node[key], next_sch

        else:
            raise IndexError(f"Nodo non indicizzabile al passo '{chunk}' (tipo: {type(node).__name__})")

    return result

def get(data, path, default=None):
    if not path: return data
    
    parts = path.split('.', 1)
    key_str = parts[0]
    rest = parts[1] if len(parts) > 1 else None

    # Gestione Wildcard (Dalla get riga 440)
    if key_str == '*':
        if isinstance(data, list):
            return [get(item, rest or '', default) for item in data]
        return default

    # Accesso Sicuro (Logica migliorata stile get2)
    next_data = default
    try:
        if isinstance(data, list):
            # Solo per le liste convertiamo in int
            if key_str.lstrip('-').isnumeric():
                next_data = data[int(key_str)]
        elif isinstance(data, dict):
            # Per i dict usiamo la chiave stringa originale
            next_data = data.get(key_str)
        else:
             # Opzionale: Aggiungere qui getattr per oggetti se serve
             next_data = getattr(data, key_str, default)
    except (IndexError, TypeError):
        return default

    if rest is None:
        return next_data if next_data is not None else default
    return get(next_data, rest, default)

def route(url: dict, new_part: str) -> str:
    """
    Updates the URL's path and/or adds query parameters based on the input string.
    New values overwrite existing ones with the same name.

    Args:
        url: A dict containing parts of the URL (protocol, host, port, path, query, fragment).
        new_part: The new path string (e.g., '/nuova/pagina') or a query string (e.g., '?id=100'),
                  or a combination of both (e.g., '/nuova/pagina?page=2&category=tech').

    Returns:
        The updated full URL as a string.
    """
    # Copia i dati dal dizionario URL per sicurezza
    #url = url.copy()
    url = copy.deepcopy(url)
    protocol = url.get("protocol", "http")
    host = url.get("host", "localhost")
    port = url.get("port")
    path = url.get("path", [])
    query_params = url.get('query', {})
    fragment = url.get("fragment", "")

    # Usa un dizionario per i segnaposto, mappando le stringhe speciali a token unici
    '''placeholders = {
        '${this.value}': '__PLACEHOLDER_THIS_VALUE__',
    }'''
    
    # Sostituisci i caratteri speciali con i segnaposto prima di decodificare
    
    #for special_string, placeholder in placeholders.items():
    #    new_part = new_part.replace(special_string, placeholder)

    # Analizza la stringa di input per separare il percorso dalla query
    parsed_new_part = urlparse(new_part)

    # Aggiorna il percorso se la stringa di input contiene un percorso
    if parsed_new_part.path:
        path = [p for p in parsed_new_part.path.split('/') if p]

    # Aggiorna i parametri di query se la stringa di input contiene una query
    '''if parsed_new_part.query:
        query_params = {}
        [query_params.setdefault(k, []).append(v) for k, v in (param.split('=', 1) for param in parsed_new_part.query.split('&') if '=' in param)]
        #new_params = parse_qs(parsed_new_part.query, keep_blank_values=True)
        # Unisce e sovrascrive i parametri esistenti con i nuovi
        for key, value in query_params.items():
            query_params.setdefault(key, []).append(value)
            #query[key] = [value[-1]]'''
    
    if parsed_new_part.query:
        [query_params.setdefault(k, []).append(v) for k, v in (param.split('=', 1) for param in parsed_new_part.query.split('&') if '=' in param)]
        for key, value in query_params.items():
            # ?org=colosso&org=${this.value}
            # ?org=${this.value}&org=colosso
            # ?org=${this.value}
            #query_params.setdefault(key, [])
            #query_params[key].reverse()
            
            #query_params[key] = [query_params[key][-1]]
            #if "${" in query_params[key][-1]:
            #    query_params[key].reverse()
            #query[key] = [value[-1]]
            pass
    else:
        #query_params = query_
        pass

    # Ricostruisci la query string con SOLO l'ultimo valore per ogni chiave
    query_parts = []
    query_string = ""
    for key, values in query_params.items():
        if values:  # prendi solo l'ultimo elemento
            query_parts.append(f"{key}={values[-1]}")
    query_string = "&".join(query_parts)

    base_url = ""
    '''# Ricostruisce l'URL completo
    base_url = f"{protocol}://{host}"
    if port:
        base_url += f":{port}"'''
    if path:
        base_url += "/" + "/".join(path)

    # Codifica i parametri di query
    if query_string:
        #encoded_query = urlencode(query, doseq=True)
        #base_url += f"?{encoded_query}"
        base_url += f"?{query_string}"
    
    if fragment:
        base_url += f"#{fragment}"

    #for key, value in placeholders.items():
    #    base_url = base_url.replace(value,key)

    return base_url

async def _execute_step_internal(action_step,context=dict()) -> Any:
    """
    Esegue un'azione (funzione, args, kwargs) fornita da 'step', 
    senza il contesto completo del pipe.
    """
        
    fun = action_step[0]
    args = action_step[1] if len(action_step) > 1 else ()
    kwargs = action_step[2] if len(action_step) > 2 else {}
    if isinstance(fun, str):
        #Funzione da stringa (context lookup)
        #print("funzione##############################################à",context,fun)
        fun = get({'@':context}, fun)
    
    aaa = []
    for arg in args:
        # Modifica: Controllo più rigoroso per lookup su contesto
        if isinstance(arg, str) and arg.strip().startswith("@"):
            aaa.append(get({'@':context}, arg))
        else:
            aaa.append(arg)
    args = tuple(aaa)

    kkk = {}
    for k, v in kwargs.items():
        if isinstance(v, str) and v.strip().startswith("@"):
            kkk[k] = get({'@':context}, v)
        else:
            kkk[k] = v
    kwargs = kkk

    if not isinstance(action_step, tuple) or len(action_step) < 2 or not callable(action_step[0]):
        # Miglioramento context errore
        step_repr = str(action_step)[:100]
        raise TypeError(f"L'azione fornita non è un formato step valido. Action: {step_repr}", fun, args, kwargs)

    if asyncio.iscoroutinefunction(fun):
        # Inspect the function to see if it accepts 'context'
        sig = inspect.signature(fun)
        if 'context' in sig.parameters:
            kwargs['context'] = context
        result = await fun(*args, **kwargs)
    else:
        # Inspect the function to see if it accepts 'context'
        sig = inspect.signature(fun)
        if 'context' in sig.parameters:
            kwargs['context'] = context
        result = fun(*args, **kwargs)

    # Auto-wrapping in Transaction se non lo è già
    if isinstance(result, dict) and 'success' in result and ('data' in result or 'errors' in result):
        return result
    
    return {"success": True, "data": result, "errors": []}
        

def step(func, *args, **kwargs):
    return (func, args, kwargs)

async def pipe(*stages,context=dict()):
    """
    Orchestra un flusso dichiarativo, chiamando le funzioni in sequenza.
    Ogni stage deve essere fornito nel formato: (funzione, args_tuple, kwargs_dict).
    Le sorgenti supportate sono: 'input', 'output' o valori letterali.
    """
    context |= {'outputs': []}
    stage_index = 0
    final_output = None
    
    with log_block(f"Pipe with {len(stages)} stages", level="TRACE", emoji="🚀"):
        # --- OpenTelemetry Hook ---
        telemetry_list = getattr(container, 'telemetry', lambda: [])()
        
        with MultiSpanContext(telemetry_list, "pipe_execution"):
            for stage_tuple in stages:
                stage_index += 1
                step_name = getattr(stage_tuple[0], '__name__', str(stage_tuple[0]))
                
                # Utilizza timed_block o log_block per ogni stage per tracciare i tempi
                with log_block(f"Step {stage_index}: {step_name}", level="TRACE", emoji="👣"):
                    outcome = await _execute_step_internal(stage_tuple, context)
                
                if isinstance(outcome, dict) and outcome.get('success') is True and 'data' in outcome:
                    data_to_pass = outcome['data']
                else:
                    data_to_pass = outcome
                
                final_output = data_to_pass
                # Tronca l'output per evitare log giganti se necessario (opzionale, qui manteniamo raw)
                context['outputs'].append(data_to_pass)
            
    return final_output

class MockSpanContext:
    def __enter__(self): return self
    def __exit__(self, *args): pass

class MultiSpanContext:
    """Gestisce l'apertura di più span per una lista di provider di telemetria."""
    def __init__(self, telemetry_list, span_name, attributes=None):
        self.telemetry_list = telemetry_list or []
        self.span_name = span_name
        self.attributes = attributes
        self.spans = []

    def __enter__(self):
        for tel in self.telemetry_list:
            if hasattr(tel, 'start_span'):
                span = tel.start_span(self.span_name, attributes=self.attributes)
                if hasattr(span, '__enter__'):
                    span.__enter__()
                self.spans.append(span)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for span in reversed(self.spans):
            if hasattr(span, '__exit__'):
                span.__exit__(exc_type, exc_val, exc_tb)

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
        if isinstance(data, dict) and 'success' in data and 'data' in data:
            return data
            
        return {"success": True, "data": data, "errors": []}
    except Exception as e:
        return {
            "success": False, 
            "data": None, 
            "errors": [{"type": type(e).__name__, "message": str(e)}]
        }

async def branch(on_success: Callable, on_failure: Callable, context=dict()):
    """
    Instrada il flusso basandosi sul campo 'ok' del risultato (result.json).
    
    Args:
        outcome: Il dizionario risultato da analizzare.
        on_success: Funzione da chiamare se ok=True (riceve outcome['data']).
        on_failure: Funzione da chiamare se ok=False (riceve outcome['error']).
        
    Returns:
        Il risultato della funzione chiamata (on_success o on_failure).
    """
    outcome = context.get('outputs', [None])[-1]
    
    with log_block("Branching", level="TRACE", emoji="📂"):
        if isinstance(outcome, dict) and outcome.get('success') is True:
            return await _execute_step_internal(on_success, context)
        else:
            return await _execute_step_internal(on_failure, context)

async def retry(func , max_attempts: int = 3, retryable_errors: List[str] = None, context=dict()) -> Dict[str, Any]:
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
        transaction = await _execute_step_internal(func,context)
            
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

async def guard(condition: str, context=dict()) -> Optional[Dict[str, Any]]:
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
        safe_context = context
        if isinstance(context, dict):
             # Crea una copia safe per MistQL rimuovendo oggetti non serializzabili
             # o convertendoli in stringhe.
             # Si può fare una copia shallow e rimpiazzare le chiavi problematiche note
             # oppure una sanitizzazione ricorsiva se necessario.
             # Per ora sanitizziamo shallow 'outputs' se presente
            safe_context = context.copy()
            if 'outputs' in safe_context:
                safe_outputs = []
                for out in safe_context['outputs']:
                    if isinstance(out, (dict, list, str, int, float, bool, type(None))):
                        safe_outputs.append(out)
                    else:
                        safe_outputs.append(str(out))
                safe_context['outputs'] = safe_outputs
            
            # Sanitizza eventuali altri oggetti non serializzabili al primo livello
            for k, v in safe_context.items():
                if not isinstance(v, (dict, list, str, int, float, bool, type(None))):
                    safe_context[k] = str(v)

        if type(context) not in [str, int, float, bool,dict,list]:
            safe_context = str(context)
            
        wrapped_context = {'@': safe_context}
        #print("condition---------------------",condition)
        result = mistql.query(condition, wrapped_context)
        #print("result---------------------",result,condition)
        
        # Se il risultato è truthy, la condizione è soddisfatta
        if result:
            return {
                "success": True, 
                "data": context, 
                "errors": []
            }
        else:
            # Condizione non soddisfatta
            return {
                "success": False, 
                "data": context, 
                "errors": [{
                    #"message": error_message,
                    "condition": condition,
                    "evaluated_result": result,
                    "context": safe_context # Logghiamo il contesto safe per debug
                }]
            }
    except Exception as e:
        # Errore nell'esecuzione della query MistQL
        return {
            "success": False,
            "data": None,
            "errors": [{
                "message": f"Errore nella valutazione MistQL: {str(e)}",
                "condition": condition,
                "exception": type(e).__name__
            }]
        }

async def fallback(primary_func, secondary_func, context=dict()) -> Dict[str, Any]:
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
    transaction = await _execute_step_internal(primary_func,context)
    if transaction['success']:
        return transaction
        
    # Prova secondaria
    transaction = await _execute_step_internal(secondary_func,context)  
    return transaction

async def switch(cases, context=dict()):
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
        #print(condition,action_step)
        guard_result = await guard(condition, context)
        #print("guard_result---------------------",condition,guard_result)
        success = guard_result.get("success", False)
        
        if success:
            return await _execute_step_internal(action_step,context)

async def work(workflow, context=dict()):
    """
    Esegue un workflow come una transazione radice, verificando i permessi tramite Defender.
    Se Defender non è disponibile (es. bootstrap), consente l'esecuzione solo per task di sistema.
    """
    # 1. Setup Root Transaction
    current_tx_id, tx_token = _setup_transaction_context()
    
    if context is None:
        context = {}
    
    # Assicura che 'identifier' nel contesto corrisponda al Transaction ID
    if 'identifier' not in context:
        context['identifier'] = current_tx_id

    try:
        # 2. Permission Check (Defender Guard)
        authorized = False
        defender_service = None
        
        # Tenta di recuperare il servizio Defender dal container
        if hasattr(container, 'defender'):
            try:
                defender_service = container.defender()
            except Exception:
                defender_service = None
        
        if defender_service:
            # Defender è attivo: Verifica Permessi
            wf_name = getattr(workflow, '__name__', str(workflow))
            check_ctx = context | {'workflow_name': wf_name, 'transaction_id': current_tx_id}
            
            # Delega la verifica al Defender
            authorized = await defender_service.check_permission(**check_ctx)
            if not authorized:
                framework_log("WARNING", f"Accesso negato da Defender per {wf_name}", emoji="⛔", data=check_ctx)

        else:
            # Defender non attivo: Bypass di Sistema (Bootstrap)
            # Consenti se flaggato come sistema o se è il bootstrap stesso
            is_system = context.get('system', False) or context.get('user') == 'system'
            wf_name = getattr(workflow, '__name__', str(workflow))
            
            if is_system or 'bootstrap' in wf_name:
                authorized = True
                framework_log("DEBUG", f"Defender offline: Accesso System concesso per {wf_name}.", emoji="🛡️")
            else:
                authorized = False
                framework_log("ERROR", f"Defender offline: Accesso User negato per {wf_name}.", emoji="⛔")

        if not authorized:
             # Genera un errore esplicito
             raise PermissionError("Accesso negato: Permessi insufficienti o Defender non disponibile.")
        
        # Esegue il workflow direttamente
        return await _execute_step_internal(workflow, context)

    except Exception as e:
        framework_log("ERROR", f"Errore avvio workflow: {e}", emoji="❌")
        raise

    finally:
        # Pulisce il contextvar per non inquinare il chiamante
        if tx_token:
            _transaction_id.reset(tx_token)

async def catch(try_step, catch_step,context=dict()):
    """
    Esegue il primo step. Se il risultato è un oggetto errore (dizionario con 'ok': False), 
    esegue il secondo step come fallback.
    """
    # Usiamo una versione interna di 'pipe' per eseguire un singolo step
    # Per semplicità, la chiameremo _execute_step
    
    # 1. Tenta di eseguire lo step principale
    try:
        outcome = await _execute_step_internal(try_step,context)
    except Exception as e:
        outcome = {'success': False, 'errors': [str(e)]}
    framework_log("WARNING", f"Eccezione catturata da catch: {outcome}", emoji="🪝")
    # 2. Verifica se è un oggetto errore ROP
    # 2. Verifica se è un oggetto errore ROP
    if isinstance(outcome, dict) and outcome.get('success') is False:
        framework_log("WARNING", f"Fallimento nello step. Esecuzione del fallback: {outcome.get('errors')}", emoji="⚠️")
        
        # Puoi anche passare l'errore al catch_step, ma per semplicità lo eseguiamo direttamente
        # Esegue lo step di fallback
        
        return await _execute_step_internal(catch_step)
    
    return outcome

async def foreach(input_list, step_to_run, context=dict()) -> List[Any]:
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
        result = await pipe(item, step_to_run,context)
        results.append(result)
        
    return results

async def batch(*steps_to_run) -> Dict[str, Any]:
    """
    Esegue una lista di step in parallelo (con asyncio.gather) e aggrega i risultati.
    Ritorna un risultato aggregato con 'ok': True solo se TUTTI gli step hanno successo.
    """
    if not steps_to_run:
        return {"success": True, "data": [], "errors": None}

    tasks = []
    
    with log_block(f"Batch with {len(steps_to_run)} steps", level="TRACE", emoji="🧬"):
        for action_step in steps_to_run:
            if hasattr(action_step, '__call__') or asyncio.iscoroutinefunction(action_step):
                 step_tuple = (action_step, (), {})
                 task = asyncio.create_task(_execute_step_internal(step_tuple))
            elif isinstance(action_step, tuple):
                 task = asyncio.create_task(_execute_step_internal(action_step))
            else:
                raise TypeError(f"batch supporta solo step (tuple) o callable, ricevuto: {type(action_step)}")
            
            tasks.append(task)
        
        # Esegue in parallelo, catturando eccezioni Python
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = []
    failures = []
    
    for r in raw_results:
        # 1. Gestione Eccezioni Python (crash della funzione)
        if isinstance(r, Exception):
            failures.append({"type": type(r).__name__, "message": str(r)})
            continue
            
        # 2. Gestione Errori Logici (ROP: dizionari con ok=False)
        if isinstance(r, dict):
            if r.get('success') is False: 
                failures.extend(r.get('errors', []))
            else:
                # Se ok=True o se non c'è la chiave ok (dato raw), lo consideriamo successo
                # Se c'è 'data', estraiamo quello, altrimenti prendiamo tutto l'oggetto
                successes.append(r.get('data', r))
        else:
            # Dato raw non dizionario
            successes.append(r)
    
    # Logica di aggregazione: Tutto OK o niente
    is_success = len(failures) == 0
    
    return {
        "success": is_success,
        "data": successes,
        "errors": failures
    }

async def race(*steps_to_run) -> Any:
    """
    Esegue più step in parallelo e restituisce IL RISULTATO del primo che completa.
    Gli altri task vengono cancellati.
    """
    if not steps_to_run:
        return None

    tasks = []
    
    # Creazione dei task (uguale a batch/fan_out)
    for action_step in steps_to_run:
        if hasattr(action_step, '__call__') or asyncio.iscoroutinefunction(action_step):
             step_tuple = (action_step, (), {})
             task = asyncio.create_task(_execute_step_internal(step_tuple))
        elif isinstance(action_step, tuple):
             task = asyncio.create_task(_execute_step_internal(action_step))
        else:
            # Se uno step non è valido, lo ignoriamo o lanciamo errore?
            # Per coerenza con batch, lanciamo errore.
             raise TypeError(f"race supporta solo step (tuple) o callable, ricevuto: {type(action_step)}")
        tasks.append(task)

    try:
        # returns a tuple (done, pending)
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Prende il risultato del vincitore
        winner_task = done.pop()
        
        # Se il vincitore ha lanciato un'eccezione, la rilanciamo o la restituiamo?
        # Qui seguiamo la logica python standard: accedendo a .result() si rilancia l'eccezione
        try:
            return winner_task.result()
        except Exception as e:
            # Se vogliamo wrappare l'errore in ROP:
            return {"success": False, "errors": [str(e)], "type": "RaceWinnerError"}

    finally:
        # Cancelliamo tutti i task ancora pendenti per non lasciarli appesi
        for task in pending:
            task.cancel()
            # Opzionale: attendere che la cancellazione sia effettiva
            # await asyncio.gather(task, return_exceptions=True)

async def retry(action_step, attempts = 3, delay = 1.0, context=dict()) -> Any:
    """
    Esegue uno step, riprovando in caso di fallimento fino a un massimo di tentativi.
    """
    last_outcome = None
    
    for attempt in range(attempts):
        framework_log("DEBUG", f"Tentativo {attempt + 1}/{attempts} per lo step...", emoji="🔄")
        
        # Esegue lo step usando l'helper interno
        outcome = await _execute_step_internal(action_step,context)
        last_outcome = outcome
        
        # Logica di successo (non è un oggetto errore ROP)
        if not (isinstance(outcome, dict) and outcome.get('success') is False):
            framework_log("DEBUG", f"Step completato al tentativo {attempt + 1}.", emoji="✅")
            return outcome
        
        # Se siamo all'ultimo tentativo, non aspettare e restituisci l'errore
        if attempt < attempts - 1:
            framework_log("WARNING", f"Fallimento. Attesa di {delay} secondi prima di riprovare.", emoji="⏳")
            await asyncio.sleep(delay)
            # Logica per l'aumento del delay (ritardo esponenziale)
            # delay *= 2 # Esempio di ritardo esponenziale

    framework_log("ERROR", f"Fallimento definitivo dopo {attempts} tentativi.", emoji="❌")
    return last_outcome

async def timeout(action_step, max_seconds = 30.0, context=dict()) -> Any:
    """
    Esegue uno step e lo annulla se supera il tempo limite specificato.
    """
    # Usiamo il meccanismo di timeout di asyncio
    try:
        # Crea un Task che esegue lo step
        task = asyncio.create_task(_execute_step_internal(action_step,context))
        
        # Attende il completamento del Task con un timeout
        return await asyncio.wait_for(task, timeout=max_seconds)
        
    except asyncio.TimeoutError:
        # Il Task è scaduto: restituisce un errore ROP
        return {
            "success": False,
            "errors": [f"Timeout superato: lo step non è stato completato entro {max_seconds} secondi."],
            "type": "TimeoutError"
        }
    except Exception as e:
        # Gestisce altri errori generici durante l'esecuzione del task
        return {
            "success": False,
            "errors": [f"Errore interno durante il timeout: {e}"],
            "type": "ExecutionError"
        }

async def throttle(action_step, rate_limit_ms = 1000, context=dict()) -> Any:
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

async def trigger(event_name, context=dict()) -> Dict[str, Any]:
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