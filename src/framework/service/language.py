from kink import di
import importlib
import tomli
import sys
import os
from jinja2 import Environment
import asyncio
import ast
import re
import fnmatch
from datetime import datetime, timezone
import uuid
import json
import copy
from urllib.parse import parse_qs,urlencode,urlparse
import traceback
import types # Importato per la gestione dinamica dei moduli
import inspect
import contextvars
from cerberus import Validator, TypeDefinition, errors
import hashlib
import functools
import platform
from typing import Dict, Any, Optional, List, Callable
import psutil
import socket

# Cache e stack per prevenire loop e ricaricamenti ripetuti
# Ora registrati in DI per poterli sovrascrivere / mockare facilmente.
if 'module_cache' not in di:
    di['module_cache'] = {}
if 'loading_stack' not in di:
    di['loading_stack'] = set()

if 'log_buffer' not in di:
    di['log_buffer'] = []

# Context var per propagare il transaction id nei flussi asincroni
_transaction_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('transaction_id', default=None)

def get_transaction_id() -> Optional[str]:
    """Restituisce il transaction id corrente dal contextvar, se presente."""
    return _transaction_id.get()


def set_transaction_id(tx: Optional[str]) -> None:
    """Imposta il transaction id corrente nel contextvar (pubblica API)."""
    if tx is None:
        # reset to None by setting None
        _transaction_id.set(None)
    else:
        _transaction_id.set(str(tx))

def buffered_log(level: str, message: str, emoji: str = ""):
    """Logger rudimentale che bufferizza i messaggi iniziali"""
    formatted = f"{emoji} {message}"
    di['log_buffer'].append({
        'level': level,
        'message': message,
        'emoji': emoji,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'transaction_id': get_transaction_id()
    })
    #print(formatted)  # Mantiene output semplice durante il bootstrap

def asynchronous(custom_filename: str = __file__, app_context: Optional[Dict[str, Any]] = None):
    """
    Decoratore per catturare eccezioni, generare un rapporto di debug dettagliato e loggarlo usando il logger configurato.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Stabilisce/propaga un transaction id nel contesto asincrono
            tx = None
            if 'transaction_id' in kwargs and kwargs.get('transaction_id'):
                tx = kwargs.get('transaction_id')
            elif app_context and isinstance(app_context, dict) and app_context.get('transaction_id'):
                tx = app_context.get('transaction_id')
            else:
                tx = str(uuid.uuid4())

            token = _transaction_id.set(tx)
            try:
                return await func(*args, **kwargs)
            except Exception:
                # Recupera il codice sorgente del modulo della funzione
                source_code = None
                '''try:
                    source_code = inspect.getsource(func)
                except KeyboardInterrupt:
                    print("Interruzione da tastiera (Ctrl + C).")
                except (OSError, TypeError):
                    source_code = ""'''

                source_code = await _load_resource(path="/"+custom_filename)

                # Genera il rapporto usando l'eccezione attiva
                report = analyze_exception(
                    source_code=source_code,
                    custom_filename=custom_filename,
                    app_context=app_context
                )
                # Inietta il transaction id nel report per correlazione
                report['TRANSACTION_ID'] = tx
                
                ok = await convert(report, str, 'json')

                # Buffera anche il log strutturato con il transaction id
                buffered_log("ERROR", ok, emoji="❌")

                print(ok)

                # Rilancia l'eccezione
                #raise

            finally:
                try:
                    _transaction_id.reset(token)
                except Exception:
                    pass

        return wrapper
    return decorator

def synchronous(custom_filename: str = __file__, app_context: Optional[Dict[str, Any]] = None):
    """
    Decoratore per catturare eccezioni, generare un rapporto di debug dettagliato e loggarlo usando il logger configurato.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Imposta temporaneamente il transaction id se fornito (propagazione ai task creati)
            tx = None
            if 'transaction_id' in kwargs and kwargs.get('transaction_id'):
                tx = kwargs.get('transaction_id')
            elif app_context and isinstance(app_context, dict) and app_context.get('transaction_id'):
                tx = app_context.get('transaction_id')
            elif app_context and isinstance(app_context, dict) and app_context.get('REQUEST_ID'):
                tx = app_context.get('REQUEST_ID')
            else:
                # non forziamo la generazione qui; lasciare None mantiene il comportamento attuale
                tx = None

            token = None
            if tx is not None:
                try:
                    token = _transaction_id.set(str(tx))
                except Exception:
                    token = None

            try:
                return func(*args, **kwargs)
            except Exception:
                # Recupera il codice sorgente del modulo della funzione
                source_code = None
                try:
                    source_code = inspect.getsource(func)
                except KeyboardInterrupt:
                    print("Interruzione da tastiera (Ctrl + C).")
                except (OSError, TypeError):
                    source_code = ""

                # Genera il rapporto usando l'eccezione attiva
                report = analyze_exception(
                    source_code=source_code,
                    custom_filename=custom_filename,
                    app_context=app_context
                )
                
                #exc_type, exc_value, _ = sys.exc_info()
                #error_message = f"Errore intercettato in '{func.__name__}': {type(exc_value).__name__} - {str(exc_value)}"
                #ok = await convert(report, 'str', 'json')
                ok = asyncio.run(convert(report, str, 'json'))

                print(ok)

                # Rilancia l'eccezione
                #raise
            finally:
                # Reset del contextvar se era stato impostato
                if token is not None:
                    try:
                        _transaction_id.reset(token)
                    except Exception:
                        pass

        return wrapper
    return decorator

# Backend (sync file read wrapped in async for tests)
if sys.platform != 'emscripten':
    async def _load_resource(**kwargs) -> str:
        path = kwargs.get("path", "")
        if path.startswith('/'):
            path = path[1:]
        try:
            with open(f"{path}", "r") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File non trovato: {path}")
else:
    import js
    async def _load_resource(**kwargs) -> str:
        path = kwargs.get("path", "")
        # browser-specific fetching (placeholder)
        try:
            resp = await js.fetch(path)
            return await resp.text()
        except Exception as e:
            raise FileNotFoundError(f"File non trovato (fetch fallito): {path}") from e


def _get_module_cache() -> Dict[str, types.ModuleType]:
    return di['module_cache']


def _get_loading_stack():
    return di['loading_stack']
    
class LogReportEncoder(json.JSONEncoder):
    """
    JSONEncoder personalizzato per la serializzazione di oggetti complessi 
    trovati nei log di debug e nelle tracce di errore.
    Converte qualsiasi tipo di dato non serializzabile in una stringa.
    """
    def default(self, obj):
        try:
            # 1. Tenta di usare l'implementazione predefinita della superclasse
            # Questo gestisce tutti i tipi standard (dict, list, str, int, float, bool, None)
            return super().default(obj)
        except TypeError:
            # 2. Se la serializzazione standard fallisce (TypeError: ... is not JSON serializable)
            # converti l'oggetto nella sua rappresentazione in stringa.
            # Questo è il fallback universale.
            
            # Per oggetti che hanno un metodo to_dict/to_json, potresti aggiungerlo qui:
            # if hasattr(obj, 'to_dict'):
            #     return obj.to_dict()
                
            # Fallback per tutti gli altri: usa la rappresentazione in stringa
            # Esempi: loop eventi, oggetti complessi, istanze di classi personalizzate.
            return str(obj)
    
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

async def normalize(schema, value=None, mode='full'):
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
        raise TypeError("Lo schema deve essere un dizionario valido per Cerberus.")

    # 1. Popolamento e Trasformazione Iniziale (Default, Funzioni)
    # Cerberus gestisce i 'default', ma le 'functions' richiedono un pre-processing
    processed_value = value.copy() # Lavora su una copia per non modificare l'originale

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
    print("##################",schema)
    v = Validator(schema,allow_unknown=True)

    # Permetti a Cerberus di gestire i valori di default durante la validazione
    # Cerberus gestirà 'type', 'required', 'default' e 'regex' direttamente
    if not v.validate(processed_value):
        # La validazione fallisce, Cerberus fornisce i messaggi di errore
        #errors_str = "; ".join([f"{k}: {', '.join(v)}" for k, v in v.errors.items()])
        print(f"⚠️ Errore di validazione: {v.errors}  | data:{processed_value}")
        raise ValueError(f"⚠️ Errore di validazione: {v.errors} | data:{processed_value}")

    final_output = v.document

    return final_output

def transform(data_dict, mapper, values, input, output):

    """ Trasforma un set di costanti in un output mappato. """

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

# =====================================================================
# --- Funzioni di Generazione ---
# =====================================================================

def calculate_hash_of_function(func: types.FunctionType):
    """
    Calcola un hash SHA256 stabile, svelando le funzioni decorate.
    """
    import marshal
    from inspect import unwrap
    # 🌟 PASSO CRUCIALE: Svela la funzione originale se è stata decorata
    unwrapped_func = unwrap(func)
    
    if not hasattr(unwrapped_func, '__code__'):
        raise TypeError(f"L'oggetto {func.__name__} non è ispezionabile.")

    code_obj = unwrapped_func.__code__
    
    # Costruisce la tupla con i componenti essenziali della LOGICA
    relevant_parts = (
        code_obj.co_code,
        code_obj.co_consts,
        code_obj.co_names,
        code_obj.co_varnames,
        code_obj.co_freevars,
        code_obj.co_cellvars,
        code_obj.co_argcount,
        code_obj.co_kwonlyargcount,
        code_obj.co_flags
    )
    
    serialized = marshal.dumps(relevant_parts)
    return hashlib.sha256(serialized).hexdigest()

def estrai_righe_da_codice(codice_sorgente: str, riga_inizio: int, riga_fine: int) -> str:
    """
    Estrae il codice sorgente tra riga_inizio (inclusa) e riga_fine (inclusa).
    
    ATTENZIONE: i numeri di riga sono basati su 1 (come in un editor).
    Gli indici delle liste in Python partono da 0.
    """
    
    # 1. Dividi il codice in una lista di righe
    righe = codice_sorgente.splitlines()
    
    # 2. Converti i numeri di riga (base 1) in indici di lista (base 0)
    # L'indice iniziale è riga_inizio - 1
    indice_inizio = riga_inizio - 1
    
    # L'indice finale è riga_fine (perché lo slicing [start:end] esclude 'end')
    indice_fine = riga_fine
    
    # 3. Estrai la porzione della lista
    righe_selezionate = righe[indice_inizio:indice_fine]
    
    # 4. Ricongiungi le righe selezionate in una singola stringa, 
    #    mantenendo il carattere di nuova riga ('\n')
    codice_estratto = '\n'.join(righe_selezionate)
    
    return codice_estratto

@asynchronous()
async def generate_checksum(
    main_path: str, 
) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    """
    Genera il contratto JSON, mappando ogni metodo in un oggetto annidato
    che distingue l'hash di produzione da quello di test.
    """
    # 1. Caricamento e Analisi
    contract_path = main_path.replace('.py', '.test.py')
    main_code = await _load_resource(path=main_path)
    contract_code = await _load_resource(path=contract_path)
    
    if not main_code or not contract_code:
        buffered_log("INFO", "Impossibile caricare i file sorgente o di test ({main_path} / {contract_path}).")
        return {}

    main_module = analyze_module(main_code, main_path)
    contract_ana = analyze_module(contract_code, contract_path)
    contract_hashes = {} # Struttura interna modificata
    #Module
    '''for x,data in contract_ana['TestModule'].get('data',{}).get('methods').items():
        target_name = '__module__' if x == 'TestModule' else x.replace('test_', '')
        #print(x,estrai_righe_da_codice(contract_code,data.get('lineno',0),data.get('end_lineno',0)),'\n++\n')
        if target_name not in main_module:
            continue
        data = main_module[target_name].get('data',{})
        #print(target_name,estrai_righe_da_codice(main_code,data.get('lineno',0),data.get('end_lineno',0)),'\n++\n')
        hash_prod = await convert(estrai_righe_da_codice(main_code,data.get('lineno',0),data.get('end_lineno',0)) ,str,'hash')
        hash_test = await convert(estrai_righe_da_codice(contract_code,data.get('lineno',0),data.get('end_lineno',0)) ,str,'hash')
        contract_hashes[target_name] = {x.replace('test_',''):{'production':hash_prod,'test':hash_test}}
    # 2. Itera e Genera Hash
    #print(contract_ana,'<<<-------------###############################################')
    
    for mname in contract_ana:
        data = contract_ana.get(mname)
        # Continua (salta l'iterazione) SE NON è un dizionario OPPURE se è un dizionario ma NON ha la chiave 'type'.
        if not (isinstance(data, dict) and 'type' in data and data['type'] == 'class') and mname != '__module__':
            continue
        methods = data.get('data', {}).get('methods', {})
        for method_name, method_data in methods.items():
            if not method_name.startswith('test_'):
                continue

            target_name = '__module__' if mname == 'TestModule' else mname.replace('Test', '')
            is_module_level_test = (mname == 'TestModule')
            
            # Recupero target di produzione e test
            target_prod = main_module if is_module_level_test else main_module.get(target_name, {})
            target_test = contract_ana.get(mname, {})
            
            if not target_test or not target_prod:
                continue

            method_name_clean = method_name.replace('test_', '')
            method_contract: Dict[str, str] = {}
            
            # A. Hash del Metodo di Test
            test_method_data = target_test.get('data', {}).get('methods', {}).get(method_name, {})
            if test_method_data:
                test_code = estrai_righe_da_codice(
                    contract_code,
                    test_method_data.get('lineno', 0),
                    test_method_data.get('end_lineno', 0)
                )
                method_contract['test'] = await convert(test_code, str, 'hash')
            
            # B. Hash del Metodo di Produzione
            prod_method_data = target_prod.get('data', {}).get('methods', {}).get(method_name_clean, {})
            if prod_method_data:
                prod_code = estrai_righe_da_codice(
                    main_code,
                    prod_method_data.get('lineno', 0),
                    prod_method_data.get('end_lineno', 0)
                )
                method_contract['production'] = await convert(prod_code, str, 'hash')

            # Aggiunge il contratto solo se almeno un hash è presente
            if method_contract:
                print(target_name,method_name_clean,method_contract)
                #contract_hashes[target_name] = method_contract
                '''
            
    # 2. Itera e Genera Hash (Logica Unificata)
    for mname, data in contract_ana.items():
        # Continua (salta l'iterazione) SE NON è un dizionario OPPURE se è un dizionario ma NON ha la chiave 'type'
        # E NON è il modulo di base (mname != '__module__')
        # Il controllo 'mname != '__module__'' è implicito nelle classi, ma esplicito per il caso base.
        is_class = isinstance(data, dict) and 'type' in data and data['type'] == 'class'
        
        # Se non è una classe e non è il modulo di base, salta.
        if not is_class and mname != '__module__':
            continue
            
        # Per coerenza, se è il modulo di base, usa i dati di contract_ana (che potrebbe avere info a livello di modulo)
        # Altrimenti usa i dati della classe/modulo specifico.
        methods = data.get('data', {}).get('methods', {})
        
        # Se mname è '__module__', cerca i metodi a livello di modulo in contract_ana['__module__']
        # Il primo blocco si occupava solo di contract_ana['TestModule'] che è un caso specifico
        
        # Usa TestModule per la logica di estrazione dei metodi
        if mname == 'TestModule':
            # Questo caso gestisce il primo blocco di codice fornito, usando la logica del secondo.
            target_name = '__module__'
        else:
            # Questo caso gestisce le classi di test.
            # Rimuove 'Test' dalla classe di test per trovare la classe di produzione
            target_name = mname.replace('Test', '')
        
        # -------------------------------------------------------------------------------------
        
        for method_name, method_data in methods.items():
            if not method_name.startswith('test_'):
                continue

            method_name_clean = method_name.replace('test_', '')
            is_module_level_test = (mname == 'TestModule' or target_name == '__module__')
            
            # Recupero target di produzione e test
            # Se è un test a livello di modulo, il target di produzione è 'main_module'
            target_prod = main_module if is_module_level_test and method_name_clean in main_module else main_module.get(target_name, {})
            # Il target di test è sempre il modulo/classe corrente (data)
            target_test = data
            
            # Gestione del caso in cui i metodi sono direttamente nel modulo
            if is_module_level_test:
                # Qui cerchiamo la funzione di produzione direttamente in main_module
                prod_data_source = target_prod
                prod_method_data = prod_data_source.get(method_name_clean, {}).get('data',{})
            else:
                # Qui cerchiamo il metodo nella classe di produzione (target_prod)
                prod_data_source = target_prod
                prod_method_data = prod_data_source.get('data', {}).get('methods', {}).get(method_name_clean, {})
            
            # Dati del metodo di test (usiamo sempre method_data che viene dal ciclo for)
            test_method_data = method_data
            
            if not test_method_data or not prod_method_data:
                continue # Non abbiamo dati di test o di produzione validi, salta

            method_contract: Dict[str, str] = {}
            
            # A. Hash del Metodo di Test
            test_code = estrai_righe_da_codice(
                contract_code,
                test_method_data.get('lineno', 0),
                test_method_data.get('end_lineno', 0)
            )
            method_contract['test'] = await convert(test_code, str, 'hash')
            
            # B. Hash del Metodo di Produzione
            prod_code = estrai_righe_da_codice(
                main_code,
                prod_method_data.get('lineno', 0),
                prod_method_data.get('end_lineno', 0)
            )
            method_contract['production'] = await convert(prod_code, str, 'hash')

            # Aggiunge il contratto solo se almeno un hash è presente
            if method_contract:
                # Inizializza il dizionario per target_name se non esiste
                if target_name not in contract_hashes:
                    contract_hashes[target_name] = {}
                
                # Assegna il dizionario degli hash al nome del metodo pulito
                contract_hashes[target_name][method_name_clean] = method_contract
            
    # 3. Scrittura JSON e Ritorno
    json_path = main_path.replace('.py', '.contract.json')
    json_content = json.dumps(contract_hashes, indent=4)
    # await backend(path=json_path, content=json_content, mode='w') 

    buffered_log("INFO", f"✅ Generato e scritto il contratto JSON in {json_path}")
    
    # Ritorno del formato finale a 5 livelli
    return {main_path: contract_hashes}

def analyze_function_calls(func: types.FunctionType) -> set[str]:
    """Analizza una funzione e restituisce i nomi di tutte le funzioni chiamate al suo interno."""
    
    source_code = inspect.getsource(func)
    tree = ast.parse(source_code)
    called_names: set[str] = set()

    class CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Cerca le chiamate dirette (es. 'B()')
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            # Cerca le chiamate a metodi (es. 'self.method()')
            elif isinstance(node.func, ast.Attribute):
                # Potrebbe essere un metodo o una chiamata a un modulo/oggetto esterno
                if isinstance(node.func.value, ast.Name):
                    called_names.add(node.func.value.id + '.' + node.func.attr)
                else:
                    called_names.add(node.func.attr) # solo il nome del metodo/attributo
            
            # Continua la visita dei nodi interni (argomenti, ecc.)
            self.generic_visit(node)

    visitor = CallVisitor()
    visitor.visit(tree)
    return called_names

def map_dependencies(module: types.ModuleType):
    """Crea la mappa delle dipendenze: {funzione_pubblica: {dipendenze_chiamate}}."""
    dependency_map = {}
    
    # Itera su tutti i membri del modulo
    for name, member in inspect.getmembers(module):
        # Filtra solo le funzioni pubbliche (non _nascoste) che sono definite nel modulo
        if (inspect.isfunction(member) or inspect.ismethod(member)) and \
           not name.startswith('_') and member.__module__ == module.__name__:
            
            try:
                # Analizza la funzione pubblica
                calls = analyze_function_calls(member)
                dependency_map[name] = calls
            except Exception as e:
                # Gestisce errori nel recupero del codice sorgente (es. funzioni C-built-in)
                buffered_log("ERROR", f"Errore nell'analisi AST per {name}: {e}")
                
    return dependency_map

def correlate_failure(failing_test_name: str, dependency_map: Dict[str, set[str]]):
    """
    Identifica la funzione pubblica interessata dal fallimento del test.
    
    Args:
        failing_test_name: Il nome della funzione il cui test è fallito (es. 'test_exposed_function').
    """
    # 1. Caso Semplice: Il test fallito è un test di integrazione diretto.
    # Se fallisce 'test_exposed_function', allora 'exposed_function' è il problema.
    if failing_test_name.startswith('test_'):
        target_fn_name = failing_test_name.replace('test_', '')
        
        # 2. Correlazione Indiretta: Cerca se la funzione fallita è una dipendenza
        
        # Inverti la mappa per una ricerca più veloce
        # {'_private_logic': {'exposed_function'}, ...}
        inverted_map: Dict[str, set[str]] = {}
        for caller, callees in dependency_map.items():
            for callee in callees:
                inverted_map.setdefault(callee, set()).add(caller)
        
        # Quali funzioni pubbliche chiamano la funzione fallita/instabile?
        affected_public_functions = inverted_map.get(target_fn_name, set())
        
        if affected_public_functions:
            print(f"🚨 TEST FALLITO: Il fallimento in '{target_fn_name}' ha un impatto sulle seguenti funzioni pubbliche:")
            for fn in affected_public_functions:
                print(f"   -> {fn}")
            return affected_public_functions
            
        elif target_fn_name in dependency_map:
            # Fallito il test di integrazione principale
            print(f"❌ TEST FALLITO: Fallimento diretto del test di integrazione di '{target_fn_name}'.")
            return {target_fn_name}
        
    print(f"❓ TEST FALLITO: Impossibile correlare '{failing_test_name}' a una funzione pubblica. (Potrebbe essere un test non standard)")
    return set()

genera = {
    'module': generate_checksum,
    #'timenow_utc': lambda: asyncio.sleep(0, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    'identifier': lambda: asyncio.sleep(0, str(uuid.uuid4())),
}

async def generate(data,schema=None):
    func = genera.get(schema)
    if not func:
        raise ValueError(f"Nessuna funzione di generazione per le chiavi: {schema}")
    return await func(data)

# =====================================================================
# --- Funzioni di Caricamento --- CDDF (Contract-Driven Dependency Filter)
# =====================================================================

async def _validate_and_filter_module(
    main_module: types.ModuleType, 
    path: str, 
) -> types.ModuleType:
    """
    Copia le classi e le funzioni dal main_module al filtered_module, mantenendo
    solo i membri che hanno un contratto valido e presente nel file .contract.json.
    """
    validated_members: List[str] = []

    contract_json_path = path.replace('.py', '.contract.json')
    try:
        json_content = await _load_resource(path=contract_json_path)
        external_contracts: Dict[str, Any] = await convert(json_content, dict, 'json')
        buffered_log("DEBUG", f"Contratto JSON esterno caricato da {contract_json_path}.")
    except Exception as e:
        buffered_log("WARNING", f"Nessun contratto JSON valido trovato in {contract_json_path}. Filtro hash disabilitato.", e)
        external_contracts = {}

    contract_path = path.replace('.py', '.test.py')
    contract_code = await _load_resource(path=contract_path)
    contract_ana = analyze_module(contract_code, contract_path)
    contract_module = await resource(path=contract_path)

    exports_map = getattr(contract_module, 'exports', {}) if isinstance(getattr(contract_module, 'exports', None), dict) else {}
    if exports_map:
        buffered_log("DEBUG", f"🔐 exports trovato in {path}: {list(exports_map.keys())}")
    else:
        buffered_log("WARNING", "⚠️ Nessun 'exports' dichiarato: nessun membro sarà esposto automaticamente.")

    # Build map of test-targeted methods: {TargetName: {method1, method2}}
    contract_methods_by_name: Dict[str, set[str]] = {
        ('__module__' if mname == 'TestModule' else mname.replace('Test', '')):
            {tn.replace('test_', '') for tn in (data.get('data', {}).get('methods', {}) or {}).keys() if tn.startswith('test_')}
        for mname, data in contract_ana.items() if isinstance(data, dict)
    }

    # Validate hashes (compact loop): produce contract_validated_methods only for methods with matching hashes
    contract_validated_methods = {}

    ccc = await generate_checksum(path)

    for tgt, group in (external_contracts or {}).items():
        if not isinstance(group, dict):
            continue
        prod_obj = main_module if tgt == '__module__' else getattr(main_module, tgt, None)
        test_obj = getattr(contract_module, 'TestModule' if tgt == '__module__' else f'Test{tgt}', None)
        if not prod_obj or not test_obj:
            buffered_log("WARNING", f"Oggetto produzione/test mancante per contratto: {tgt}")
            continue

        valid = {
            m for m, hashes in group.items()
            if isinstance(hashes, dict) and 'production' in hashes and 'test' in hashes
                for _ in [0]
                if (getattr(prod_obj, m, None) is not None and getattr(test_obj, f'test_{m}', None) is not None)
                and (lambda p, t, s_p=hashes['production'], s_t=hashes['test']: (calculate_hash_of_function(p) == s_p and calculate_hash_of_function(t) == s_t))(getattr(prod_obj, m), getattr(test_obj, f'test_{m}'))
        }
        
        for m, hashes in group.items():
            # 1. Filtro iniziale: verifica che 'hashes' sia un dict e contenga le chiavi necessarie
            if not (isinstance(hashes, dict) and 'production' in hashes and 'test' in hashes):
                continue
            
            # 2. Ottiene i membri
            prod_func = getattr(prod_obj, m, None)
            test_func = getattr(test_obj, f'test_{m}', None)
            
            # 3. Filtro di esistenza: verifica che i membri esistano
            if prod_func is None or test_func is None:
                print(f"DEBUG: Membro '{m}' non trovato in prod o test. Saltato.")
                continue
            
            # Estrai gli hash di riferimento
            expected_prod_hash = hashes['production']
            expected_test_hash = hashes['test']

            # Calcola gli hash correnti
            current_prod_hash = ccc.get(path,{}).get(tgt,{}).get(m,{}).get('production','')
            current_test_hash = ccc.get(path,{}).get(tgt,{}).get(m,{}).get('test','')
            
            # **********************************************
            # 🔥 Punti in cui viene eseguita la stampa degli hash (Aggiunti come richiesto)
            '''print("---")
            print(f"Membro: {m}")
            print(prod_func)
            print(f"Hash Production (Atteso): {expected_prod_hash}")
            print(f"Hash Production (Corrente): {current_prod_hash}")
            print(test_func)
            print(f"Hash Test (Atteso): {expected_test_hash}")
            print(f"Hash Test (Corrente): {current_test_hash}")'''
            # **********************************************
            
            # 4. Filtro di validazione hash
            if current_prod_hash == expected_prod_hash and current_test_hash == expected_test_hash:
                valid.add(m)
        
        if valid:
            contract_validated_methods[tgt] = valid
    #print(valid,contract_validated_methods,contract_methods_by_name,'###########')
    buffered_log("DEBUG", f"🔍 Avvio filtro: membri mantenuti se presenti in {contract_json_path} e/o testati.")

    # Compute allowed exports based on exports_map + presence of tests/validated methods
    allowed_exports = {
        public 
        for public, priv in exports_map.items()
        for candidate in [public] + ([priv] if isinstance(priv, str) else [])
        if hasattr(main_module, candidate) and (
            (inspect.isclass(getattr(main_module, candidate)) and (contract_methods_by_name.get(candidate) or contract_validated_methods.get(candidate))) or
            (inspect.isfunction(getattr(main_module, candidate)) and (candidate in contract_methods_by_name.get('__module__', {}) and candidate in contract_validated_methods.get('__module__', {})))
        )
    }
    buffered_log("DEBUG", f"🔍 Avvio filtro: membri mantenuti se presenti in {allowed_exports} e/o testati.")
    # Create filtered module and populate only allowed exports
    filtered_module = types.ModuleType(f"filtered:{main_module.__name__}")
    if hasattr(main_module, '__file__'):
        filtered_module.__file__ = main_module.__file__

    '''buffered_log("DEBUG", f"🔗 Copia dei moduli importati per il contesto di {path}...")
    for name, member in inspect.getmembers(main_module):
        # Condizione 1: È un modulo importato?
        if inspect.ismodule(member):
            # Condizione 2: Non è un modulo interno (built-in) o il modulo genitore stesso?
            # Questo evita di copiare oggetti interni di Python (es. '__builtins__') 
            # o il modulo che stiamo filtrando.
            if name not in sys.builtin_module_names and name not in ['__file__', '__name__', '__package__', '__loader__', '__spec__', main_module.__name__]:
                # Condizione 3: Non inizia con un underscore nascosto (se non vuoi copiare importazioni "private")
                if not name.startswith('_'): 
                    setattr(filtered_module, name, member)
                    buffered_log("DEBUG", f"   > Copiato modulo di dipendenza: {name}")'''

    if exports_map:
        for public_name, private_spec in exports_map.items():
            private_name = private_spec if isinstance(private_spec, str) else public_name
            if public_name not in allowed_exports:
                buffered_log("DEBUG", f"Export ignorato: {public_name} -> {private_name}")
                continue
            if not hasattr(main_module, private_name):
                buffered_log("WARNING", f"Export dichiarato ma non trovato nel modulo: {private_name} (dichiarato come {public_name})")
                continue

            member = getattr(main_module, private_name)
            if inspect.isclass(member):
                # shallow clone of class attributes, preserving special/protected methods
                attrs = {k: v for k, v in member.__dict__.items()}
                attrs['__module__'] = filtered_module.__name__
                FilteredClass = type(member.__name__, member.__bases__, attrs)
                setattr(filtered_module, public_name, FilteredClass)
                validated_members.append(public_name)

                # remove methods not in validated set (but keep specials and protected)
                valid_set = contract_validated_methods.get(member.__name__, set()) or contract_methods_by_name.get(member.__name__, set())
                for attr_name, _ in inspect.getmembers(FilteredClass, inspect.isfunction):
                    if attr_name.startswith('__') and attr_name.endswith('__'):
                        continue
                    if attr_name.startswith('_'):
                        continue
                    if attr_name not in valid_set:
                        try:
                            delattr(FilteredClass, attr_name)
                        except Exception:
                            pass
                    else:
                        validated_members.append(f"{public_name}.{attr_name}")

            elif inspect.isfunction(member) or not inspect.isclass(member):
                setattr(filtered_module, public_name, member)
                validated_members.append(public_name)
    else:
        buffered_log("WARNING", "⚠️ Nessun 'exports' dichiarato: nessun membro sarà esposto dal modulo filtrato.")

    buffered_log("INFO", f"✅ Validazione e filtro riusciti per {path}. Membri esposti: {validated_members}")
    return filtered_module

def resolve_path(resource_path: str | None) -> str:
    """Normalizza e aggiunge il prefisso 'src/' al percorso della risorsa."""
    resource_path = (resource_path or "").lstrip('/')
    if resource_path.startswith('application/') or resource_path.startswith('framework/') or resource_path.startswith('infrastructure/'):
        return os.path.normpath(os.path.join('src', resource_path))
    return os.path.normpath(resource_path)

async def _load_dependencies(module: types.ModuleType,dependencies) -> None:
    """Risolve le dipendenze 'imports' definite in un modulo."""
    
    for key, import_path in dependencies.items():
        # Normalizza percorso usato come chiave cache (stesso formato di _load_python_module)
        cache_key = import_path
        # Se è già nel cache, riutilizza (DEBUG)
        if import_path.endswith(".py") and cache_key in di['module_cache']:
            value = di['module_cache'][cache_key]
            setattr(module, key, value)
            buffered_log("DEBUG", f"♻️ Cache hit per dipendenza '{key}' da {cache_key}")
            continue

        try:
            imported_content = await _load_resource(path='src/'+import_path)
        except FileNotFoundError:
            buffered_log("WARNING", f"⚠️ Dipendenza non trovata: {import_path}")
            continue
        value: Any
        if isinstance(imported_content, str) and import_path.endswith(".json"):
            try:
                value = await convert(imported_content, 'dict', 'json')
            except Exception:
                value = json.loads(imported_content)
        elif import_path.endswith(".py"):
            # carica come modulo dinamico (salvato nella cache dentro _load_python_module)
            value = await _load_python_module(key, import_path, imported_content)
        else:
            value = imported_content
        setattr(module, key, value)
        buffered_log("DEBUG", f"📦 Dipendenza '{key}' caricata da {import_path}")

async def _load_python_module(name: str, path: str, code: str) -> types.ModuleType:
    """Crea ed esegue dinamicamente un modulo Python con le variabili globali necessarie."""
    module_name = f"{path}"
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__source__ = code
    module.__dict__['language'] = di['module_cache'].get('language')
    
    try:
        dependencies = analyze_module(code, path)
        
        dependencies = dependencies.get('imports',{}).get('value',{})
        buffered_log("INFO", f"🔍 Dipendenze trovate in {path}: {dependencies}")
        await _load_dependencies(module,dependencies.copy())
        # 2. Compila il codice con il nome del file
        compiled_code = compile(code, module_name, 'exec')
        exec(compiled_code, module.__dict__)
        # salva nel cache globale per riusi futuri (evita ricaricamenti ripetuti)
        di['module_cache'][path] = module
    except Exception as e:
        raise ImportError(f"Esecuzione modulo Python fallita per {path}: {e}") from e
    return module

async def resource(path: str | None = None, **kwargs) -> Any:
    """
    Carica una risorsa (JSON o modulo Python) e ne valida il contratto.
    
    Argomenti:
        lang (str): La lingua da iniettare nei moduli Python.
        path (str | None): Il percorso della risorsa.
    """
    resource_path = resolve_path(path)
    content = await _load_resource(path=resource_path)
    if resource_path.endswith(".json"):
        buffered_log("INFO", f"📄 Caricamento e parsing JSON da {resource_path}... type={type(content)}")
        return await convert(content, dict, 'json')
    
    if resource_path.endswith(".py"):
        # Notare che `lang` viene passato qui
        main_module = await _load_python_module("main_module", resource_path, content)
        if resource_path.endswith(".test.py"):
            return main_module
        # La funzione di validazione è astratta/esterna
        filtered_module = await _validate_and_filter_module(main_module, resource_path)
        buffered_log("DEBUG", f"📦 Modulo Python caricato e validato da {resource_path}.")
        return filtered_module
    buffered_log("WARNING", f"⚠️ Tipo di risorsa non supportato per {resource_path}. Restituito contenuto grezzo.")
    return content

async def load_di_entry(**constants: Any) -> None:
    """
    Carica una risorsa specificata in 'constants' e la registra nel container DI globale.

    La logica di registrazione è basata sulla configurazione:
    - Se 'dependency_keys' è presente, registra una factory (Manager) per l'istanziamento lazy.
    - Altrimenti, istanzia subito la risorsa e la aggiunge a una lista (Provider).

    :param lang: La lingua da iniettare nella funzione 'resource'.
    :param constants: La configurazione della risorsa da caricare.
    """
    # 1. Estrazione dei parametri di configurazione
    path: str = constants.get('path', '')
    service_name: str = constants.get('service', constants.get('name', '')) 
    attribute_name: str = constants.get('adapter', constants.get('name', ''))
    init_args: Dict[str, Any] = constants.get('payload', constants.get('config', {}))
    dependency_keys = constants.get('dependency_keys', None)

    # 2. Informazioni per il logging e validazione minima
    log_info = f"'{path}' con service '{service_name}' e attr '{attribute_name}'"

    if not path or not service_name or not attribute_name:
        buffered_log("ERROR", f"❌ Errore: Configurazioni DI insufficienti: {constants}")
        return
    
    # 3. Inizializzazione della Chiave nel DI (se assente)
    # Si usa una lambda che restituisce [] per poter collezionare Provider
    if service_name not in di:
        di[service_name] = lambda _di: []

    
        # 4. Caricamento del Modulo/Risorsa (Usando il path fornito)
        module = await resource(**constants)
        resource_class: Callable = getattr(module, attribute_name)

        # 5. Definizione della Factory/Resolver
        
        if dependency_keys:
            # --- CASO: MANAGER/FACTORY (Istanziamento lazy con dipendenze) ---
            
            dependencies: Dict[str, Any] = {}
            for dep_key in dependency_keys:
                if dep_key not in di:
                    di[dep_key] = lambda _di: []
                    
                # Salva il resolver della dipendenza
                dependencies[dep_key] = di[dep_key]
            #print(f"⏳ Caricamento Manager: '{service_name}' ({log_info}) con dipendenze {dependencies}",dependency_keys)
            di[service_name] = lambda _di: resource_class(**init_args|{'providers': dependencies})
            buffered_log("INFO", f"✅ Registrato Factory: '{service_name}' ({log_info})")

        else:
            # --- CASO: PROVIDER/SINGLETON (Istanziamento eager in una lista) ---
            if service_name not in di:
                di[service_name] = lambda di: list([])

            #provider = getattr(module, 'adapter')
            di[service_name].append(resource_class(config=init_args))
            
            buffered_log("INFO", f"✅ Aggiunto Provider a lista: '{service_name}' ({log_info})")

# =====================================================================
# --- Funzioni Principali di Analisi ---
# =====================================================================

def _get_system_info() -> Dict[str, Any]:
    """Raccoglie le informazioni chiave su CPU, RAM e Processo."""
    mem = psutil.virtual_memory()
    
    return {
        "hostname": socket.gethostname(),
        "process_id": os.getpid(),
        "cpu_cores_logical": psutil.cpu_count(),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_available_gb": round(mem.available / (1024**3), 2),
        "os_name": platform.platform(),
    }

def analyze_module(source_code: str, module_name: str) -> Dict[str, Any]:
    """Analizza il codice sorgente (AST) per ricavare la struttura del modulo,
    annidando i metodi all'interno della loro classe.
    """
    structure = {"module_name": module_name, "module_docstring": None}
    
    try:
        tree = ast.parse(source_code)
        if (docstring := ast.get_docstring(tree)):
            structure["module_docstring"] = docstring.strip()
            
        # Per una corretta gestione dello scope, dobbiamo iterare direttamente su tree.body
        # e poi usare ast.walk/ast.iter_child_nodes per l'analisi interna se necessario.
        
        # Mappa i nodi Function/Assign che sono metodi o variabili di classe 
        # per evitarli nell'analisi principale delle funzioni/variabili di modulo.
        ignored_nested_nodes = set()

        # 1. Analisi di Primo Livello (Classi e Funzioni/Variabili di Modulo)
        for node in tree.body:

            # Analisi Classi
            if isinstance(node, ast.ClassDef):
                
                class_info = {
                    "type": "class",
                    "data": {
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "docstring": ast.get_docstring(node),
                        "bases": [
                            ast.get_source_segment(source_code, base)
                            for base in node.bases
                            if ast.get_source_segment(source_code, base) is not None
                        ],
                        "methods": {}, # 🚨 NUOVA SEZIONE PER I METODI 🚨
                        "class_vars": {} # Opzionale: per le variabili di classe
                    }
                }
                
                # Iteriamo SOLO sul corpo della classe per trovare i membri interni
                for class_member in node.body:
                    
                    # Identificazione Metodi
                    if isinstance(class_member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Aggiungiamo questo nodo al set degli ignorati per l'analisi del modulo
                        ignored_nested_nodes.add(class_member)
                        
                        method_info = {
                            "type": "method",
                            "lineno": class_member.lineno,
                            "end_lineno": class_member.end_lineno,
                            "docstring": ast.get_docstring(class_member),
                            "args": [
                                a.arg for a in class_member.args.posonlyargs + class_member.args.args + [class_member.args.vararg] 
                                if a and a.arg not in ('self', 'cls') # Filtra self/cls dall'elenco argomenti
                            ],
                            # Non includiamo 'code' per semplicità, ma puoi aggiungerlo qui:
                            # "code": ast.get_source_segment(source_code, class_member) 
                        }
                        class_info["data"]["methods"][class_member.name] = method_info
                        
                    # Opzionale: Identificazione Variabili di Classe
                    elif isinstance(class_member, ast.Assign) and class_member.targets and isinstance(class_member.targets[0], ast.Name):
                        # Aggiungiamo questo nodo al set degli ignorati
                        ignored_nested_nodes.add(class_member)
                        
                        var_name = class_member.targets[0].id
                        class_info["data"]["class_vars"][var_name] = {
                            "lineno": class_member.lineno,
                            "type_ast": type(class_member.value).__name__,
                        }

                structure[node.name] = class_info # Aggiungiamo la classe completa

            # Analisi Funzioni di Modulo
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Se non è una funzione/metodo di classe (già gestita e aggiunta a ignored_nested_nodes),
                # allora è una funzione di modulo.
                if node not in ignored_nested_nodes:
                    func_info = {
                        "type": "function",
                        "data": {
                            "lineno": node.lineno,
                            "end_lineno": node.end_lineno,
                            #"code": asyncio.run(convert(ast.get_source_segment(source_code, node), str, 'hash')),
                            #"code": ast.get_source_segment(source_code, node),
                            #"code": asyncio.run(generate(ast.get_source_segment(source_code, node), 'hash')),
                            "docstring": ast.get_docstring(node),
                            "args": [a.arg for a in node.args.posonlyargs + node.args.args + [node.args.vararg] if a],
                        }
                    }
                    structure[node.name] = func_info
            
            # Analisi Variabili/Dizionari di Modulo (solo top-level Assign)
            elif isinstance(node, ast.Assign):
                # Se è un'assegnazione di modulo, e non è una variabile di classe (già ignorata)
                if node not in ignored_nested_nodes:
                    
                    # La logica del tuo codice precedente cercava solo dizionari:
                    if isinstance(node.value, ast.Dict) and node.targets and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        var_value = None
                        try:
                            var_value = ast.literal_eval(node.value)
                        except (ValueError, TypeError):
                            var_value = "Evaluation Error"
                        
                        info = {
                            "type": type(node.value).__name__,
                            "lineno": node.lineno,
                            "end_lineno": node.end_lineno,
                            "value": var_value,
                        }
                        structure[var_name] = info
                        
            # Se ci sono blocchi di controllo (if/for/ecc.) che contengono Assegnazioni/Funzioni,
            # questi devono essere gestiti con una logica ricorsiva a parte, ma per semplicità
            # e per mantenere la struttura basata su tree.body, li ignoriamo qui.

    except Exception as e:
        structure["parsing_error"] = f"Errore nell'analisi AST: {type(e).__name__} - {str(e)}"

    return structure

def truncate_value(key: str, value: Any, max_str_len: int = 256, max_list_len: int = 20) -> Any:
    """
    Tronca valori di stringa e collezioni (liste/tuple) troppo grandi
    per mantenere i log di dimensione ragionevole.
    """
    if isinstance(value, str):
        if len(value) > max_str_len:
            return f"{value[:max_str_len]}... [TRONCATA, L={len(value)}]"
        return value

    elif isinstance(value, (list, tuple, set)):
        # Tronca le collezioni
        if len(value) > max_list_len:
            truncated_items = list(value)[:max_list_len]
            # Assicurati che anche gli elementi troncati siano processati
            processed_items = [
                truncate_value("", item, max_str_len=30, max_list_len=5)
                for item in truncated_items
            ]
            
            return f"{processed_items} ... [TRONCATA, N={len(value)}]"
        
        # Processa gli elementi interni della collezione se la collezione è piccola
        return [
            truncate_value("", item, max_str_len=30, max_list_len=5)
            for item in value
        ]
        
    elif isinstance(value, dict):
        # Recursivamente applica il troncamento ai valori del dizionario
        return {
            k: truncate_value(k, v, max_str_len=max_str_len, max_list_len=max_list_len) 
            for k, v in value.items()
        }

    # Per tutti gli altri tipi (int, float, bool, oggetti piccoli), restituisci il valore così com'è.
    return value

def analyze_traceback(tb: Optional[types.TracebackType]) -> List[Dict[str, Any]]:
    """
    Estrae i frame del traceback in un formato strutturato, gestendo in modo robusto
    il recupero della riga di codice sorgente.
    """
    structured_tb = []
    current_tb = tb
    
    # Pre-carica il sorgente del modulo principale se è quello iniettato nello scenario di test
    #in_memory_source_lines = MODULE_CODE_RESOLVED.splitlines()

    while current_tb is not None:
        frame = current_tb.tb_frame
        
        # Ignora le librerie di sistema
        filename = frame.f_code.co_filename
        if "/usr/" in filename or "/local/lib/python" in filename or "python3." in filename:
            current_tb = current_tb.tb_next
            continue

        # Estrai e sanifica le variabili locali del frame corrente
        local_vars_state = {
            #k: sanitize_variable_value(k, v) 
            k: truncate_value(k, v)
            for k, v in frame.f_locals.items() 
            if not k.startswith('__') and k not in ['frame', 'frame_summary', 'current_tb', 'tb']
        }
        
        # === INIZIO FIX CRITICO PER Index/Source Error ===
        line_content = None
        
        # 1. Tentativo con traceback.FrameSummary (il più robusto per file su disco)
        try:
            # lookup_line=True forza la ricerca della riga dal disco/modulo
            frame_summary = traceback.FrameSummary(filename, frame.f_lineno, frame.f_code.co_name, lookup_line=True)
            if frame_summary.line:
                line_content = frame_summary.line.strip()
        except Exception:
            pass 

        # 2. Fallback per codice dinamico ('<string>' o nomi di file fittizi come 'api_handler_v1.py')
        '''if line_content is None and (filename.startswith('<') or filename.endswith('api_handler_v1.py')):
            try:
                # Usa il sorgente in memoria fornito dal blocco di test
                line_content = _get_line_from_source(in_memory_source_lines, frame.f_lineno)
            except Exception:
                pass'''

        # 3. Fallback finale
        if line_content is None:
            if filename.startswith('<'):
                line_content = "SORGENTE DINAMICA NON DISPONIBILE (exec/lambda)"
            else:
                line_content = "SORGENTE NON RECUPERATA DAL DISCO/MODULO"
        
        # === FINE FIX CRITICO ===

        structured_tb.append({
            "step_filename": filename,
            "step_lineno": frame.f_lineno,
            "step_function": frame.f_code.co_name,
            "step_code_line": line_content, 
            "local_variables_state": local_vars_state
        })
        current_tb = current_tb.tb_next
    
    return structured_tb

def analyze_exception(source_code: str, custom_filename: str = "<code_in_memory>", app_context: Dict[str, Any] = None) -> Dict[str, Any]:
    
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    if exc_type is None or exc_traceback is None:
        return {"status": "Nessuna eccezione attiva trovata."}
        
    tb_list = traceback.extract_tb(exc_traceback)
    full_traceback_text = traceback.format_exception(exc_type, exc_value, exc_traceback)
    
    last_traceback = exc_traceback
    while last_traceback.tb_next:
        last_traceback = last_traceback.tb_next
    last_frame_object = last_traceback.tb_frame 
    
    raw_filename = tb_list[-1].filename
    raw_lineno = tb_list[-1].lineno
    
    source_to_analyze = source_code
    analysis_filename = custom_filename
    report_filename = raw_filename
    
    
    '''source_from_disk = await backend(raw_filename)
    source_to_analyze = source_from_disk
    analysis_filename = raw_filename
    report_filename = raw_filename'''
            
    # La riga di codice non è più recuperata qui.

    module_structure = analyze_module(source_to_analyze, analysis_filename)
    structured_tb = analyze_traceback(exc_traceback)
    
    # Recupera i dettagli dell'errore finale dal traceback strutturato (più affidabile)
    final_error_step = structured_tb[-1] if structured_tb else {
        "step_code_line": "SORGENTE NON RECUPERATA", 
        "step_lineno": raw_lineno, 
        "step_function": tb_list[-1].name
    }
    
    final_local_vars = {
         #k: sanitize_variable_value(k, v)
         k: truncate_value(k, v)
         for k, v in last_frame_object.f_locals.items() 
         if not k.startswith('__') and k not in ['last_traceback', 'last_frame_object', 'raw_lineno', 'tb_list', 'exc_traceback']
    }
    
    exception_details = {
        "exception_type": type(exc_value).__name__,
        "exception_message": str(exc_value),
        "error_location": {
            "filename": report_filename,
            "line_number": final_error_step["step_lineno"],
            "function_name": final_error_step["step_function"],
            "source_code_line": final_error_step["step_code_line"], # <- Usa il valore da structured_tb
        },
        "LOCAL_VARIABLES_STATE_FINAL_FRAME": final_local_vars,
    }
    
    debug_report = {
        "ENVIRONMENT_CONTEXT": {
            "timestamp": datetime.now().isoformat(),
            "python_version": platform.python_version(),
            **_get_system_info()
        },
        "APPLICATION_CONTEXT": app_context or {"VERSION": "N/A", "USER_ID": "anonymous"},
        "EXCEPTION_DETAILS": exception_details,
        "MODULE_STRUCTURE_ANALYSIS": module_structure,
        "STRUCTURED_TRACEBACK": structured_tb[1:-1],  # Esclude il frame di analyze_exception
        #"FULL_TRACEBACK_TEXT": full_traceback_text 
    }
    
    return debug_report