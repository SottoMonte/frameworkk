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
# --- Funzioni di Caricamento ---
# =====================================================================

async def validate_and_filter_module(main_module: types.ModuleType, path: str) -> types.ModuleType:
    """
    Simula la validazione (hashing, test) e restituisce un modulo filtrato.
    Per l'esempio, includiamo solo le funzioni e classi che iniziano con 'format_' o 'Application'.
    """
    validated_members = {'format_user', 'application', 'messenger','executor','storekeeper','defender','presenter','adapter'} # Membri che hanno 'superato' la validazione
    
    # Crea un nuovo modulo con solo i membri approvati
    filtered_module = types.ModuleType(f"filtered:{main_module.__name__}")
    filtered_module.__file__ = main_module.__file__
    
    for name in validated_members:
        if hasattr(main_module, name):
            setattr(filtered_module, name, getattr(main_module, name))
            
    # Assegna anche la dipendenza risolta, se presente
    if hasattr(main_module, 'schema'):
        setattr(filtered_module, 'schema', getattr(main_module, 'schema'))
        
    print(f"✅ Validazione e filtro riusciti per {path}. Membri esposti: {list(validated_members)}")
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
        print(f"⏳ Caricamento dipendenza '{key}' da {import_path}...")
        try:
            imported_content = await backend(path='src/'+import_path)
        except FileNotFoundError:
            continue
        value: Any
        if isinstance(imported_content, str) and import_path.endswith(".json"):
            try:
                value = await convert(imported_content, 'dict', 'json')
            except Exception:
                value = json.loads(imported_content)
        elif import_path.endswith(".py"):
            value = await _load_python_module(key, import_path, imported_content)
        else:
            value = imported_content
        setattr(module, key, value)
        print(f"📦 Dipendenza '{key}' caricata da {import_path}")

async def _load_python_module(name: str, path: str, code: str) -> types.ModuleType:
    """Crea ed esegue dinamicamente un modulo Python con le variabili globali necessarie."""
    module_name = f"{path}"
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__source__ = code
    module.__dict__['language'] = di['module_cache'].get('language')
    
    #module.__dict__['imports'] = dependencies
    #print(code)
    
    try:
        dependencies = analyze_module(code, path)
        
        dependencies = dependencies.get('imports',{}).get('value',{})
        print(f"🔍 Dipendenze trovate in {path}: {dependencies}")
        await _load_dependencies(module,dependencies.copy())
        exec(code, module.__dict__)
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
        return await convert(content, str, 'json')
    
    if resource_path.endswith(".py"):
        # Notare che `lang` viene passato qui
        main_module = await _load_python_module("main_module", resource_path, content)
        # La funzione di validazione è astratta/esterna
        filtered_module = await validate_and_filter_module(main_module, resource_path)
        return filtered_module
        
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
         print(f"❌ Errore: Configurazioni DI insufficienti: {constants}")
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
            print(f"✅ Registrato Factory: '{service_name}' ({log_info})")

        else:
            # --- CASO: PROVIDER/SINGLETON (Istanziamento eager in una lista) ---
            if service_name not in di:
                di[service_name] = lambda di: list([])

            #provider = getattr(module, 'adapter')
            di[service_name].append(resource_class(config=init_args))
            
            print(f"✅ Aggiunto Provider a lista: '{service_name}' ({log_info})")

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

def analyze_module(source_code: str, module_name: str) -> Dict[str, Any]:
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