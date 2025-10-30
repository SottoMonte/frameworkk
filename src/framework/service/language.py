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

def buffered_log(level: str, message: str, emoji: str = ""):
    """Logger rudimentale che bufferizza i messaggi iniziali"""
    formatted = f"{emoji} {message}"
    di['log_buffer'].append({
        'level': level,
        'message': message,
        'emoji': emoji,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    #print(formatted)  # Mantiene output semplice durante il bootstrap

# Backend (sync file read wrapped in async for tests)
if sys.platform != 'emscripten':
    async def backend(**kwargs) -> str:
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
    async def backend(**kwargs) -> str:
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

async def generate_and_validate_contract_json(
    main_path: str, 
) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    """
    Genera il contratto JSON, mappando ogni metodo in un oggetto annidato
    che distingue l'hash di produzione da quello di test.
    """
    
    # 1. Caricamento e Analisi
    contract_path = main_path.replace('.py', '.test.py')
    
    main_code = await backend(path=main_path)
    contract_code = await backend(path=contract_path)
    
    if not main_code or not contract_code:
        buffered_log("INFO", "Impossibile caricare i file sorgente o di test ({main_path} / {contract_path}).")
        return {}

    main_module = await _load_python_module("main_module_temp", main_path, main_code)
    contract_module = await _load_python_module("contract_module_temp", contract_path, contract_code)
    contract_ana = analyze_module(contract_code, contract_path)
    
    contract_hashes: Dict[str, Dict[str, Dict[str, str]]] = {} # Struttura interna modificata

    # 2. Itera e Genera Hash
    for mname, data in contract_ana.items():
        if not isinstance(data, dict):
            continue 
            
        target_name = '__module__' if mname == 'TestModule' else mname.replace('Test', '')
        is_module_level_test = (mname == 'TestModule')
        
        # Recupero target di produzione e test
        target_prod = main_module if is_module_level_test else getattr(main_module, target_name, None)
        target_test = getattr(contract_module, mname, None)
        
        if target_test is None or target_prod is None:
            continue

        # Dizionario che conterrà i contratti dei singoli metodi: {'post': {...}, 'read': {...}}
        group_contracts: Dict[str, Dict[str, str]] = {}
        test_methods_data = data.get('data', {}).get('methods', {})
        
        # Ciclo compatto
        for test_name in test_methods_data.keys():
            if not test_name.startswith('test_'):
                continue

            method_name = test_name.replace('test_', '')
            
            # Oggetto per il contratto singolo: {'production': hash, 'test': hash}
            method_contract: Dict[str, str] = {}
            
            # A. Hash del Metodo di Test
            test_fn = getattr(target_test, test_name, None)
            if test_fn:
                method_contract['test'] = calculate_hash_of_function(test_fn)
            
            # B. Hash del Metodo di Produzione
            main_fn = getattr(target_prod, method_name, None)
            if main_fn:
                method_contract['production'] = calculate_hash_of_function(main_fn)
            
            # Aggiunge il contratto solo se almeno un hash è presente
            if method_contract:
                group_contracts[method_name] = method_contract

        if group_contracts:
            contract_hashes[target_name] = group_contracts

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
        json_content = await backend(path=contract_json_path)
        external_contracts: Dict[str, Any] = await convert(json_content, dict, 'json')
        buffered_log("INFO", f"Contratto JSON esterno caricato da {contract_json_path}.")
    except Exception as e:
        buffered_log("WARNING", f"Nessun contratto JSON valido trovato in {contract_json_path}. Filtro hash disabilitato.", e)
        external_contracts = {}

    contract_path = path.replace('.py', '.test.py')
    contract_code = await backend(path=contract_path)
    contract_ana = analyze_module(contract_code, contract_path)
    contract_module = await resource(path=contract_path)

    exports_map = getattr(contract_module, 'exports', {}) if isinstance(getattr(contract_module, 'exports', None), dict) else {}
    if exports_map:
        buffered_log("INFO", f"🔐 exports trovato in {path}: {list(exports_map.keys())}")
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
            current_prod_hash = calculate_hash_of_function(prod_func)
            current_test_hash = calculate_hash_of_function(test_func)
            
            # **********************************************
            # 🔥 Punti in cui viene eseguita la stampa degli hash (Aggiunti come richiesto)
            print("---")
            print(f"Membro: {m}")
            print(prod_func)
            print(f"Hash Production (Atteso): {expected_prod_hash}")
            print(f"Hash Production (Corrente): {current_prod_hash}")
            print(test_func)
            print(f"Hash Test (Atteso): {expected_test_hash}")
            print(f"Hash Test (Corrente): {current_test_hash}")
            # **********************************************
            
            # 4. Filtro di validazione hash
            if current_prod_hash == expected_prod_hash and current_test_hash == expected_test_hash:
                valid.add(m)
                print(f"VALIDATO: Membro '{m}' aggiunto a 'valid'.")
            else:
                print(f"FALLITO: Membro '{m}' non validato (hash non corrispondenti).")
        
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
                            buffered_log("DEBUG", f"Rimosso metodo: {member.__name__}.{attr_name}")
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
    if not resource_path:
        return 'src'
    if not resource_path.startswith('src/'):
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

        buffered_log("INFO", f"⏳ Caricamento dipendenza '{key}' da {import_path}...")
        try:
            imported_content = await backend(path='src/'+import_path)
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
        buffered_log("INFO", f"📦 Dipendenza '{key}' caricata da {import_path}")

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
        exec(code, module.__dict__)
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
    content = await backend(path=resource_path)
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

def _get_line_from_source(source_lines: List[str], lineno: int) -> str:
    """Recupera una specifica riga dal sorgente diviso."""
    index = lineno - 1
    if 0 <= index < len(source_lines):
        return source_lines[index].strip()
    return "RIGA SORGENTE NON TROVATA O FUORI LIMITE"

def asynchronous(custom_filename: str = __file__, app_context: Optional[Dict[str, Any]] = None):
    """
    Decoratore per catturare eccezioni, generare un rapporto di debug dettagliato e loggarlo usando il logger configurato.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
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

                source_code = await backend(path="/"+custom_filename)

                # Genera il rapporto usando l'eccezione attiva
                report = analyze_exception(
                    source_code=source_code,
                    custom_filename=custom_filename,
                    app_context=app_context
                )
                
                ok = await convert(report, str, 'json')

                print(ok)

                # Rilancia l'eccezione
                #raise

        return wrapper
    return decorator

def synchronous(custom_filename: str = __file__, app_context: Optional[Dict[str, Any]] = None):
    """
    Decoratore per catturare eccezioni, generare un rapporto di debug dettagliato e loggarlo usando il logger configurato.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
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

        return wrapper
    return decorator

def analyze_module2(source_code: str, module_name: str) -> Dict[str, Any]:
    """Analizza il codice sorgente (AST) per ricavare la struttura del modulo."""
    structure = {"module_name": module_name, "module_docstring": None}
    
    try:
        tree = ast.parse(source_code)
        if (docstring := ast.get_docstring(tree)): # Usa l'operatore := (Python 3.8+)
            structure["module_docstring"] = docstring.strip()
            
        # Per un'analisi corretta, è meglio iterare direttamente su tree.body 
        # e poi usare ast.walk/ast.iter_child_nodes per l'analisi interna.
        # Oppure, per ast.walk, si deve migliorare lo scope check.
        
        # SOLUZIONE: Usiamo ast.walk ma miglioriamo lo scope check.
        # Il modo più semplice per determinare il top-level è
        # tenere traccia di se siamo entrati in un blocco FunctionDef o ClassDef.
        
        # Per semplicità, ci concentriamo sul correggere solo il controllo ast.Assign
        
        for node in ast.walk(tree):
            # 1. Analisi Funzioni (codice originale)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = {
                    "type": "function",
                    "data": {
                        "lineno": node.lineno,
                        # Nota: get_source_segment richiede Python 3.8+
                        "code": ast.get_source_segment(source_code, node),
                        "docstring": ast.get_docstring(node),
                        "args": [a.arg for a in node.args.posonlyargs + node.args.args + [node.args.vararg] if a],
                    }
                }
                structure[node.name] = func_info
            # 2. Analisi Variabili/Dizionari (LOGICA MODIFICATA)
            elif isinstance(node, ast.Assign):
                
                # --- INIZIO NUOVO SCOPE CHECK ---
                
                # Un'assegnazione è "a livello di modulo" se l'antenato è l'albero radice (module)
                # O se è in un costrutto di blocco (if, for, while) che è a sua volta a livello di modulo.
                # Per la tua esigenza, basta escludere quelle dentro a funzioni o classi.
                
                # Un modo più robusto, senza ricorrere ad ast.walk nidificato, è usare ast.NodeVisitor,
                # ma per correggere il tuo codice esistente:
                
                # Cerchiamo l'antenato principale del nodo per l'assegnazione, 
                # partendo dal corpo del modulo 'tree.body'.
                
                is_top_level_assign = False
                
                # Controlla se il nodo fa parte del corpo principale del modulo
                # O se è in un nodo del corpo principale che non sia Funzione/Classe
                for top_level_node in tree.body:
                    if node is top_level_node:
                        # Assegnazione diretta a livello di modulo
                        is_top_level_assign = True
                        break
                    # Se non è un nodo diretto, controlla se è un discendente di un nodo 
                    # che non è Funzione/Classe (e che non è stato già analizzato come Funzione/Classe)
                    elif isinstance(top_level_node, (ast.If, ast.For, ast.While, ast.With)) and node in ast.walk(top_level_node):
                        # L'assegnazione è dentro un blocco a livello di modulo (if/for/ecc.)
                        is_top_level_assign = True
                        break
                        
                # Se è un'assegnazione a livello di modulo E il valore assegnato è un dizionario...
                if is_top_level_assign and isinstance(node.value, ast.Dict) and node.targets and isinstance(node.targets[0], ast.Name):
                    
                    # --- FINE NUOVO SCOPE CHECK ---
                    
                    var_name = node.targets[0].id
                    
                    # Estraggo il codice sorgente del dizionario
                    dict_code = ast.get_source_segment(source_code, node.value)
                    
                    # Ottiene il valore effettivo
                    var_value = None
                    try:
                        # Tenta di valutare il nodo AST per ottenere il dizionario Python
                        var_value = ast.literal_eval(node.value)
                    except (ValueError, TypeError) as e:
                        var_value = f"Evaluation Error: {type(e).__name__}"
                    
                    info = {
                        "type": type(node.value).__name__,
                        "lineno": node.lineno,
                        "value": var_value,
                    }
                    structure[var_name] = info
            elif isinstance(node, ast.ClassDef):
                # Un'analisi Classi completa richiederebbe di analizzare anche i
                # membri interni (metodi, variabili di classe), ma per una 
                # struttura di base:

                class_info = {
                    "type": "class",
                    "data": {
                        "lineno": node.lineno,
                        "docstring": ast.get_docstring(node),
                        # Le classi base (ereditarietà)
                        "bases": [
                            ast.get_source_segment(source_code, base)
                            for base in node.bases
                            if ast.get_source_segment(source_code, base) is not None
                        ],
                        # Analisi incompleta: Questo non include i metodi/variabili,
                        # ma ne ottiene solo i metadati di base della classe.
                    }
                }
                structure[node.name] = class_info
    except Exception as e:
        structure["parsing_error"] = f"Errore nell'analisi AST: {type(e).__name__} - {str(e)}"

    return structure

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
                            "code": ast.get_source_segment(source_code, node),
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
                            "value": var_value,
                        }
                        structure[var_name] = info
                        
            # Se ci sono blocchi di controllo (if/for/ecc.) che contengono Assegnazioni/Funzioni,
            # questi devono essere gestiti con una logica ricorsiva a parte, ma per semplicità
            # e per mantenere la struttura basata su tree.body, li ignoriamo qui.

    except Exception as e:
        structure["parsing_error"] = f"Errore nell'analisi AST: {type(e).__name__} - {str(e)}"

    return structure

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
            k: v
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
         k: v
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
        "STRUCTURED_TRACEBACK": structured_tb, 
        #"FULL_TRACEBACK_TEXT": full_traceback_text 
    }
    
    return debug_report