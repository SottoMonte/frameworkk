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
from typing import Dict, Callable, Any
import hashlib

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


mappa = {
    (str,dict,''): lambda v: v if isinstance(v, dict) else {},
    (str,dict,'json'): lambda v: json.loads(v) if isinstance(v, str) else {},
    (dict,str,'json'): lambda v: json.dumps(v) if isinstance(v, dict) else '',

}

async def convert(target, output,input=''):
    try:
        return mappa[(type(target),output,input)](target)
    except KeyError:
        raise ValueError(f"Conversione non supportata: {type(target)} -> {output} da {input}")
    except Exception as e:
        raise ValueError(f"Errore conversione: {e}")

async def format(target ,**constants):
    try:
        jinjaEnv = Environment()
        #jinjaEnv.filters['get'] = lambda d, k, default=None: d.get(k, default) if isinstance(d, dict) else default
        template = jinjaEnv.from_string(target)
        return template.render(constants)
    except Exception as e:
        raise ValueError(f"Errore formattazione: {e}")

async def resource(lang, **constants) -> Any:
    path: str = constants.get("path", "")

    # Normalizza la path ricevuta:
    # - rimuove leading slash
    # - garantisce il prefisso 'src/' solo una volta
    path = (path or "").lstrip('/')
    if not path:
        path = 'src'
    elif not path.startswith('src/'):
        path = os.path.normpath(os.path.join('src', path))
    else:
        path = os.path.normpath(path)

    content = await backend(path=path)


    if path.endswith(".json"):
        return await convert(content, 'dict', 'json')

    # Funzioni di supporto incapsulate dentro 'resource', come richiesto
    async def _execute_python_module(adapter_name: str, path: str, module_code: str, dependency_loader=None) -> types.ModuleType:
        """
        Crea un module object dinamico, esegue il codice in un suo namespace e ritorna il module.
        Allega __source__ con il codice originale per successiva ispezione/hash.
        Inietta alcuni global utili (language, loader, types, asyncio).
        """
        module_name = f"dynamic_{uuid.uuid4().hex}"
        module = types.ModuleType(module_name)
        # usa la path già normalizzata (evita 'src/src/...' se path contiene già 'src/')
        module.__file__ = path
        ns = module.__dict__

        # variabili utili disponibili al codice eseguito
        ns['language'] = lang
        ns['loader'] = lang         # alias semplice: il loader può essere l'oggetto language
        ns['types'] = types
        ns['asyncio'] = asyncio

        # salva sorgente per hashing/diagnostica
        module.__source__ = module_code
        try:
            exec(module_code, ns)
        except Exception as e:
            raise ImportError(f"Esecuzione modulo fallita: {e}") from e
        return module

    def _compute_top_level_hashes(source: str) -> Dict[str, str]:
        """
        Restituisce mapping name -> sha256 della porzione di sorgente per
        funzioni e classi di livello superiore.
        """
        out: Dict[str, str] = {}
        try:
            tree = ast.parse(source)
        except Exception:
            return out
        lines = source.splitlines()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1) - 1
                end = getattr(node, "end_lineno", start + 1)
                seg = "\n".join(lines[start:end])
                out[node.name] = hashlib.sha256(seg.encode("utf-8")).hexdigest()
        return out

    def _compute_test_method_hashes(source: str) -> Dict[str, str]:
        """
        Restituisce mapping "TestClass.test_method" -> sha256 della porzione
        di sorgente del metodo di test.
        """
        out: Dict[str, str] = {}
        try:
            tree = ast.parse(source)
        except Exception:
            return out
        lines = source.splitlines()
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and (node.name == "TestModule" or node.name.startswith("Test")):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                        start = getattr(item, "lineno", 1) - 1
                        end = getattr(item, "end_lineno", start + 1)
                        seg = "\n".join(lines[start:end])
                        out[f"{node.name}.{item.name}"] = hashlib.sha256(seg.encode("utf-8")).hexdigest()
        return out

    def _load_hash_db():
        """
        Restituisce tuple (db, db_path). Se il file non esiste lo crea vuoto.
        """
        db_path = "src/framework/service/test_hashes.json"
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            if not os.path.exists(db_path):
                # crea file vuoto
                with open(db_path, "w") as f:
                    json.dump({}, f)
                return {}, db_path
            with open(db_path, "r") as f:
                try:
                    return json.load(f), db_path
                except Exception:
                    # se non è valid JSON, sovrascriviamo con vuoto per non bloccare il sistema
                    with open(db_path, "w") as fw:
                        json.dump({}, fw)
                    return {}, db_path
        except Exception:
            # fallback: DB in-memory se anche la creazione fallisce
            return {}, db_path

    async def _validate_module_contract(module: types.ModuleType, path: str, run_tests: bool = False):
        """
        Verifica che il modulo abbia entry nel JSON degli hash e che gli hash
        di top-level e dei test coincidano. Se manca l'entry esegue i test:
        - se i test falliscono -> ImportError
        - se i test passano -> salva gli hash nel JSON e procede con la validazione
        """
        if path.endswith(".py"):
            test_path = path[:-3] + ".test.py"
        else:
            test_path = path + ".test.py"

        try:
            test_content = await backend(path=test_path)
        except FileNotFoundError:
            raise ImportError(f"Nessun file di test trovato per {path}: atteso {test_path}")

        test_module = await _execute_python_module("test_adapter", test_path, test_content, dependency_loader=None)

        # se il file di test definisce una mappa 'imports', risolviamola e popoliamo le variabili
        # es.: "imports = { 'model': 'framework/schema/model.json' }"
        try:
            imports_map = getattr(test_module, "imports", None)
            if isinstance(imports_map, dict):
                for key, import_path in imports_map.items():
                    try:
                        imported_content = await backend(path=import_path)
                    except FileNotFoundError:
                        continue
                    if isinstance(imported_content, str) and import_path.endswith(".json"):
                        try:
                            value = await convert(imported_content, 'dict', 'json')
                        except Exception:
                            # fallback a json.loads diretto
                            value = json.loads(imported_content)
                    elif import_path.endswith(".py"):
                        # esegui il modulo dipendenza e assegna il module
                        value = await _execute_python_module(f"dep_{key}", import_path, imported_content, dependency_loader=None)
                    else:
                        value = imported_content
                    setattr(test_module, key, value)
        except Exception:
            # non blocchiamo l'esecuzione dei test in caso di problemi secondari con gli imports
            pass

        db, db_path = _load_hash_db()
        # usiamo una key canonica per il DB (la path già normalizzata passata a resource)
        canonical_key = os.path.normpath(path)
        # cerchiamo anche eventuali varianti salvate precedentemente per compatibilità
        found_key = None
        for k in db.keys():
            try:
                if os.path.normpath(k) == canonical_key or k.endswith(path) or canonical_key.endswith(os.path.normpath(k)):
                    found_key = k
                    break
            except Exception:
                continue
        # se troviamo una vecchia chiave, usiamola come punto di partenza ma poi riscriviamo sotto la canonical_key
        entry = db.get(found_key) if found_key else db.get(canonical_key)

        main_source = getattr(module, "__source__", None)
        test_source = getattr(test_module, "__source__", None)
        if main_source is None or test_source is None:
            raise ImportError("Sorgente non disponibile per hashing")

        main_hashes = _compute_top_level_hashes(main_source)
        test_hashes = _compute_test_method_hashes(test_source)

        # se manca l'entry: esegui i test; se passano, salva gli hash e continua
        if not entry:
            try:
                # semplice runner dei test definiti nel file di test
                for name, obj in list(vars(test_module).items()):
                    if not isinstance(obj, type):
                        continue
                    if not (name == "TestModule" or name.startswith("Test")):
                        continue
                    test_instance = obj()
                    setattr(test_instance, "main_module", module)
                    for attr in dir(test_instance):
                        if not attr.startswith("test_"):
                            continue
                        method = getattr(test_instance, attr)
                        if asyncio.iscoroutinefunction(method):
                            await method()
                        else:
                            method()
            except Exception as e:
                raise ImportError(f"Test fallito durante validazione iniziale per {path}: {e}")

            # se i test passano, persistiamo gli hash calcolati
            db[canonical_key] = {
                 "functions": main_hashes,
                 "tests": test_hashes
             }
            try:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                with open(db_path, "w") as f:
                    json.dump(db, f, indent=2)
            except Exception:
                # non blocchiamo l'importazione se il salvataggio fallisce
                pass
            # se esisteva una vecchia chiave, rimuoviamola per evitare duplicati
            if found_key and found_key != canonical_key and found_key in db:
                try:
                    del db[found_key]
                except Exception:
                    pass
            entry = db.get(canonical_key)

        expected_funcs = entry.get("functions", {})
        expected_tests = entry.get("tests", {})

        validated = set()
        auto_accept = os.environ.get("FWK_AUTO_ACCEPT_HASH", "") == "1"
        updated = False

        for test_key, registered_test_hash in expected_tests.items():
            actual_test_hash = test_hashes.get(test_key)
            if actual_test_hash is None:
                raise ImportError(f"Test registrato '{test_key}' non trovato nel file di test -> importazione bloccata")

            if actual_test_hash != registered_test_hash:
                if auto_accept:
                    expected_tests[test_key] = actual_test_hash
                    db.setdefault(canonical_key, {})["tests"] = expected_tests
                    updated = True
                else:
                    raise ImportError(f"Hash test mismatch per '{test_key}' -> importazione bloccata")

            if "." not in test_key:
                raise ImportError(f"Formato test key non valido: {test_key}")
            cls, method = test_key.split(".", 1)
            if cls == "TestModule":
                member = method[5:] if method.startswith("test_") else method
                registered_member_hash = expected_funcs.get(member)
                actual_member_hash = main_hashes.get(member)
                if registered_member_hash is None or actual_member_hash is None:
                    raise ImportError(f"Hash non registrato o membro non trovato per '{member}' richiesto da '{test_key}'")
                if registered_member_hash != actual_member_hash:
                    if auto_accept:
                        expected_funcs[member] = actual_member_hash
                        db.setdefault(canonical_key, {})["functions"] = expected_funcs
                        updated = True
                    else:
                        raise ImportError(f"Hash mismatch per membro '{member}' richiesto da '{test_key}'")
                validated.add(member)
            else:
                if not cls.startswith("Test"):
                    raise ImportError(f"Nome classe test non riconosciuto: {cls}")
                target_class = cls[4:] or None
                registered_member_hash = expected_funcs.get(target_class)
                actual_member_hash = main_hashes.get(target_class)
                if registered_member_hash is None or actual_member_hash is None:
                    raise ImportError(f"Hash non registrato o classe non trovata per '{target_class}' richiesta da '{test_key}'")
                if registered_member_hash != actual_member_hash:
                    if auto_accept:
                        expected_funcs[target_class] = actual_member_hash
                        db.setdefault(canonical_key, {})["functions"] = expected_funcs
                        updated = True
                    else:
                        raise ImportError(f"Hash mismatch per classe '{target_class}' richiesta da '{test_key}'")
                validated.add(target_class)

        if updated:
            try:
                with open(db_path, "w") as f:
                    json.dump(db, f, indent=2)
            except Exception:
                pass

        # opzionale: eseguire i test una seconda volta se richiesto
        if run_tests:
            for name, obj in list(vars(test_module).items()):
                if not isinstance(obj, type):
                    continue
                if not (name == "TestModule" or name.startswith("Test")):
                    continue
                test_instance = obj()
                setattr(test_instance, "main_module", module)
                for attr in dir(test_instance):
                    if not attr.startswith("test_"):
                        continue
                    method = getattr(test_instance, attr)
                    try:
                        if asyncio.iscoroutinefunction(method):
                            await method()
                        else:
                            method()
                    except Exception as e:
                        raise ImportError(f"Test fallito {name}.{attr}: {e}")

        return validated

    def _create_filtered_module(main_module: types.ModuleType, validated):
        """
        Restituisce un oggetto module con i soli membri validati (consente .application).
        """
        module_name = getattr(main_module, "__name__", f"filtered_{uuid.uuid4().hex}")
        out_module = types.ModuleType(module_name)
        out_module.__file__ = getattr(main_module, "__file__", None)
        for name in validated:
            if hasattr(main_module, name):
                setattr(out_module, name, getattr(main_module, name))
        return out_module

    # Fine funzioni di supporto ------------------------------

    # esegui il modulo principale
    main_module = await _execute_python_module(path, path, content, dependency_loader=None)

    # se il modulo principale definisce una mappa 'imports', risolviamola e popoliamo le variabili
    try:
        imports_map = getattr(main_module, "imports", None)
        if isinstance(imports_map, dict):
            for key, import_path in imports_map.items():
                try:
                    imported_content = await backend(path=import_path)
                except FileNotFoundError:
                    continue
                if isinstance(imported_content, str) and import_path.endswith(".json"):
                    try:
                        value = await convert(imported_content, 'dict', 'json')
                    except Exception:
                        value = json.loads(imported_content)
                elif import_path.endswith(".py"):
                    value = await _execute_python_module(f"dep_{key}", import_path, imported_content, dependency_loader=None)
                else:
                    value = imported_content
                setattr(main_module, key, value)
    except Exception:
        # non blocchiamo il caricamento del modulo principale se qualche import fallisce
        pass

    # valida contratto tramite JSON degli hash + test file
    validated = await _validate_module_contract(main_module, path, run_tests=False)

    filtered = _create_filtered_module(main_module, validated)
    return filtered
