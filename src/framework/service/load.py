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
    buffered_log,
    _load_resource
)

# 1. Configurazione del Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(name)s.%(funcName)s] - %(message)s'
)
logger = logging.getLogger("BOOTSTRAPPER")

# =====================================================================
# --- Funzioni di Generazione (Spostate da language.py) ---
# =====================================================================

@asynchronous()
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
        buffered_log("INFO", f"Impossibile caricare i file sorgente o di test ({main_path} / {contract_path}).")
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

    buffered_log("INFO", f"✅ Generato e scritto il contratto JSON in {json_path}")
    
    return {main_path: contract_hashes}

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

async def _validate_and_filter_module(main_module: types.ModuleType, path: str, ) -> types.ModuleType:
    """
    Copia le classi e le funzioni dal main_module al filtered_module, mantenendo
    solo i membri che hanno un contratto valido e presente nel file .contract.json.
    """
    validated_members: List[str] = []
    # print()
    buffered_log("DEBUG", f"🔍 Avvio validazione contratto per il modulo: {path}", dir(main_module))
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
    # contract_module = await resource(path=contract_path) # Recursion risk? 
    # resource calls _load_python_module which works.
    # But resource checks if .test.py -> returns it directly. So OK.
    contract_module_res = await resource(path=contract_path)
    contract_module = contract_module_res.get('data') if isinstance(contract_module_res, dict) and 'data' in contract_module_res else contract_module_res

    exports_map = getattr(contract_module, 'exports', {}) if isinstance(getattr(contract_module, 'exports', None), dict) else {}
    if exports_map:
        buffered_log("DEBUG", f"🔐 exports trovato in {path}: {list(exports_map.keys())}")
    else:
        buffered_log("WARNING", "⚠️ Nessun 'exports' dichiarato: generazione automatica da contratto se disponibile.")
        if external_contracts:
            for k, v in external_contracts.items():
                if k == '__module__':
                    if isinstance(v, dict):
                        for method_name in v.keys():
                            exports_map[method_name] = method_name
                else:
                    exports_map[k] = k
        
        if not exports_map:
             buffered_log("WARNING", "⚠️ Nessun 'exports' dichiarato e nessun contratto utilizzabile: nessun membro sarà esposto automaticamente.")

    # Build map of test-targeted methods: {TargetName: {method1, method2}}
    contract_methods_by_name: Dict[str, set[str]] = {
        ('__module__' if mname == 'TestModule' else mname.replace('Test', '')):
            {tn.replace('test_', '') for tn in (data.get('data', {}).get('methods', {}) or {}).keys() if tn.startswith('test_')}
        for mname, data in contract_ana.items() if isinstance(data, dict)
    }

    # Validate hashes (compact loop)
    contract_validated_methods = {}
    ccc_envelope = await generate_checksum(path)
    ccc = ccc_envelope.get('data', {}) if isinstance(ccc_envelope, dict) else ccc_envelope

    if not external_contracts:
        print(f"DEBUG_LOADER: {path} - Using Auto-Trust (CCC generated)")
        buffered_log("WARNING", "⚠️ Nessun contratto JSON esterno. Uso gli hash generati (Auto-Trust).")
        external_contracts = ccc.get(path, {})
    else:
        print(f"DEBUG_LOADER: {path} - Using External Contract: {list(external_contracts.keys())}")

    for tgt, group in (external_contracts or {}).items():
        if not isinstance(group, dict):
            continue
        prod_obj = main_module if tgt == '__module__' else getattr(main_module, tgt, None)
        test_obj = getattr(contract_module, 'TestModule' if tgt == '__module__' else f'Test{tgt}', None)
        
        if not prod_obj or not test_obj:
            # buffered_log("WARNING", f"Oggetto produzione/test mancante per contratto: {tgt}")
            continue

        valid = set()
        for m, hashes in group.items():
            if not (isinstance(hashes, dict) and 'production' in hashes and 'test' in hashes):
                continue
            
            prod_func = getattr(prod_obj, m, None)
            test_func = getattr(test_obj, f'test_{m}', None)
            
            if prod_func is None or test_func is None:
                continue

            expected_prod_hash = hashes['production']
            expected_test_hash = hashes['test']

            current_prod_hash = ccc.get(path,{}).get(tgt,{}).get(m,{}).get('production','')
            current_test_hash = ccc.get(path,{}).get(tgt,{}).get(m,{}).get('test','')
            
            if current_prod_hash == expected_prod_hash and current_test_hash == expected_test_hash:
                valid.add(m)
            else:
                print(f"DEBUG_LOADER: Mismatch hash for {m}. P:{current_prod_hash} vs {expected_prod_hash}")
        
        if valid:
            contract_validated_methods[tgt] = valid

    buffered_log("DEBUG", f"🔍 Avvio filtro: membri mantenuti se presenti in {contract_json_path} e/o testati.")
    print(f"DEBUG_LOADER: Exports Map: {exports_map}")
    print(f"DEBUG_LOADER: Methods by Name: {contract_methods_by_name}")
    print(f"DEBUG_LOADER: Validated Methods: {contract_validated_methods}")
    print(f"DEBUG_LOADER: Allowed Exports (calc):")

    # Compute allowed exports
    allowed_exports = {
        public 
        for public, priv in exports_map.items()
        for candidate in [public] + ([priv] if isinstance(priv, str) else [])
        if hasattr(main_module, candidate) and (
            (inspect.isclass(getattr(main_module, candidate)) and (contract_methods_by_name.get(candidate) or contract_validated_methods.get(candidate))) or
            (inspect.isfunction(getattr(main_module, candidate)) and (candidate in contract_methods_by_name.get('__module__', {}) and candidate in contract_validated_methods.get('__module__', {})))
        )
    }
    print(f"DEBUG_LOADER: Allowed Exports: {allowed_exports}")
    allowed_exports = allowed_exports.union(set({'language'}))
    exports_map['language'] = 'language'
    buffered_log("DEBUG", f"🔍 Avvio filtro: membri mantenuti se presenti in {allowed_exports} e/o testati.")
    
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
                # shallow clone of class attributes
                attrs = {k: v for k, v in member.__dict__.items()}
                attrs['__module__'] = filtered_module.__name__
                FilteredClass = type(member.__name__, member.__bases__, attrs)
                setattr(filtered_module, public_name, FilteredClass)
                validated_members.append(public_name)

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
                if not hasattr(member, '_is_decorated'):
                    setattr(filtered_module, public_name, member)
                    validated_members.append(public_name)
                    pass
                if inspect.iscoroutinefunction(member):
                    try:
                        decorator_factory = asynchronous(
                            custom_filename=main_module.__file__ if hasattr(main_module, '__file__') else path,
                            app_context=None 
                        )
                        new_member = decorator_factory(member)
                        buffered_log("DEBUG", f"Decoratore 'asynchronous' applicato a funzione sincrona: {private_name}")
                    except Exception as ex:
                        buffered_log("ERROR", f"Impossibile applicare decoratore a {private_name}: {ex}")
                        new_member = member 
                else:
                    try:
                        decorator_factory = synchronous(
                            custom_filename=main_module.__file__ if hasattr(main_module, '__file__') else path,
                            app_context=None 
                        )
                        new_member = decorator_factory(member)
                        buffered_log("DEBUG", f"Decoratore 'synchronous' applicato a funzione: {private_name}")
                    except Exception as ex:
                        buffered_log("ERROR", f"Impossibile applicare decoratore SYNC a {private_name}: {ex}")
                        new_member = member 
                
                setattr(filtered_module, public_name, new_member)
                validated_members.append(public_name)
            elif inspect.ismodule(member):
                setattr(filtered_module, public_name, member)
                validated_members.append(public_name)
    else:
        buffered_log("WARNING", "⚠️ Nessun 'exports' dichiarato: nessun membro sarà esposto dal modulo filtrato.")

    buffered_log("INFO", f"✅ Validazione e filtro riusciti per {path}. Membri esposti: {validated_members}")
    return filtered_module

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

        buffered_log("DEBUG", f"⏳ Caricamento dipendenza '{key}' da {import_path}...")
        value = await resource(path=import_path)
        setattr(module, key, value)
        container.module_cache()[import_path] = value
        buffered_log("DEBUG", f"📦 Dipendenza '{key}' caricata da {import_path}")

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
            buffered_log("DEBUG", f"♻️ Placeholder module inserito nella cache per {path} (pre-caricamento)")
    except Exception:
        container.module_cache()[path] = module

    '''if module.__dict__['language'] is None and path not in ['src/framework/service/contract.test.py','src/framework/service/contract.py','src/framework/service/language.test.py','src/framework/service/language.py','framework/service/language.py']:
        buffered_log("WARNING", "⚠️ Modulo di lingua non caricato prima delle dipendenze.", path)
        raise ImportError("Modulo di lingua mancante per le dipendenze.")'''
    
    try:
        dependencies = analyze_module(code, path)
        dependencies = dependencies.get('imports',{}).get('value',{})
        if path.replace('.test.py','.py',) in dependencies:
            del dependencies[path.replace('.test.py','.py')]
        
        buffered_log("INFO", f"🔍 Dipendenze trovate in {path}: {dependencies}")
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

async def load_di_entry(**constants: Any) -> None:
    """
    Carica una risorsa specificata in 'constants' e la registra nel container DI globale.
    """
    path: str = constants.get('path', '')
    service_name: str = constants.get('service', constants.get('name', '')) 
    attribute_name: str = constants.get('adapter', constants.get('name', ''))
    init_args: Dict[str, Any] = constants.get('payload', constants.get('config', {}))
    dependency_keys = constants.get('dependency_keys', None)

    log_info = f"'{path}' con service '{service_name}' e attr '{attribute_name}'"

    if not path or not service_name or not attribute_name:
        buffered_log("ERROR", f"❌ Errore: Configurazioni DI insufficienti: {constants}")
        return
    
    if not hasattr(container, service_name):
        setattr(container, service_name, providers.Singleton(list))

    # Caricamento del Modulo/Risorsa 
    module = await resource(**constants)
    resource_class: Callable = getattr(module, attribute_name)

    if dependency_keys:
        # --- CASO: MANAGER/FACTORY ---
        dependencies: Dict[str, Any] = {}
        for dep_key in dependency_keys:
            if not hasattr(container, dep_key):
                setattr(container, dep_key, providers.Singleton(list))
            dependencies[dep_key] = getattr(container, dep_key)()
        
        setattr(container, service_name, providers.Factory(resource_class, **init_args, providers=dependencies))
        buffered_log("INFO", f"✅✅✅✅ Registrato Factory: '{service_name}' ({log_info})")
    else:
        # --- CASO: PROVIDER/SINGLETON ---
        if not hasattr(container, service_name):
            setattr(container, service_name, providers.Singleton(list))
        
        service_list = getattr(container, service_name)()
        service_list.append(resource_class(config=init_args))
        
        buffered_log("INFO", f"✅✅✅✅ Aggiunto Provider a lista: '{service_name}' ({log_info})")
        return { "success": True, "results": [] }

# Alias per compatibilità o preferenza di nome
register = load_di_entry

# =====================================================================
# --- Funzioni Browser esistenti (Preservate) ---
# =====================================================================

def parse_browser_cookies(cookie_string: str) -> Dict[str, str]:
    if not cookie_string:
        return {}
    logger.debug("Parsing dei cookie in ambiente browser...")
    cookies_dict = {}
    try:
        for cookie_pair in cookie_string.split(';'):
            if '=' in cookie_pair:
                key, value = cookie_pair.split('=', 1)
                cookies_dict[key.strip()] = value
    except Exception as e:
        logger.error(f"Errore critico durante il parsing dei cookie: {e}")
        return cookies_dict
    return cookies_dict

def tenta_recupero_sessione(session_value: str) -> Dict[str, Any]:
    session_data: Dict[str, Any] = {}
    if not session_value or session_value == 'None':
        return session_data
    for i in range(2):
        try:
            logger.debug(f"Tentativo di eval() su sessione (Passo {i+1}): {session_value}")
            session_value = eval(session_value)
            if not isinstance(session_value, str) and i == 0:
                 break
        except Exception as e:
            logger.warning(f"Errore durante l'eval() della sessione al passo {i+1}. Dettaglio: {e}")
            return {} 
    
    if isinstance(session_value, dict):
        return session_value
    return {} 

async def installa_dipendenze_browser() -> None:
    if sys.platform != "emscripten":
        return
    logger.info("Rilevato ambiente Pyodide. Avvio installazione dipendenze.")
    try:
        import micropip 
        packages_to_install = ["kink", "tomli", "jinja2", "untangle", "bs4", "lxml"]
        await micropip.install(packages_to_install)
        logger.info(f"Installazione di {len(packages_to_install)} pacchetti completata.")
    except ImportError:
        logger.critical("Dipendenze Pyodide (micropip) non disponibili, ma sys.platform è 'emscripten'.")
        raise RuntimeError("Impossibile caricare micropip per l'installazione dipendenze.")

# =====================================================================
# --- Bootstrap (Orchestratore) ---
# =====================================================================

async def bootstrap_core(config) -> None:
    # Nota: Usiamo language.register qui? No, usiamo la nostra register locale ora, 
    # ma language.py deve essere ancora disponibile.
    # Il codice originale chiamava `await language.register`. Ora `register` è qui.
    # Dobbiamo aggiornare le chiamate interne.
    
    manager_loader_path = [
        {
            'path': 'framework/manager/messenger.py', 
            'name': 'messenger', 
            'config': {'cache_enabled': True, 'log_level': 'INFO'},
            'dependency_keys': ['message'], 
            'messenger': 'messenger' 
        },
        {
            'path': 'framework/manager/executor.py', 
            'name': 'executor', 
            'config': {'cache_enabled': True, 'log_level': 'INFO'},
            'dependency_keys': ['actuator'], 
            'messenger': 'executor'
        },
        {
            'path': 'framework/manager/presenter.py',
            'name': 'presenter',
            'config': {'cache_enabled': True, 'log_level': 'INFO'},
            'dependency_keys': ['messenger'], 
            'messenger': 'presenter'
        },
        {
            'path': 'framework/manager/defender.py',
            'name': 'defender',
            'config': {'cache_enabled': True, 'log_level': 'INFO'},
            'dependency_keys': ['authentication'], 
            'messenger': 'defender' 
        },
        {
            'path': 'framework/manager/storekeeper.py',
            'name': 'storekeeper',
            'config': {'cache_enabled': True, 'log_level': 'INFO'},
            'dependency_keys': ['persistence'], 
            'messenger': 'storekeeper'
        },
        {
            'path': 'framework/manager/tester.py',
            'name': 'tester',
            'config': {'cache_enabled': True, 'log_level': 'INFO'},
            'dependency_keys': ['messenger','persistence'], 
            'messenger': 'tester' 
        }
    ]
    
    await register(**{
        'path': 'infrastructure/message/console.py', 
        'service': 'message', 
        'adapter': 'adapter', 
        'payload': config
    })

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
    import framework.service.language as language
    
    text = await resource(path="pyproject.toml")
    config = await language.format(text,**config_params)
    config = await convert(config, dict, 'toml')
    
    await bootstrap_core(config)
    
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