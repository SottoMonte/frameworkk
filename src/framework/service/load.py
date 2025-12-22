import os
import sys
import asyncio
import logging
import types
import inspect
import uuid
import json
import time
from typing import Dict, Any, List, Optional, Callable
from framework.service.context import container
import framework.service.flow as flow
from framework.service.flow import asynchronous, synchronous, convert
from framework.service.inspector import (
    analyze_module,
    calculate_hash_of_function,
    estrai_righe_da_codice,
    framework_log,
    buffered_log,
    _load_resource,
    log_block
)

from dependency_injector import providers

# Logging is now handled via framework_log from inspector.py

# =====================================================================
# --- Funzioni di Generazione (Spostate da language.py) ---
# =====================================================================

async def generate_checksum(main_path: str, ) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    """
    Genera il contratto JSON, mappando ogni metodo in un oggetto annidato
    che distingue l'hash di produzione da quello di test.
    """
    # 1. Caricamento e Analisi
    contract_path = main_path.replace('.py', '.test.py')
    main_code = await _load_resource(path=main_path)
    contract_code = await _load_resource(path=contract_path)
    
    if not main_code or not contract_code:
        framework_log("INFO", f"Impossibile caricare i file sorgente o di test ({main_path} / {contract_path}).")
        return {}

    main_module = analyze_module(main_code, main_path)
    contract_ana = analyze_module(contract_code, contract_path)
    contract_hashes = {} 

    # 2. Itera e Genera Hash (Logica Unificata)
    for mname, data in contract_ana.items():
        # Continua (salta l'iterazione) SE NON è un dizionario OPPURE se è un dizionario ma NON ha la chiave 'type'
        # E NON è il modulo di base (mname != '__module__')
        is_class = isinstance(data, dict) and 'type' in data and data['type'] == 'class'
        
        # Se non è una classe e non è il modulo di base, salta.
        if not is_class and mname != '__module__':
            continue
            
        # Per coerenza, se è il modulo di base, usa i dati di contract_ana 
        methods = data.get('data', {}).get('methods', {})
        
        # Usa TestModule per la logica di estrazione dei metodi
        if mname == 'TestModule':
            target_name = '__module__'
        else:
            target_name = mname.replace('Test', '')
        
        for method_name, method_data in methods.items():
            if not method_name.startswith('test_'):
                continue

            method_name_clean = method_name.replace('test_', '')
            is_module_level_test = (mname == 'TestModule' or target_name == '__module__')
            
            # Recupero target di produzione
            target_prod = main_module if is_module_level_test and method_name_clean in main_module else main_module.get(target_name, {})
            
            # Gestione del caso in cui i metodi sono direttamente nel modulo
            if is_module_level_test:
                prod_data_source = target_prod
                prod_method_data = prod_data_source.get(method_name_clean, {}).get('data',{})
            else:
                prod_data_source = target_prod
                prod_method_data = prod_data_source.get('data', {}).get('methods', {}).get(method_name_clean, {})
            
            test_method_data = method_data
            
            if not test_method_data or not prod_method_data:
                continue 

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
                if target_name not in contract_hashes:
                    contract_hashes[target_name] = {}
                contract_hashes[target_name][method_name_clean] = method_contract
            
    # 3. Scrittura JSON e Ritorno
    json_path = main_path.replace('.py', '.contract.json')
    # json_content = json.dumps(contract_hashes, indent=4)
    # await backend(path=json_path, content=json_content, mode='w') 

    framework_log("INFO", f"✅ Generato e scritto il contratto JSON in {json_path}")
    
    return {'data': {main_path: contract_hashes}, 'success': True}

genera = {
    'module': generate_checksum,
    'identifier': lambda: asyncio.sleep(0, str(uuid.uuid4())),
}

async def generate(data, schema=None):
    func = genera.get(schema)
    if not func:
        raise ValueError(f"Nessuna funzione di generazione per le chiavi: {schema}")
    return await func(data)

# =====================================================================
# --- Funzioni di Caricamento --- CDDF (Contract-Driven Dependency Filter)
# =====================================================================

# =====================================================================
# --- Helper per _validate_and_filter_module (CDDF) ---
# =====================================================================

async def _load_contract_info(main_module, path):
    """Carica il contratto JSON e le info dal modulo di test."""
    #framework_log("TRACE", f"Caricamento e validazione contratto per {path}", emoji="📜", module=main_module)
    framework_log("TRACE", f"Caricamento e validazione contratto per {path}", emoji="📜")
    # 1. Caricamento contratto JSON
    contract_json_path = path.replace('.py', '.contract.json')
    external_contracts = {}
    try:
        json_content = await _load_resource(path=contract_json_path)
        external_contracts = await convert(json_content, dict, 'json')
        framework_log("TRACE", f"Contratto JSON esterno caricato da {contract_json_path}.")
    except Exception as e:
        framework_log("WARNING", f"Nessun contratto JSON valido trovato in {contract_json_path}. Filtro hash disabilitato.", e)

    # 2. Caricamento modulo di test
    contract_path = path.replace('.py', '.test.py')
    contract_module_res = await resource(path=contract_path)
    # Estrai modulo se resource() ritorna un wrapper
    contract_module = contract_module_res.get('data') if isinstance(contract_module_res, dict) and 'data' in contract_module_res else contract_module_res
    
    # Analisi statica del codice di test
    contract_code = await _load_resource(path=contract_path)
    contract_ana = analyze_module(contract_code, contract_path)

    return {
        'external_contracts': external_contracts,
        'contract_module': contract_module,
        'contract_ana': contract_ana
    }

def _resolve_exports_map(main_module, contract_info):
    """Costruisce la mappa degli exports basata sul modulo di test o sul contratto JSON."""
    contract_module = contract_info['contract_module']
    external_contracts = contract_info['external_contracts']
    
    # Tentativo primario: exports definito in .test.py
    exports_map = getattr(contract_module, 'exports', {}) if isinstance(getattr(contract_module, 'exports', None), dict) else {}
    
    if exports_map:
        framework_log("TRACE", f"🔐 exports trovato: {list(exports_map.keys())}")
        return exports_map
        
    # Tentativo secondario: derivazione da .contract.json
    framework_log("WARNING", "⚠️ Nessun 'exports' dichiarato: generazione automatica da contratto se disponibile.")
    if external_contracts:
        for k, v in external_contracts.items():
            if k == '__module__' and isinstance(v, dict):
                for method_name in v.keys():
                    exports_map[method_name] = method_name
            else:
                exports_map[k] = k
    
    if not exports_map:
        framework_log("WARNING", "⚠️ Nessun 'exports' dichiarato e nessun contratto utilizzabile.")
    
    return exports_map

async def _validate_checksums(main_module, path, contract_info):
    """Valida gli hash dei metodi se presente un contratto esterno."""
    external_contracts = contract_info['external_contracts']
    contract_module = contract_info['contract_module']
    
    ccc_envelope = await generate_checksum(path)
    ccc = ccc_envelope.get('data', {}) if isinstance(ccc_envelope, dict) else ccc_envelope

    if not external_contracts:
        framework_log("TRACE", f"Using Auto-Trust (CCC generated) for {path}", emoji="🛡️")
        return {} # Nessuna validazione strict richiesta

    framework_log("TRACE", f"Using External Contract for {path}: {list(external_contracts.keys())}", emoji="📜")
    
    contract_validated_methods = {}
    
    for tgt, group in external_contracts.items():
        if not isinstance(group, dict): continue
            
        prod_obj = main_module if tgt == '__module__' else getattr(main_module, tgt, None)
        test_obj = getattr(contract_module, 'TestModule' if tgt == '__module__' else f'Test{tgt}', None)
        
        if not prod_obj or not test_obj: continue

        valid = set()
        for m, hashes in group.items():
            if not (isinstance(hashes, dict) and 'production' in hashes and 'test' in hashes): continue
            
            # Verifica che esistano metodi corrispondenti
            if getattr(prod_obj, m, None) is None or getattr(test_obj, f'test_{m}', None) is None:
                continue

            expected_p = hashes['production']
            expected_t = hashes['test']
            current_p = ccc.get(path,{}).get(tgt,{}).get(m,{}).get('production','')
            current_t = ccc.get(path,{}).get(tgt,{}).get(m,{}).get('test','')
            
            if current_p == expected_p and current_t == expected_t:
                valid.add(m)
            else:
                framework_log("ERROR", f"Hash mismatch per '{m}' in {path}: il codice è stato modificato rispetto al contratto (P:{current_p[:8]}... vs E:{expected_p[:8]}...).", emoji="🚫") 
                framework_log("DEBUG", f"Integrità: L'attributo '{m}' in {path} è stato rimosso dal modulo per violazione del contratto.", emoji="🛡️")
        if valid:
            contract_validated_methods[tgt] = valid
            
    return contract_validated_methods

def _compute_allowed_exports(main_module, exports_map, contract_info, validated_methods):
    """Calcola l'insieme finale dei membri esportabili e validati."""
    contract_ana = contract_info['contract_ana']
    
    # Mappa metodi testati esplicitamente
    # contract_ana struttura: { 'TestClasse': {'data': {'methods': {'test_metodo': ...}}} }
    contract_methods_by_name = {
        ('__module__' if mname == 'TestModule' else mname.replace('Test', '')):
            {tn.replace('test_', '') for tn in (data.get('data', {}).get('methods', {}) or {}).keys() if tn.startswith('test_')}
        for mname, data in contract_ana.items() if isinstance(data, dict)
    }

    allowed_exports = {
        public 
        for public, priv in exports_map.items()
        for candidate in [public] + ([priv] if isinstance(priv, str) else [])
        if hasattr(main_module, candidate) and (
            not contract_info.get('external_contracts') # Auto-Trust: allow all exported
            or
            (inspect.isclass(getattr(main_module, candidate)) and 
                (contract_methods_by_name.get(candidate) or validated_methods.get(candidate))) 
            or
            (inspect.isfunction(getattr(main_module, candidate)) and 
                (candidate in contract_methods_by_name.get('__module__', {}) and candidate in validated_methods.get('__module__', {})))
        )
    }
    
    # Force include 'language'
    allowed_exports.add('language')
    exports_map['language'] = 'language'
    
    return allowed_exports

def _create_filtered_module(main_module, exports_map, allowed_exports, validated_methods, contract_info):
    """Crea un nuovo oggetto modulo popolandolo solo con i membri validati."""
    path = main_module.__file__ if hasattr(main_module, '__file__') else "unknown"
    contract_ana = contract_info['contract_ana']
    
    # Ricostruiamo la mappa metodi testati che serve qui dentro
    contract_methods_by_name = {
        ('__module__' if mname == 'TestModule' else mname.replace('Test', '')):
            {tn.replace('test_', '') for tn in (data.get('data', {}).get('methods', {}) or {}).keys() if tn.startswith('test_')}
        for mname, data in contract_ana.items() if isinstance(data, dict)
    }
    
    filtered_module = types.ModuleType(f"filtered:{main_module.__name__}")
    if hasattr(main_module, '__file__'):
        filtered_module.__file__ = main_module.__file__

    validated_members_log = []

    if not exports_map:
        framework_log("WARNING", "⚠️ Nessun 'exports' dichiarato: file vuoto.")
        return filtered_module

    for public_name, private_spec in exports_map.items():
        private_name = private_spec if isinstance(private_spec, str) else public_name
        
        if public_name not in allowed_exports:
            continue
        if not hasattr(main_module, private_name):
            continue

        member = getattr(main_module, private_name)
        
        if inspect.isclass(member):
            # Shallow clone class
            attrs = {k: v for k, v in member.__dict__.items()}
            attrs['__module__'] = filtered_module.__name__
            FilteredClass = type(member.__name__, member.__bases__, attrs)
            
            valid_set = validated_methods.get(member.__name__, set()) or contract_methods_by_name.get(member.__name__, set())
            
            # Prune methods not validated
            for attr_name, _ in inspect.getmembers(FilteredClass, inspect.isfunction):
                if attr_name.startswith('__') or attr_name.startswith('_'): continue
                if attr_name not in valid_set:
                    try: delattr(FilteredClass, attr_name)
                    except: pass
                else:
                    validated_members_log.append(f"{public_name}.{attr_name}")
            
            setattr(filtered_module, public_name, FilteredClass)
            validated_members_log.append(public_name)

        elif inspect.isfunction(member):
            # Apply decorators logic if needed (simplified here just copying member)
            # Re-applying logic from original:
            new_member = member
            if inspect.iscoroutinefunction(member):
                try:
                    deco = asynchronous(custom_filename=path)
                    new_member = deco(member)
                except Exception: pass
            else:
                try:
                    deco = synchronous(custom_filename=path)
                    new_member = deco(member)
                except Exception: pass

            setattr(filtered_module, public_name, new_member)
            validated_members_log.append(public_name)
            
        elif inspect.ismodule(member):
            setattr(filtered_module, public_name, member)
            validated_members_log.append(public_name)

    framework_log("INFO", f"✅ Validazione riuscita per {path}. Esposti: {validated_members_log}")
    return filtered_module


async def _validate_and_filter_module(main_module: types.ModuleType, path: str) -> types.ModuleType:
    if isinstance(main_module, dict) and 'success' in main_module and not main_module['success']:
         raise ImportError(f"Modules load failed: {main_module.get('errors')}")

    # Esecuzione Pipeline CDDF referenced
    # Nota: flow.pipe passa l'output di uno step come primo argomento del successivo.
    # Qui però abbiamo bisogno di 'accumulare' info. flow.pipe base è lineare.
    # Useremo chiamate dirette per semplicità o dovremmo adattare gli step per ritornare (main_module, context...)
    
    # 1. Info Contratto
    contract_info = await _load_contract_info(main_module, path)
    
    # 2. Risoluzione Exports
    exports_map = _resolve_exports_map(main_module, contract_info)
    
    # 3. Validazione Checksum
    validated_methods = await _validate_checksums(main_module, path, contract_info)
    
    # 4. Calcolo Allowed Exports
    allowed_exports = _compute_allowed_exports(main_module, exports_map, contract_info, validated_methods)
    
    # 5. Creazione Modulo Filtrato
    return _create_filtered_module(main_module, exports_map, allowed_exports, validated_methods, contract_info)

async def _load_dependencies(module: types.ModuleType, dependencies) -> None:
    """Risolve le dipendenze 'imports' definite in un modulo."""
    
    for key, import_path in dependencies.items():
        cache_key = import_path
        if isinstance(import_path, str) and import_path.endswith('.py'):
            if cache_key in container.module_cache():
                value = container.module_cache()[cache_key]
                # buffered_log("DEBUG", f"♻️ {cache_key} Cache hit modulo Python")
                setattr(module, key, value)
                continue
            alt_key = import_path
            if alt_key in container.module_cache():
                value = container.module_cache()[alt_key]
                setattr(module, key, value)
                continue

        framework_log("TRACE", f"⏳ Caricamento dipendenza '{key}' da {import_path}...")
        res = await resource(path=import_path)
        value = res.get('data') if isinstance(res, dict) and 'data' in res else res
        setattr(module, key, value)
        container.module_cache()[import_path] = value
        framework_log("TRACE", f"📦 Dipendenza '{key}' caricata da {import_path}")

async def _load_python_module(name: str, path: str, code: str) -> types.ModuleType:
    """Crea ed esegue dinamicamente un modulo Python con le variabili globali necessarie."""
    module_name = f"{path}"
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__source__ = code
    module.__dict__['language'] = container.module_cache().get('framework/service/language.py')

    try:
        async with container.module_cache_lock():
            container.module_cache()[path] = module
            framework_log("TRACE", f"♻️ Placeholder module inserito nella cache per {path} (pre-caricamento)")
    except Exception:
        container.module_cache()[path] = module

    '''if module.__dict__['language'] is None and path not in ['src/framework/service/contract.test.py','src/framework/service/contract.py','src/framework/service/language.test.py','src/framework/service/language.py','framework/service/language.py']:
        framework_log("WARNING", "⚠️ Modulo di lingua non caricato prima delle dipendenze.", path)
        raise ImportError("Modulo di lingua mancante per le dipendenze.")'''
    
    try:
        dependencies = analyze_module(code, path)
        dependencies = dependencies.get('imports',{}).get('value',{})
        if path.replace('.test.py','.py',) in dependencies:
            del dependencies[path.replace('.test.py','.py')]
        
        framework_log("TRACE", f"🔍 Dipendenze trovate in {path}: {dependencies}")
        await _load_dependencies(module, dependencies.copy())
        compiled_code = compile(code, module_name, 'exec')
        exec(compiled_code, module.__dict__)
        container.module_cache()[path] = module
    except Exception as e:
        raise ImportError(f"Esecuzione modulo Python fallita per {path}: {e}") from e
    return module

async def resource(**kwargs) -> Any:
    """
    Carica una risorsa (JSON o modulo Python) e ne valida il contratto.
    """
    resource_path = kwargs.get('path', '')
    content = await _load_resource(path=resource_path)
    return await flow.switch({
        'match (regex ".json") @.path': flow.step(convert, content, dict, 'json'),
        'match (regex ".py") @.path': flow.step(flow.pipe,
            flow.step(_load_python_module, 'main_module', '@.path', content),
            flow.step(flow.switch, {
                '@.path | match (regex ".test.py")': flow.step(lambda x: x, '@.outputs.-1'),
                'true': flow.step(_validate_and_filter_module, '@.outputs.-1', resource_path),
            }),
        ),
        'true': flow.step(lambda: content),
    }, context={'path': resource_path})

# =====================================================================
# --- Helper per load_di_entry (Refactoring Flow) ---
# =====================================================================

def _check_di_config(**constants):
    """Valida la configurazione di ingresso per la DI."""
    path = constants.get('path')
    service = constants.get('service', constants.get('name'))
    adapter = constants.get('adapter', constants.get('service', constants.get('name')))
    if not path or not service or not adapter:
        framework_log("ERROR", f"❌ Errore: Configurazioni DI insufficienti: {constants}")
        raise ValueError(f"Configurazioni DI insufficienti: {constants}")
    return constants

def _ensure_service_container(service_name):
    """Assicura che il container abbia una lista per il servizio specificato."""
    if not hasattr(container, service_name):
        setattr(container, service_name, providers.Singleton(list))
    return service_name

def _extract_and_validate_module(res, constants):
    """Estrae il modulo dalla risposta di resource() e valida l'attributo."""
    path = constants.get('path')
    attribute_name = constants.get('adapter', constants.get('name'))
    
    module = res.get('data') if isinstance(res, dict) and 'data' in res else res
    
    if isinstance(module, dict):
        if 'success' in module and not module['success']:
             framework_log("CRITICAL", f"CRITICAL ERROR LOADING RESOURCE {path}: {module.get('errors')}", emoji="🛑")
             raise ImportError(f"Failed to load resource {path}: {module.get('errors')}")
        
        if not hasattr(module, attribute_name):
             framework_log("ERROR", f"DEBUG_ERROR: Module {path} is a dict without {attribute_name}", emoji="❌", module_data=module)
             raise AttributeError(f"Module {path} is a dict and lacks {attribute_name}")
    
    return module

def _register_dependency_in_container(module, constants):
    """Registra la classe/funzione nel container DI (come Factory o Singleton)."""
    service_name = constants.get('service', constants.get('name'))
    attribute_name = constants.get('adapter', constants.get('service', constants.get('name')))
    init_args = constants.get('payload', constants.get('config', {}))
    dependency_keys = constants.get('dependency_keys', None)
    path = constants.get('path')
    log_info = f"'{path}' con service '{service_name}' e attr '{attribute_name}'"

    resource_class = getattr(module, attribute_name)

    if dependency_keys:
        # --- CASO: MANAGER/FACTORY ---
        dependencies = {}
        for dep_key in dependency_keys:
            if not hasattr(container, dep_key):
                setattr(container, dep_key, providers.Singleton(list))
            dependencies[dep_key] = getattr(container, dep_key)()
        
        setattr(container, service_name, providers.Factory(resource_class, **init_args, providers=dependencies))
        framework_log("INFO", f"✅✅✅✅ Registrato Factory: '{service_name}' ({log_info})")
    else:
        # --- CASO: PROVIDER/SINGLETON ---
        if not hasattr(container, service_name):
            setattr(container, service_name, providers.Singleton(list))
        
        service_list = getattr(container, service_name)()
        service_list.append(resource_class(config=init_args))
        framework_log("INFO", f"✅✅✅✅ Aggiunto Provider a lista: '{service_name}' ({log_info})")
    
    return {"success": True, "results": []}

async def load_di_entry(**constants: Any) -> None:
    """
    Carica una risorsa specificata in 'constants' e la registra nel container DI globale usando flow.pipe.
    """
    #service_val = constants.get('service', constants.get('name'))
    try:
        await flow.pipe(
            flow.step(_check_di_config, **constants),
            #flow.step(_ensure_service_container, service_val),
            flow.step(_ensure_service_container, '@.service'),
            flow.step(resource, **constants),
            flow.step(_extract_and_validate_module, '@.outputs.-1', constants),
            flow.step(_register_dependency_in_container, '@.outputs.-1', constants)
        , context=constants)
    except Exception as e:
        framework_log("ERROR", f"Errore critico in load_di_entry per {constants.get('path')}: {e}", exception=e)
        raise e

# Alias per compatibilità o preferenza di nome
register = load_di_entry

# =====================================================================
# --- Funzioni Browser esistenti (Preservate) ---
# =====================================================================

def parse_browser_cookies(cookie_string: str) -> Dict[str, str]:
    if not cookie_string:
        return {}
    framework_log("DEBUG", "Parsing dei cookie in ambiente browser...")
    cookies_dict = {}
    try:
        for cookie_pair in cookie_string.split(';'):
            if '=' in cookie_pair:
                key, value = cookie_pair.split('=', 1)
                cookies_dict[key.strip()] = value
    except Exception as e:
        framework_log("ERROR", f"Errore critico durante il parsing dei cookie: {e}")
        return cookies_dict
    return cookies_dict

def tenta_recupero_sessione(session_value: str) -> Dict[str, Any]:
    session_data: Dict[str, Any] = {}
    if not session_value or session_value == 'None':
        return session_data
    for i in range(2):
        try:
            framework_log("DEBUG", f"Tentativo di eval() su sessione (Passo {i+1}): {session_value}")
            session_value = eval(session_value)
            if not isinstance(session_value, str) and i == 0:
                 break
        except Exception as e:
            framework_log("WARNING", f"Errore durante l'eval() della sessione al passo {i+1}. Dettaglio: {e}")
            return {} 
    
    if isinstance(session_value, dict):
        return session_value
    return {} 

async def installa_dipendenze_browser() -> None:
    if sys.platform != "emscripten":
        return
    framework_log("INFO", "Rilevato ambiente Pyodide. Avvio installazione dipendenze.")
    try:
        import micropip 
        packages_to_install = ["kink", "tomli", "jinja2", "untangle", "bs4", "lxml"]
        await micropip.install(packages_to_install)
        framework_log("INFO", f"Installazione di {len(packages_to_install)} pacchetti completata.")
    except ImportError:
        framework_log("CRITICAL", "Dipendenze Pyodide (micropip) non disponibili, ma sys.platform è 'emscripten'.")
        raise RuntimeError("Impossibile caricare micropip per l'installazione dipendenze.")

# =====================================================================
# --- Bootstrap (Orchestratore) ---
# =====================================================================

async def bootstrap_core(config) -> None:
    with log_block("Bootstrap Core Phases", level="INFO", emoji="🏗️"):
        # --- Telemetry Initialization ---
        tel_config = config.get('telemetry')
        if tel_config and tel_config.get('enabled', False):
            with log_block("Telemetry Initialization", level="DEBUG", emoji="📡"):
                await register(**{
                    'path': 'infrastructure/message/otel.py',
                    'service': 'telemetry',
                    'adapter': 'adapter',
                    'payload': tel_config | {'project': config.get('project', {}).get('name', 'sottomonte-app')}
                })

        manager_loader_path = [
            {
                'path': 'framework/manager/messenger.py', 
                'service': 'messenger', 
                'config': {'cache_enabled': True, 'log_level': 'INFO'},
                'dependency_keys': ['message'], 
                'messenger': 'messenger' 
            },
            {
                'path': 'framework/manager/executor.py', 
                'service': 'executor', 
                'config': {'cache_enabled': True, 'log_level': 'INFO'},
                'dependency_keys': ['actuator'], 
                'messenger': 'executor'
            },
            {
                'path': 'framework/manager/presenter.py',
                'service': 'presenter',
                'config': {'cache_enabled': True, 'log_level': 'INFO'},
                'dependency_keys': ['messenger'], 
                'messenger': 'presenter'
            },
            {
                'path': 'framework/manager/defender.py',
                'service': 'defender',
                'config': {'cache_enabled': True, 'log_level': 'INFO'},
                'dependency_keys': ['authentication'], 
                'messenger': 'defender' 
            },
            {
                'path': 'framework/manager/storekeeper.py',
                'service': 'storekeeper',
                'config': {'cache_enabled': True, 'log_level': 'INFO'},
                'dependency_keys': ['persistence'], 
                'messenger': 'storekeeper'
            },
            {
                'path': 'framework/manager/tester.py',
                'service': 'tester',
                'config': {'cache_enabled': True, 'log_level': 'INFO'},
                'dependency_keys': ['messenger','persistence'], 
                'messenger': 'tester' 
            }
        ]
        
        with log_block("Infrastructure Initialization", level="DEBUG", emoji="🛠️"):
            await register(**{
                'path': 'infrastructure/message/console.py', 
                'service': 'message', 
                'adapter': 'adapter', 
                'payload': config
            })

        with log_block("Manager Registration", level="DEBUG", emoji="🧩"):
            for mgr in manager_loader_path:
                await register(**mgr)

        if hasattr(container, 'messenger'):
            dependency_messenger = container.messenger()
            for log in container.log_buffer():
                await dependency_messenger.post(domain=log.get('level','DEBUG').lower(), message=log.get('message'))

async def bootstrap() -> None:
    env_config: Dict[str, Any] = dict(os.environ)
    session_data: Dict[str, Any] = {}
    identifier_val: str = 'None'
    
    if sys.platform == "emscripten":
        import js 
        await installa_dipendenze_browser()
        cookies: Dict[str, str] = parse_browser_cookies(str(js.document.cookie))
        session_str = cookies.get('session', 'None')
        identifier_val = cookies.get('session_identifier', 'None')
        session_data = tenta_recupero_sessione(session_str)
        
        config_params = {**env_config, "session": session_data, "identifier": identifier_val}
        platform_type = "Browser (Pyodide)"
    else:
        config_params = env_config | {"session": session_data}
        platform_type = "Server (Standard)"

    # IMPORTANTE: fetch era in language, ma ora resource (simile a fetch) è qui.
    # language.format e language.convert sono ancora in language.py.
    # Dobbiamo importare language qui o usare module_cache?
    # bootstrap dipende da language per `format` e `convert`.

    # Utilizziamo flow.pipe che gestisce automaticamente l'unwrapping dei dati
    # da {'success': True, 'data': ...} ritornati da resource()
    config = await flow.pipe(
        flow.step(resource, path="pyproject.toml"),
        flow.step(flow.format,'@.outputs.-1', **config_params),
        flow.step(flow.convert,'@.outputs.-1', dict, 'toml')
    )

    framework_log("DEBUG", f"Configurazione caricata: {config}", emoji="⚙️")
    await bootstrap_core(config)
    framework_log("INFO", "Bootstrap core completato.", emoji="🚀")

    dependency_executor = container.executor()
    dependency_messenger = container.messenger()

    await dependency_messenger.post(domain='debug', message="✅ Manager di base (Messenger, Executor) caricati e pronti.")
    await dependency_messenger.post(domain='debug', message=f"Configurazione caricata con successo (Ambiente: {platform_type}).")
    
    # --- FASE DI CARICAMENTO PROVIDER ---
    provider_tasks: List[asyncio.Task] = []
    MODULI_PRINCIPALI = ["presentation", "persistence", "message", "authentication", "actuator","authorization"]
    await dependency_messenger.post(domain='debug', message="Preparazione al caricamento dei Provider d'Infrastruttura...")

    for module_name in MODULI_PRINCIPALI:
        if module_name in config and isinstance(config,dict) and isinstance(config.get(module_name), dict):
            for driver_name, setting_data in config[module_name].items():
                adapter_name = setting_data.get("adapter")
                if not adapter_name:
                    await dependency_messenger.post(domain='error', message=f"Configurazione incompleta per '{module_name}/{driver_name}': Manca 'adapter'.")
                    continue
                
                payload_data = {**setting_data, "profile": driver_name, "project": config.get("project", "default")}
                ppp = {'path': f"infrastructure/{module_name}/{adapter_name}.py",
                'service': module_name, 
                'adapter': 'adapter', 
                'payload': payload_data,
                }
                task = asyncio.create_task(
                    register(**ppp),
                    name=f"{module_name}:{driver_name}"
                )
                provider_tasks.append(task)
                await dependency_messenger.post(domain='debug', message=f"Task creata: Provider {module_name} / Adattatore {adapter_name} ('{driver_name}').")
        else:
            await dependency_messenger.post(domain='warning', message=f"Nessuna configurazione trovata per i Provider del modulo '{module_name}'. Saltato.")

    await dependency_messenger.post(domain='debug', message=f"Avvio del caricamento parallelo di {len(provider_tasks)} Provider...")
    if provider_tasks:
        ok = await dependency_executor.all_completed(tasks=provider_tasks)
    
    await dependency_messenger.post(domain='debug', message="Caricamento di tutti i Provider completato.")

    # --- FASE DI AVVIO DEGLI ELEMENTI DI PRESENTAZIONE ---
    if not hasattr(container, 'presentation'):
        await dependency_messenger.post(domain='warning', message="Nessun elemento di 'Presentazione' trovato nel DI. Fase di caricamento saltata.")
        return
    presentation_elements: List[Any] = container.presentation() 
    event_loop = asyncio.get_event_loop()
    await dependency_messenger.post(domain='debug', message=f"Avvio dei caricatori ({len(presentation_elements)}) per gli elementi di Presentazione.")
    for item in presentation_elements:
        item_name = getattr(item, '__class__', item)
        if hasattr(item, "loader"):
            try:
                item.loader(loop=event_loop)
                await dependency_messenger.post(domain='debug', message=f"Loader eseguito con successo per {item_name}.")
            except Exception as e:
                await dependency_messenger.post(domain='error', message=f"ERRORE GRAVE: Il 'loader' dell'elemento {item_name} ha fallito. Dettaglio: {e}")
        else:
            await dependency_messenger.post(domain='debug', message=f"L'elemento {item_name} non ha un metodo 'loader'. Saltato.")

    await dependency_messenger.post(domain='debug', message="Framework avviato con successo. Sistema pronto e operativo.")