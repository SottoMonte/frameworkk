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

from cerberus import Validator, TypeDefinition, errors
import inspect
from typing import Dict, Callable, Any

# --- 1. Eccezione per la Tracciabilità degli Errori ---

class ResourceLoadError(Exception):
    """
    Eccezione personalizzata per gli errori di caricamento delle risorse.
    Include l'adapter e il path per la tracciabilità della catena di errore.
    """
    def __init__(self, message: str, adapter_name: str, path: str):
        super().__init__(message)
        self.adapter = adapter_name
        self.path = path
        self.message = message
        # Migliora il messaggio visualizzato nello stack trace
        self.args = (f"❌ Caricamento fallito per '{adapter_name}' ({path}): {message}",)


# --- 2. Funzioni Helper per la Logica Specifica e il Caricamento ---

# --- ASSUNZIONI E LOGGER (Come nel codice precedente) ---
import logging
logger = logging.getLogger("RESOURCE_LOADER")

import inspect

# Helper di logging strutturato: mostra adapter, path e funzione chiamante
def _log(level: str, msg: str, adapter: str = None, path: str = None, exc: bool = False):
    """
    level: 'debug'|'info'|'warning'|'error'|'exception'
    msg: messaggio principale
    adapter/path: contesto opzionale
    exc: True per includere stack trace (usa logger.exception)
    """
    caller = inspect.stack()[1].function
    extra = {"adapter": adapter, "path": path, "ctx": caller}
    if exc or level == 'exception':
        logger.exception(msg, extra=extra)
    else:
        getattr(logger, level)(msg, extra=extra)


# Cache e stack per prevenire loop e ricaricamenti ripetuti
# Ora registrati in DI per poterli sovrascrivere / mockare facilmente.
if 'module_cache' not in di:
    di['module_cache'] = {}  # type: Dict[str, types.ModuleType]
if 'loading_stack' not in di:
    di['loading_stack'] = set()  # type: Set[str]


def _get_module_cache() -> Dict[str, types.ModuleType]:
    return di['module_cache']


def _get_loading_stack():
    return di['loading_stack']


class ResourceLoadError(Exception):
    def __init__(self, message: str, adapter_name: str = "", path: str = ""):
        super().__init__(f"{adapter_name} @ {path}: {message}")
        self.adapter = adapter_name
        self.path = path


# Backend (sync file read wrapped in async for tests)
if sys.platform != 'emscripten':
    async def backend(**kwargs) -> str:
        path = kwargs.get("path", "")
        if path.startswith('/'):
            path = path[1:]
        try:
            with open(f"src/{path}", "r") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File non trovato: src/{path}")
else:
    import js
    async def backend(**kwargs) -> str:
        path = kwargs.get("path", "")
        # browser-specific fetching (placeholder)
        resp = await js.fetch(path)
        return await resp.text()


async def json_to_pydict(content: str, adapter_name: str):
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"{adapter_name}: JSON parse error: {e}")


def _extract_imports_from_code(code: str) -> Dict[str, str]:
    try:
        tree = ast.parse(code)
    except Exception:
        return {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "imports":
                    if isinstance(node.value, ast.Dict):
                        out: Dict[str, str] = {}
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                                out[k.value] = v.value
                        return out
    return {}


async def _default_dependency_loader(lang: Any, path: str) -> types.ModuleType:
    key = path
    cache = _get_module_cache()
    stack = _get_loading_stack()

    if key in cache:
        logger.debug("cache hit", extra={"adapter": key, "path": path})
        return cache[key]

    if key in stack:
        raise ResourceLoadError("Ciclo di dipendenza rilevato", adapter_name=key, path=path)

    stack.add(key)
    try:
        content = await backend(path=path, adapter=key)
        module = await _execute_python_module(lang, key, path, content, dependency_loader=None)
        cache[key] = module
        return module
    finally:
        stack.remove(key)


async def _execute_python_module(
    lang: Any,
    adapter_name: str,
    path: str,
    module_code: str,
    dependency_loader = None,
) -> types.ModuleType:
    """
    Esegue un modulo dinamico.
    dependency_loader(lang, path) può essere sync o async; se None si usa _default_dependency_loader / lang.resource(_skip_validation=True) fallback.
    """
    async def resolve_dependency(lang_arg: Any, dep_path: str) -> types.ModuleType:
        # prefer user-provided loader
        if dependency_loader:
            res = dependency_loader(lang_arg, dep_path)
            if asyncio.iscoroutine(res):
                return await res
            return res
        # prefer lang.resource with skip
        resolver = getattr(lang, "resource", None)
        if resolver:
            try:
                return await resolver(lang, path=dep_path, _skip_validation=True)
            except Exception:
                pass
        # fallback
        return await _default_dependency_loader(lang_arg, dep_path)

    imports = _extract_imports_from_code(module_code)

    spec = importlib.util.spec_from_loader(adapter_name, loader=None)
    if spec is None:
        _log('error', "Impossibile creare spec modulo", adapter=adapter_name, path=path)
        raise ResourceLoadError("Impossibile creare spec modulo", adapter_name=adapter_name, path=path)
    module = importlib.util.module_from_spec(spec)
    ns = module.__dict__

    # inject language and a convenient resource function (sync wrapper returns coroutine if loop running)
    ns['language'] = lang

    def resource_wrapper(dep_path: str):
        coro = resolve_dependency(lang, dep_path)
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return coro  # caller can await
        else:
            return asyncio.get_event_loop().run_until_complete(coro)

    ns['resource'] = resource_wrapper

    # resolve imports
    injected: Dict[str, types.ModuleType] = {}
    for name, dep_path in imports.items():
        try:
            dep_mod = await resolve_dependency(lang, dep_path)
        except Exception as e:
            _log('error', f"Errore caricamento dipendenza '{dep_path}': {e}", adapter=adapter_name, path=path, exc=True)
            raise ResourceLoadError(f"Errore caricamento dipendenza '{dep_path}': {e}", adapter_name=adapter_name, path=path) from e
        injected[name] = dep_mod

    ns.update(injected)

    try:
        exec(module_code, ns)
    except Exception as e:
        _log('exception', f"Esecuzione modulo fallita: {e}", adapter=adapter_name, path=path, exc=True)
        raise ResourceLoadError(f"Esecuzione modulo fallita: {e}", adapter_name=adapter_name, path=path) from e

    return module


async def _validate_module_contract(
    lang: Any,
    module: types.ModuleType,
    path: str,
    run_tests: bool = False,
):
    """
    Ispeziona il .test.py e restituisce membri da esporre.
    Supporta metodi di test sync e async: test_<nome_membro>.
    """
    test_path = path.replace(".py", ".test.py")
    adapter_test = module.__name__ + ".test"
    validated = set()

    try:
        test_content = await backend(path=test_path, adapter=adapter_test)
    except FileNotFoundError:
        _log('debug', "Nessun file di test trovato", adapter=module.__name__, path=test_path)
        return validated

    test_module = await _execute_python_module(lang, adapter_test, test_path, test_content, dependency_loader=None)

    for name, obj in list(vars(test_module).items()):
        if not isinstance(obj, type):
            continue
        if not (name == "TestModule" or name.startswith("Test")):
            continue

        test_instance = obj()
        setattr(test_instance, "main_module", module)

        target_class = None if name == "TestModule" else name[4:] or None

        for attr in dir(test_instance):
            if not attr.startswith("test_"):
                continue
            func = getattr(obj, attr, None)
            is_coro = asyncio.iscoroutinefunction(func)
            member = attr[5:]

            if run_tests:
                method = getattr(test_instance, attr)
                try:
                    if is_coro:
                        await method()
                    else:
                        method()
                except Exception as e:
                    raise ResourceLoadError(f"Test fallito {attr}: {e}", adapter_name=adapter_test, path=test_path)

            if target_class:
                if hasattr(module, target_class):
                    validated.add(target_class)
            else:
                if hasattr(module, member):
                    validated.add(member)

    logger.info("Ispezione contratto completata", extra={"adapter": module.__name__, "members": len(validated)})
    return validated


def _create_filtered_module(original: types.ModuleType, adapter_name: str, members) -> types.ModuleType:
    spec = importlib.util.spec_from_loader(f"filtered.{adapter_name}", loader=None)
    filtered = importlib.util.module_from_spec(spec)
    filtered.__name__ = adapter_name
    filtered.__file__ = getattr(original, "__file__", None)
    if hasattr(original, "language"):
        filtered.language = original.language
    for m in members:
        try:
            setattr(filtered, m, getattr(original, m))
        except Exception:
            logger.debug("Membro non trovato durante filtraggio", extra={"adapter": adapter_name, "member": m})
    return filtered


async def resource(lang: Any, **constants) -> Any:
    """
    Carica risorsa.
    Parametri:
      - path: str
      - adapter: str (opz.)
      - _skip_validation: bool
      - dependency_loader: callable(lang, path) -> module (sync o async)
    """
    path: str = constants.get("path", "")
    adapter: str = constants.get("adapter", path)
    skip_validation: bool = bool(constants.get("_skip_validation", False))
    dependency_loader = constants.get("dependency_loader", None)

    try:
        content = await backend(path=path, adapter=adapter)
    except FileNotFoundError:
        raise
    except Exception as e:
        _log('error', f"Backend error: {e}", adapter=adapter, path=path, exc=True)
        raise ResourceLoadError(f"Backend error: {e}", adapter_name=adapter, path=path)

    if path.endswith(".json"):
        return await json_to_pydict(content, adapter)

    # normalize dependency_loader to callable matching (lang, path)
    dep_loader_callable = None
    if callable(dependency_loader):
        def _wrap(lang_arg, p):
            res = dependency_loader(lang_arg, p)
            return res
        dep_loader_callable = _wrap

    main_module = await _execute_python_module(lang, adapter, path, content, dependency_loader=dep_loader_callable)

    if skip_validation:
        _log('info', "Skip validation requested", adapter=adapter, path=path)
        return main_module

    validated = await _validate_module_contract(lang, main_module, path, run_tests=False)
    if not validated:
        _log('warning', "Nessun membro esposto dal test", adapter=adapter, path=path)

    filtered = _create_filtered_module(main_module, adapter, validated)
    _log('info', "Risorsa caricata", adapter=adapter, path=path)
    return filtered


# Retain original get_confi name (no alias get_config)
def get_config(**constants):
    jinjaEnv = Environment()
    jinjaEnv.filters['get'] = lambda d, k, default=None: d.get(k, default) if isinstance(d, dict) else default
    if sys.platform != 'emscripten':
        try:
            with open('pyproject.toml', 'r') as f:
                text = f.read()
        except Exception:
            text = ""
    else:
        text = ""
    template = jinjaEnv.from_string(text or "")
    content = template.render(constants)
    try:
        return {}
    except Exception:
        return {}
