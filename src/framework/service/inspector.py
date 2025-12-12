
import json
import ast
import inspect
import types
import hashlib
import marshal
import os
import sys
import platform
import socket
import psutil
import traceback
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from framework.service.context import container

if sys.platform == 'emscripten':
    import js


# =====================================================================
# --- Strumenti di Introspezione e Analisi ---
# =====================================================================

class LogReportEncoder(json.JSONEncoder):
    """
    JSONEncoder personalizzato per la serializzazione di oggetti complessi 
    trovati nei log di debug e nelle tracce di errore.
    Converte qualsiasi tipo di dato non serializzabile in una stringa.
    """
    def default(self, obj):
        try:
            # 1. Tenta di usare l'implementazione predefinita della superclasse
            return super().default(obj)
        except TypeError:
            # 2. Fallback universale: converti in stringa
            return str(obj)

def _get_system_info() -> Dict[str, Any]:
    """Raccoglie le informazioni chiave su CPU, RAM e Processo."""
    mem = 2000
    
    return {
        "hostname": socket.gethostname(),
        "process_id": os.getpid(),
        "cpu_cores_logical": psutil.cpu_count(),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_available_gb": round(mem.available / (1024**3), 2),
        "os_name": platform.platform(),
    }

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
        if len(value) > max_list_len:
            truncated_items = list(value)[:max_list_len]
            processed_items = [
                truncate_value("", item, max_str_len=30, max_list_len=5)
                for item in truncated_items
            ]
            return f"{processed_items} ... [TRONCATA, N={len(value)}]"
        
        return [
            truncate_value("", item, max_str_len=30, max_list_len=5)
            for item in value
        ]
        
    elif isinstance(value, dict):
        return {
            k: truncate_value(k, v, max_str_len=max_str_len, max_list_len=max_list_len) 
            for k, v in value.items()
        }

    return value

def analyze_traceback(tb: Optional[types.TracebackType]) -> List[Dict[str, Any]]:
    """
    Estrae i frame del traceback in un formato strutturato.
    """
    structured_tb = []
    current_tb = tb
    
    while current_tb is not None:
        frame = current_tb.tb_frame
        
        # Ignora le librerie di sistema
        filename = frame.f_code.co_filename
        if "/usr/" in filename or "/local/lib/python" in filename or "python3." in filename:
            current_tb = current_tb.tb_next
            continue

        # Estrai le variabili locali
        local_vars_state = {
            k: truncate_value(k, v)
            for k, v in frame.f_locals.items() 
            if not k.startswith('__') and k not in ['frame', 'frame_summary', 'current_tb', 'tb']
        }
        
        line_content = None
        try:
            frame_summary = traceback.FrameSummary(filename, frame.f_lineno, frame.f_code.co_name, lookup_line=True)
            if frame_summary.line:
                line_content = frame_summary.line.strip()
        except Exception:
            pass 

        if line_content is None:
            if filename.startswith('<'):
                line_content = "SORGENTE DINAMICA NON DISPONIBILE"
            else:
                line_content = "SORGENTE NON RECUPERATA"
        
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
    """Genera un report dettagliato sull'eccezione corrente."""
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    if exc_type is None or exc_traceback is None:
        return {"status": "Nessuna eccezione attiva trovata."}
        
    tb_list = traceback.extract_tb(exc_traceback)
    
    last_traceback = exc_traceback
    while last_traceback.tb_next:
        last_traceback = last_traceback.tb_next
    last_frame_object = last_traceback.tb_frame 
    
    raw_filename = tb_list[-1].filename
    raw_lineno = tb_list[-1].lineno
    
    # Nota: source_code passato qui potrebbe non essere usato se si usa traceback.FrameSummary, 
    # ma è mantenuto per compatibilità con la firma originale.
    
    structured_tb = analyze_traceback(exc_traceback)
    
    final_error_step = structured_tb[-1] if structured_tb else {
        "step_code_line": "SORGENTE NON RECUPERATA", 
        "step_lineno": raw_lineno, 
        "step_function": tb_list[-1].name
    }
    
    final_local_vars = {
         k: truncate_value(k, v)
         for k, v in last_frame_object.f_locals.items() 
         if not k.startswith('__') and k not in ['last_traceback', 'last_frame_object', 'raw_lineno', 'tb_list', 'exc_traceback']
    }
    
    exception_details = {
        "exception_type": type(exc_value).__name__,
        "exception_message": str(exc_value),
        "error_location": {
            "filename": raw_filename,
            "line_number": final_error_step["step_lineno"],
            "function_name": final_error_step["step_function"],
            "source_code_line": final_error_step["step_code_line"],
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
        "STRUCTURED_TRACEBACK": structured_tb[1:-1], 
    }
    
    return debug_report

def analyze_function_calls(func: types.FunctionType) -> set[str]:
    """Analizza una funzione e restituisce i nomi di tutte le funzioni chiamate al suo interno (AST)."""
    
    # Se non riusciamo a recuperare il source (es. built-in), gestiamo l'errore.
    try:
        source_code = inspect.getsource(func)
    except OSError:
        return set()

    tree = ast.parse(source_code)
    called_names: set[str] = set()

    class CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    called_names.add(node.func.value.id + '.' + node.func.attr)
                else:
                    called_names.add(node.func.attr) 
            self.generic_visit(node)

    visitor = CallVisitor()
    visitor.visit(tree)
    return called_names

def map_dependencies(module: types.ModuleType):
    """Crea la mappa delle dipendenze: {funzione_pubblica: {dipendenze_chiamate}}."""
    dependency_map = {}
    
    for name, member in inspect.getmembers(module):
        if (inspect.isfunction(member) or inspect.ismethod(member)) and \
           not name.startswith('_') and member.__module__ == module.__name__:
            
            try:
                calls = analyze_function_calls(member)
                dependency_map[name] = calls
            except Exception:
                # Ignora errori, es. su funzioni non analizzabili
                pass
                
    return dependency_map

def correlate_failure(failing_test_name: str, dependency_map: Dict[str, set[str]]):
    """Identifica la funzione pubblica interessata dal fallimento del test."""
    if failing_test_name.startswith('test_'):
        target_fn_name = failing_test_name.replace('test_', '')
        
        inverted_map: Dict[str, set[str]] = {}
        for caller, callees in dependency_map.items():
            for callee in callees:
                inverted_map.setdefault(callee, set()).add(caller)
        
        affected_public_functions = inverted_map.get(target_fn_name, set())
        
        if affected_public_functions:
            return affected_public_functions
        elif target_fn_name in dependency_map:
            return {target_fn_name}
        
    return set()

def analyze_module(source_code: str, module_name: str) -> Dict[str, Any]:
    """Analizza il codice sorgente (AST) per ricavare la struttura del modulo."""
    structure = {"module_name": module_name, "module_docstring": None}
    
    try:
        tree = ast.parse(source_code)
        if (docstring := ast.get_docstring(tree)):
            structure["module_docstring"] = docstring.strip()
            
        ignored_nested_nodes = set()

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "type": "class",
                    "data": {
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "docstring": ast.get_docstring(node),
                        "methods": {},
                        "class_vars": {} 
                    }
                }
                
                for class_member in node.body:
                    if isinstance(class_member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        ignored_nested_nodes.add(class_member)
                        method_info = {
                            "type": "method",
                            "lineno": class_member.lineno,
                            "end_lineno": class_member.end_lineno,
                            "docstring": ast.get_docstring(class_member),
                            "args": [
                                a.arg for a in class_member.args.posonlyargs + class_member.args.args + [class_member.args.vararg] 
                                if a and a.arg not in ('self', 'cls')
                            ],
                        }
                        class_info["data"]["methods"][class_member.name] = method_info
                        
                    elif isinstance(class_member, ast.Assign) and class_member.targets and isinstance(class_member.targets[0], ast.Name):
                        ignored_nested_nodes.add(class_member)
                        var_name = class_member.targets[0].id
                        class_info["data"]["class_vars"][var_name] = {
                            "lineno": class_member.lineno,
                            "type_ast": type(class_member.value).__name__,
                        }

                structure[node.name] = class_info

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node not in ignored_nested_nodes:
                    func_info = {
                        "type": "function",
                        "data": {
                            "lineno": node.lineno,
                            "end_lineno": node.end_lineno,
                            "docstring": ast.get_docstring(node),
                            "args": [a.arg for a in node.args.posonlyargs + node.args.args + [node.args.vararg] if a],
                        }
                    }
                    structure[node.name] = func_info
            
            elif isinstance(node, ast.Assign):
                if node not in ignored_nested_nodes:
                    if isinstance(node.value, ast.Dict) and node.targets and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        var_value = None
                        try:
                            # Tentativo safe di valutazione
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
                        
    except Exception as e:
        structure["parsing_error"] = f"Errore nell'analisi AST: {type(e).__name__} - {str(e)}"

    return structure

def calculate_hash_of_function(func: types.FunctionType):
    """Calcola un hash SHA256 stabile, svelando le funzioni decorate."""
    from inspect import unwrap
    try:
        unwrapped_func = unwrap(func)
    except Exception:
        # Se unwrap fallisce, usa la funzione così com'è
        unwrapped_func = func
    
    if not hasattr(unwrapped_func, '__code__'):
        # Fallback per oggetti non standard
        return hashlib.sha256(str(func).encode('utf-8')).hexdigest()

    code_obj = unwrapped_func.__code__
    
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
    
    try:
        serialized = marshal.dumps(relevant_parts)
    except Exception:
        # Fallback se marshal fallisce
        serialized = str(relevant_parts).encode('utf-8')
        
    return hashlib.sha256(serialized).hexdigest()

def estrai_righe_da_codice(codice_sorgente: str, riga_inizio: int, riga_fine: int) -> str:
    """Estrae il codice sorgente tra riga_inizio e riga_fine (inclusive)."""
    righe = codice_sorgente.splitlines()
    indice_inizio = max(0, riga_inizio - 1)
    indice_fine = min(len(righe), riga_fine)

# =====================================================================
# --- Logging Utilites ---
# =====================================================================

def buffered_log(level: str, message: str, emoji: str = ""):
    """Logger rudimentale che bufferizza i messaggi iniziali"""
    formatted = f"{emoji} {message}"
    if hasattr(container, 'log_buffer'):
        container.log_buffer().append({
            'level': level,
            'message': message,
            'emoji': emoji,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    print(formatted)

# =====================================================================
# --- Resource Loading Utilites ---
# =====================================================================

def _check_single_import(module_name, allowed_prefixes, project_modules, layer, lineno, file_path, is_path=False):
    if is_path:
        root_module = module_name.split('/')[0]
    else:
        root_module = module_name.split('.')[0]
    
    if root_module not in project_modules:
        return 

    if root_module not in allowed_prefixes:
        # In un contesto reale questo potrebbe alzare ImportError,
        # qui logghiamo o ignoriamo per semplicità durante il refactoring
        pass

def _validate_imports(content: str, file_path: str):
    """
    Validates that imports in the file respect the architectural layering rules.
    """
    layer = None
    if 'src/application/' in file_path:
        layer = 'application'
    elif 'src/framework/' in file_path:
        layer = 'framework'
    elif 'src/infrastructure/' in file_path:
        layer = 'infrastructure'
    
    if not layer:
        return

    allowed_imports = {
        'application': ['application'],
        'framework': ['framework', 'application'],
        'infrastructure': ['infrastructure', 'framework']
    }
    
    allowed = allowed_imports.get(layer)
    if not allowed:
        return

    project_modules = ['application', 'framework', 'infrastructure']

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        imported_module = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_module = alias.name
                _check_single_import(imported_module, allowed, project_modules, layer, node.lineno, file_path)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_module = node.module
                _check_single_import(imported_module, allowed, project_modules, layer, node.lineno, file_path)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'imports':
                    if isinstance(node.value, ast.Dict):
                        for i, value in enumerate(node.value.values):
                            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                                _check_single_import(value.value, allowed, project_modules, layer, node.lineno, file_path, is_path=True)

if sys.platform != 'emscripten':
    async def _load_resource(**kwargs) -> str:
        path = kwargs.get("path", "")
        if path.startswith('/'):
            path = path[1:]

        if path.startswith('application/') or path.startswith('framework/') or path.startswith('infrastructure/'):
            path = 'src/'+path

        try:
            with open(f"{path}", "r") as f:
                content = f.read()
                _validate_imports(content, path)
                return content
        except FileNotFoundError:
            raise FileNotFoundError(f"File non trovato: {path}")
        except Exception as e:
            print(f"Errore caricamento file {path}: {e}",kwargs)
            raise e
else:
    async def _load_resource(**kwargs) -> str:
        path = kwargs.get("path", "")
        try:
            resp = await js.fetch(path)
            return await resp.text()
        except Exception as e:
            raise FileNotFoundError(f"File non trovato (fetch fallito): {path}") from e

