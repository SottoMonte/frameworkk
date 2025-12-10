from framework.service.context import container
from dependency_injector import providers
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
import types 
import inspect
import contextvars
from cerberus import Validator, TypeDefinition, errors
import functools
from typing import Dict, Any, Optional, List, Callable
import asyncio
from lark import Lark, Transformer, v_args, Token
import mistql


from framework.service.flow import (
    asynchronous, 
    synchronous, 
    get_transaction_id, 
    set_transaction_id,
    _transaction_id,
    convert
)
import framework.service.flow as flow

from framework.service.inspector import (
    LogReportEncoder,
    analyze_module,
    analyze_exception,
    calculate_hash_of_function,
    estrai_righe_da_codice,
    _get_system_info,
    buffered_log,
    _load_resource
)
# Cache e stack per prevenire loop e ricaricamenti ripetuti
# Ora registrati in DI per poterli sovrascrivere / mockare facilmente.
# Cache e stack per prevenire loop e ricaricamenti ripetuti
# Ora registrati in DI per poterli sovrascrivere / mockare facilmente.
# Gestiti da container.py

def _get_module_cache() -> Dict[str, types.ModuleType]:
    return container.module_cache()


def _get_loading_stack():
    return container.loading_stack()

# =====================================================================
# --- Funzioni di Generazione ---
# =====================================================================


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

async def _validate_and_filter_module(main_module: types.ModuleType, path: str, ) -> types.ModuleType:
    """
    Copia le classi e le funzioni dal main_module al filtered_module, mantenendo
    solo i membri che hanno un contratto valido e presente nel file .contract.json.
    """
    validated_members: List[str] = []
    print()
    buffered_log("DEBUG", f"🔍 Avvio validazione contratto per il modulo: {path}",dir(main_module))
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
    allowed_exports  = allowed_exports.union(set({'language'}))
    exports_map['language'] = 'language'
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
            # Questo evita di coprire oggetti interni di Python (es. '__builtins__') 
            # o il modulo che stiamo filtrando.
            if name not in sys.builtin_module_names and name not in ['__file__', '__name__', '__package__', '__loader__', '__spec__', main_module.__name__]:
                # Condizione 3: Non inizia con un underscore nascosto (se non vuoi coprire importazioni "private")
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
                if not hasattr(member, '_is_decorated'):
                    setattr(filtered_module, public_name, member)
                    validated_members.append(public_name)
                    pass
                if inspect.iscoroutinefunction(member):
                    try:
                        # Chiama il decoratore (asynchronous(...)) e poi applicalo alla funzione (member)
                        decorator_factory = asynchronous(
                            custom_filename=main_module.__file__ if hasattr(main_module, '__file__') else path,
                            app_context=None 
                        )
                        new_member = decorator_factory(member)
                        buffered_log("DEBUG", f"Decoratore 'asynchronous' applicato a funzione sincrona: {private_name}")
                    
                    except Exception as ex:
                        buffered_log("ERROR", f"Impossibile applicare decoratore a {private_name}: {ex}")
                        new_member = member # Fallback: usa la funzione originale
                else:
                    # Caso 2: È sincrona. Applica il decoratore.
                    
                    try:
                        # Chiama il decoratore SYNCHRONOUS con i parametri necessari
                        decorator_factory = synchronous(
                            custom_filename=main_module.__file__ if hasattr(main_module, '__file__') else path,
                            app_context=None # Usa il contesto appropriato
                        )
                        
                        # Applica il decoratore
                        new_member = decorator_factory(member)
                        buffered_log("DEBUG", f"Decoratore 'synchronous' applicato a funzione: {private_name}")
                    
                    except Exception as ex:
                        buffered_log("ERROR", f"Impossibile applicare decoratore SYNC a {private_name}: {ex}")
                        new_member = member # Fallback alla funzione originale
                
                setattr(filtered_module, public_name, new_member)
                validated_members.append(public_name)
                #setattr(filtered_module, public_name, member)
                #validated_members.append(public_name)
            elif inspect.ismodule(member):
                setattr(filtered_module, public_name, member)
                validated_members.append(public_name)
    else:
        buffered_log("WARNING", "⚠️ Nessun 'exports' dichiarato: nessun membro sarà esposto dal modulo filtrato.")

    buffered_log("INFO", f"✅ Validazione e filtro riusciti per {path}. Membri esposti: {validated_members}")
    return filtered_module

async def _load_dependencies(module: types.ModuleType,dependencies) -> None:
    """Risolve le dipendenze 'imports' definite in un modulo."""
    
    for key, import_path in dependencies.items():
        # Normalizza percorso usato come chiave cache (stesso formato di _load_python_module)
        cache_key = import_path
        # Se è già nel cache, riutilizza (DEBUG). Proviamo anche la forma risolta ('src/...')
        if isinstance(import_path, str) and import_path.endswith('.py'):
            if cache_key in container.module_cache():
                value = container.module_cache()[cache_key]
                buffered_log("DEBUG", f"♻️ {cache_key} Cache hit modulo Python da {dir(value)}")
                setattr(module, key, value)
                buffered_log("DEBUG", f"♻️ Cache hit per dipendenza '{key}' da {cache_key}")
                continue
            # Fallback: risolvi il percorso (es. 'framework/..' -> 'src/framework/...')
            alt_key = import_path
            if alt_key in container.module_cache():
                value = container.module_cache()[alt_key]
                buffered_log("DEBUG", f"♻️ {alt_key} Cache hit modulo Python da {dir(value)} (resolved)")
                setattr(module, key, value)
                buffered_log("DEBUG", f"♻️ Cache hit per dipendenza '{key}' da {alt_key} (resolved)")
                continue

        buffered_log("DEBUG", f"⏳ Caricamento dipendenza '{key}' da {import_path}...")


        '''try:
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
            value = imported_content'''
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

    #if di['module_cache'].get('framework/service/language.py') is None:
    #    raise('errore modulo language = None')


    # Inseriamo un placeholder nella cache PRIMA di risolvere le dipendenze.
    # Serve a interrompere cicli di importazione: se il .test.py importa il
    # modulo sotto test, troverà qui un ModuleType (parzialmente inizializzato)
    # invece di riavviare un caricamento ricorsivo.
    try:
        async with container.module_cache_lock():
            container.module_cache()[path] = module
            buffered_log("DEBUG", f"♻️ Placeholder module inserito nella cache per {path} (pre-caricamento)")
    except Exception:
        # Fallback non-bloccante se il lock non è disponibile
        container.module_cache()[path] = module

    if module.__dict__['language'] is None and path not in ['src/framework/service/contract.test.py','src/framework/service/contract.py','src/framework/service/language.test.py','src/framework/service/language.py','framework/service/language.py']:
        buffered_log("WARNING", "⚠️ Modulo di lingua non caricato prima delle dipendenze.",path)
        raise ImportError("Modulo di lingua mancante per le dipendenze.")
    
    
    try:
        dependencies = analyze_module(code, path)
        dependencies = dependencies.get('imports',{}).get('value',{})
        if path.replace('.test.py','.py',) in dependencies:
            del dependencies[path.replace('.test.py','.py')]
        #    dependencies['language'] = 'framework/service/language.py'
        buffered_log("INFO", f"🔍 Dipendenze trovate in {path}: {dependencies}")
        await _load_dependencies(module,dependencies.copy())
        # 2. Compila il codice con il nome del file
        compiled_code = compile(code, module_name, 'exec')
        exec(compiled_code, module.__dict__)
        # salva nel cache globale per riusi futuri (evita ricaricamenti ripetuti)
        container.module_cache()[path] = module
    except Exception as e:
        raise ImportError(f"Esecuzione modulo Python fallita per {path}: {e}") from e
    return module

async def resource(**kwargs) -> Any:
    """
    Carica una risorsa (JSON o modulo Python) e ne valida il contratto.
    
    Argomenti:
        lang (str): La lingua da iniettare nei moduli Python.
        path (str | None): Il percorso della risorsa.
    """
    
    resource_path = kwargs.get('path', '')
    content = await _load_resource(path=resource_path)
    return await flow.switch(resource_path,{
        'match (regex ".json") @':flow.step(convert,content, dict, 'json'),
        'match (regex ".py") @':flow.step(flow.pipe,resource_path,
            flow.step(_load_python_module,'main_module','input',content),
            flow.step(flow.switch,'outputs',{
                '@ | match (regex ".test.py")':flow.step(lambda x: x,'@'),
                'true':flow.step(_validate_and_filter_module,'@',resource_path),
            }),
        ),
        'true':flow.step(lambda : content),
    })

    '''if resource_path.endswith(".json"):
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
    return content'''

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
    if not hasattr(container, service_name):
        setattr(container, service_name, providers.Singleton(list))

    
    # 4. Caricamento del Modulo/Risorsa (Usando il path fornito)
    print('################################',constants)
    module = await resource(**constants)
    print('------------------>',module)
    resource_class: Callable = getattr(module, attribute_name)

    # 5. Definizione della Factory/Resolver
    
    if dependency_keys:
        # --- CASO: MANAGER/FACTORY (Istanziamento lazy con dipendenze) ---
        
        dependencies: Dict[str, Any] = {}
        for dep_key in dependency_keys:
            if not hasattr(container, dep_key):
                setattr(container, dep_key, providers.Singleton(list))
                
            # Salva il resolver della dipendenza
            dependencies[dep_key] = getattr(container, dep_key)()
        
        #print(f"⏳ Caricamento Manager: '{service_name}' ({log_info}) con dipendenze {dependencies}",dependency_keys)
        # Registra Factory
        setattr(container, service_name, providers.Factory(resource_class, **init_args, providers=dependencies))
        buffered_log("INFO", f"✅✅✅✅ Registrato Factory: '{service_name}' ({log_info})")

    else:
        # --- CASO: PROVIDER/SINGLETON (Istanziamento eager in una lista) ---
        if not hasattr(container, service_name):
            setattr(container, service_name, providers.Singleton(list))
        
        print(constants,resource_class)
        #provider = getattr(module, 'adapter')
        
        # Recupera la lista e aggiungi l'istanza
        service_list = getattr(container, service_name)()
        service_list.append(resource_class(config=init_args))
        
        buffered_log("INFO", f"✅✅✅✅ Aggiunto Provider a lista: '{service_name}' ({log_info})")
        return { "success": True, "results": [] }


# ----------------------------------------------------------------------
# --- 1. Definizione della Grammatica (DSL Rules) - CORRETTA V18 ---
# ----------------------------------------------------------------------

grammar = r"""
    start:  [dictionary] 

    // --- TOKEN ---
    COMPARISON_OP: "==" | "!=" | ">=" | "<=" | ">" | "<"
    PIPE: "|"
    #LPAR: "("
    #RPAR: ")"
    #LBRACE: "{"
    #RBRACE: "}"
    #COMMA: ","
    #COLON: ":"
    #SEMICOLON: ";"
    QUALIFIED_CNAME: CNAME ("." CNAME)+
    COMMENT: /#[^\n]*/
    #NATURAL: natural
    #INTEGER: integer
    #RATIONAL: rational
    #IRRATIONAL: irrational
    #REAL: real
    #COMPLEX: complex
    #BOOLEAN: boolean
    #STRING: string

    property_access: (CNAME | ESCAPED_STRING) ("." (CNAME | ESCAPED_STRING))*

    value: SIGNED_NUMBER -> number
        | ESCAPED_STRING -> string
        | "Vero" -> true
        | "Falso" -> false
        | CNAME -> simple_key
        | QUALIFIED_CNAME-> simple_key
    
    // Rimosso 'expression' da 'case' per evitare ricorsione ambigua
    case.8 : value -> valor
           | dictionary -> valor
           | pair -> valor
           | tuple -> valor
           
    
    // Dizionario
    dictionary.10: "{" (pair ";")* ";"?  "}" | (pair ";")*

    // Pair - Ora accetta espressioni esplicitamente
    pair_statement.10: expression ":" expression | tuple_inline ":" expression | expression ":" tuple_inline
    pair: "(" pair_statement ")" | pair_statement
    
    // Tuple - Ora accetta espressioni
    tuple: "(" [ expression ("," expression)*] ")" -> tuple_
    tuple_inline: [expression "," expression ("," expression)*] -> tuple_

    // Unità di base (CNAME, Stringa, Numero, Booleano, o Case precedente)
    atom: ESCAPED_STRING | SIGNED_NUMBER | "Vero" | "Falso" | CNAME | dictionary | pair | tuple

    // Espressione che include atomi e operatori logici/matematici
    ?logical_expression: case
        | logical_expression COMPARISON_OP case

    expression: logical_expression (PIPE logical_expression)* -> expression

    // Importazione dei Token standard di Lark
    %import common.SIGNED_NUMBER
    %import common.ESCAPED_STRING
    %import common.CNAME
    %import common.LETTER
    %import common.WS

    // Ignora spazi bianchi e commenti
    %ignore WS
    %ignore COMMENT
"""

@v_args(inline=True)
class ConfigTransformer(Transformer):
    
    def start(self, *items):
        if not items:
            return {}
        return items[0]
        
    # --- Funzioni del Transformer ---

    def pair_statement(self, key, value):
        # key è già stato elaborato da expression ma potrebbe non essere stringa
        return str(key), value

    def dictionary(self, *statements):
        return dict(statements)

    def expression(self, *items):
        #print(f"{items} |EXPRESSION")
        
        # Filtra i token PIPE e mantiene solo gli operandi
        pipeline = []
        for item in items:
            if isinstance(item, Token) and item.type == 'PIPE':
                continue
            pipeline.append(item)
        
        # Se c'è un solo elemento, restituiscilo direttamente (appiattimento)
        if len(pipeline) == 1:
            return pipeline[0]
            
        # Restituisce una tupla identificativa e la lista di operazioni
        return ('EXPRESSION', pipeline)

    def tuple_(self, *items):
        #print(f"{items} |TUPLE", len(items))
        
        # 1. Filtra eventuali elementi None (da optional?)
        lista_filtrata = [elemento for elemento in items if elemento is not None]

        # 2. Scapsulamento se singolo elemento (permette raggruppamento (expr))
        if len(lista_filtrata) == 1:
            return lista_filtrata[0] 
        
        # 3. Altrimenti tupla
        return tuple(lista_filtrata)

    def inline_dict(self, key, value):
        #print(f"{key}: {value} |INLINE DICT")
        return str(key), value

    # --- Tipi Primitivi ---

    def number(self, n):
        n_str = str(n)
        return float(n_str) if '.' in n_str and 'E' not in n_str.upper() else int(n_str)

    def string(self, s):
        return str(s).strip('"')

    def true(self): return True
    def false(self): return False
    
    def simple_key(self, s):
        return str(s)

    def valor(self, s):
        return s
    
    # --- Liste/Tuple ---

    def pair(self, *items):
        # Gestisce eventuali parentesi attorno a pair
        return items[0] if items else None
        
    # --- Strutture Complesse ---
    
    def pipeline(self, s):
        return str(s).strip()

class DSLVisitor:
    """
    Visitatore che attraversa il dizionario risultante dal parsing
    ed esegue le espressioni marcate come 'EXPRESSION'.
    Supporta funzioni definite in Python (functions_map) e nel DSL stesso.
    """
    def __init__(self, functions_map=None):
        self.functions_map = functions_map or {}
        self.root_data = {} # Contesto globale del DSL per lookup funzioni

    def run(self, data):
        """Metodo di ingresso che imposta il contesto globale."""
        self.root_data = data
        return self.visit(data)

    def visit(self, node):
        if isinstance(node, dict):
            # Visita ricorsiva per ogni valore del dizionario
            return {k: self.visit(v) for k, v in node.items()}
        elif isinstance(node, list):
            # Visita ricorsiva per le liste
            return [self.visit(x) for x in node]
        elif isinstance(node, tuple):
            # Controlla se è un'espressione da eseguire
            if len(node) > 0 and node[0] == 'EXPRESSION':
                return self.evaluate_expression(node[1])
            else:
                # Altrimenti visita gli elementi della tupla
                return tuple(self.visit(x) for x in node)
        else:
            return node

    def evaluate_expression(self, pipeline_ops):
        """
        Esegue la pipeline di operazioni.
        Esempio: [valore, func1, func2] -> func2(func1(valore))
        """
        result = None
        
        for i, op in enumerate(pipeline_ops):
            if i == 0:
                # Il primo elemento è il valore iniziale
                result = self.visit(op) 
            else:
                # Funzioni/Operazioni
                func_name = str(op)
                
                # 1. Cerca nelle funzioni Python mappate
                if func_name in self.functions_map:
                    try:
                        result = self.functions_map[func_name](result)
                    except Exception as e:
                        print(f"[{func_name}] Errore esecuzione Python: {e}")
                
                # 2. Cerca nelle funzioni definite nel DSL (root_data)
                elif func_name in self.root_data:
                    dsl_def = self.root_data[func_name]
                    # Euristica: una funzione DSL è definita come una tupla di 3 elementi:
                    # (Args), {Body}, (Ret)
                    # Oppure (Args, Body, Ret) se wrappata in tupla
                    if isinstance(dsl_def, tuple) and len(dsl_def) == 3:
                        try:
                            #print(f"[{func_name}] Esecuzione funzione DSL...")
                            result = self.execute_dsl_function(dsl_def, result)
                        except Exception as e:
                            print(f"[{func_name}] Errore esecuzione DSL: {e}")
                    else:
                         print(f"[{func_name}] Trovato nel DSL ma formato non valido per funzione: {type(dsl_def)}")
                
                else:
                    print(f"[{func_name}] Funzione NON trovata (Python o DSL).")
                    
        return result

    def execute_dsl_function(self, func_def, input_args):
        """
        Esegue una funzione definita nel DSL.
        Firma attesa: ( (Inputs...), { Body... }, (Outputs...) )
        """
        inputs_def, body_def, outputs_def = func_def
        
        # --- 1. Mappatura Input ---
        # inputs_def può essere una tupla di coppie (es: (integer:a, float:b)) o una singola coppia
        # input_args può essere un valore singolo o una tupla
        
        local_context = {}
        
        # Normalizzazione inputs_def in lista di (type, name) o (name)
        input_params = []
        
        # Helper per estrarre il nome parametro da una definizione (che può essere coppia 'tipo:nome' o solo 'nome')
        def extract_param_name(p):
            # Se è una coppia (es: ('integer', 'a')), il nome è 'a'
            if isinstance(p, tuple) and len(p) == 2:
                return str(p[1]) # Secondo elem è il nome
            return str(p)

        # Se inputs_def è una tupla che contiene stringhe E non è una coppia ('tipo', 'val')
        # Ma (tipo, val) è una tupla.
        # Caso singolo parametro: inputs_def = ('integer', 'a')
        # Caso multi parametro: inputs_def = ( ('integer', 'a'), ('float', 'b') )
        
        if isinstance(inputs_def, tuple) and len(inputs_def) == 2 and isinstance(inputs_def[0], str):
             # È una singola coppia ('tipo', 'nome') -> un solo parametro
             input_params.append(extract_param_name(inputs_def))
        elif isinstance(inputs_def, tuple):
             # È una tupla di parametri
             for p in inputs_def:
                 input_params.append(extract_param_name(p))
        else:
             # Fallback, magari è solo il nome 'a'
             input_params.append(str(inputs_def))
             
        # Mapping valori
        if len(input_params) == 1:
            # Un solo parametro riceve tutto l'input
            local_context[input_params[0]] = input_args
        else:
            # Più parametri: input_args deve essere iterabile (tupla/lista)
            if not isinstance(input_args, (list, tuple)):
                 print(f"Errore: Attesi {len(input_params)} argomenti, ricevuto singolo scalare: {input_args}")
                 return None
            if len(input_args) != len(input_params):
                 print(f"Errore: Mismatch argomenti. Attesi {len(input_params)}, ricevuti {len(input_args)}")
                 return None
            
            for name, val in zip(input_params, input_args):
                local_context[name] = val
                
        # --- 2. Esecuzione Body ---
        # body_def è un dizionario (es: {'output': "a + b"})
        
        for key, expr_str in body_def.items():
            try:
                # Valuta la stringa come espressione Python
                # Permette operazioni base (a + b, ecc)
                #val = eval(str(expr_str), {}, local_context)
                val = mistql.query(str(expr_str), data=local_context)
                local_context[str(key)] = val
            except Exception as e:
                print(f"Errore valutazione espressione '{expr_str}': {e}")
                
        # --- 3. Return Output ---
        # outputs_def definisce cosa ritornare (es: (float:output))
        # Estraiamo il nome della variabile da ritornare
        ret_val = None
        
        output_vars = []
        if isinstance(outputs_def, tuple) and len(outputs_def) == 2 and isinstance(outputs_def[0], str):
             output_vars.append(extract_param_name(outputs_def))
        elif isinstance(outputs_def, tuple):
             for p in outputs_def:
                 output_vars.append(extract_param_name(p))
        else:
             output_vars.append(str(outputs_def))
             
        if len(output_vars) == 1:
            var_name = output_vars[0]
            ret_val = local_context.get(var_name, None)
        else:
            ret_val = tuple(local_context.get(v, None) for v in output_vars)
            
        return ret_val

# ----------------------------------------------------------------------
# --- 3. Funzione Principale di Parsing ---
# ----------------------------------------------------------------------

def parse_dsl_file(content):
    parser = Lark(grammar, parser='earley')
    tree = parser.parse(content)
    return ConfigTransformer().transform(tree)

def execute_dsl_file(content):
    config = parse_dsl_file(content)
    visitor = DSLVisitor(functions_map=dsl_functions)
    
    # Nota: Usiamo visitor.run() invece di visit() per inizializzare il contesto
    final_result = visitor.run(config)
    return final_result

def run_dsl_tests(visitor: DSLVisitor, parsed_data: dict, functions_map: dict):
    """
    Esegue tutti i casi definiti nella sezione 'test_suite' del DSL.
    """
    test_suite = parsed_data.get('test_suite')
    
    if not test_suite or not isinstance(test_suite, tuple):
        print("🔴 Errore: Sezione 'test_suite' non trovata o non valida nel file DSL.")
        return False

    all_passed = True
    print("\n====================================")
    print(f"Esecuzione {len(test_suite)} Casi di Test DSL")
    print("====================================")

    for test_case in test_suite:
        if not isinstance(test_case, dict):
            print(f"🔴 Errore nel formato del caso test: {test_case}")
            continue

        test_id = test_case.get('id', 'N/A')
        target_name = test_case.get('target')
        input_args = test_case.get('input_args')
        expected = test_case.get('expected_output')

        print(f"\n[Test ID: {test_id}] Testing '{target_name}'...")

        try:
            # 1. Trova la funzione/pipeline target nel contesto globale (root_data)
            target_def = parsed_data.get(target_name)

            if target_def is None:
                print(f"🔴 FALLITO: Target '{target_name}' non trovato nel DSL.")
                all_passed = False
                continue

            # 2. Esecuzione: Le funzioni DSL sono tuple di 3 elementi (Args, Body, Ret)
            if isinstance(target_def, tuple) and len(target_def) == 3:
                # Esegui la funzione DSL
                actual_output = visitor.execute_dsl_function(target_def, input_args)
            
            # 3. Esecuzione: Se è una Pipeline (già pre-valutata come 'EXPRESSION' dal Transformer, ma che deve essere eseguita qui)
            elif isinstance(target_def, tuple) and len(target_def) > 0 and target_def[0] == 'EXPRESSION':
                 # Per testare una pipeline che non è una funzione, dobbiamo iniettare
                 # l'input_args nel primo elemento della pipeline e rieseguire.
                 # Questo è complesso, quindi è meglio definire le pipeline come funzioni DSL
                 # che accettano l'input, come fatto nell'esempio di prima.
                 # Per semplicità, qui assumiamo che solo le funzioni DSL siano testate direttamente.
                 print(f"⚠️ Tipo target non supportato per test diretto: {target_name}. Usare una funzione DSL.")
                 all_passed = False
                 continue
                 
            else:
                 # Se il target non è una funzione DSL, eseguiamo la sua valutazione.
                 # Ad esempio, se target è 'numeri: 100;' e lo vogliamo testare
                 actual_output = visitor.visit(target_def)


            # 4. Confronto
            if actual_output == expected:
                print("🟢 PASSATO!")
            else:
                print("🔴 FALLITO!")
                print(f"   Atteso: {expected}")
                print(f"   Ottenuto: {actual_output}")
                all_passed = False

        except Exception as e:
            print(f"🔴 FALLITO con ECCEZIONE: {e}")
            all_passed = False
            
    print("\n====================================")
    print(f"RISULTATO FINALE: {'🟢 TUTTI I TEST PASSATI' if all_passed else '🔴 TEST FALLITI'}")
    print("====================================")
    return all_passed

# ----------------------------------------------------------------------
# --- 4. Esempio di Utilizzo ---
# ----------------------------------------------------------------------

# --- Funzioni definite nel codice Python ---
def custom_print(data):
    print(f"*** CUSTOM PRINT ***: {data}")
    return data 

def custom_double(data):
    if isinstance(data, (int, float)):
        return data * 2
    return data

# Mappa delle funzioni disponibili per il DSL
dsl_functions = {
    'print': custom_print,
    'raddoppia': custom_double
}