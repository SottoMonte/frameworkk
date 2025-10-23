import os
import sys
import asyncio
import logging
from typing import Dict, Any, List, Optional
from kink import di # Dependancy Injection

# 1. Configurazione del Logging per la Massima Debuggabilità (Principio 1)
# Nomi chiari delle funzioni e messaggi di log descrittivi.
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(name)s.%(funcName)s] - %(message)s'
)
logger = logging.getLogger("BOOTSTRAPPER")

# ----------------------------------------------------------------------
# FUNZIONI FOCALIZZATE SULLA SINGOLA RESPONSABILITÀ (Principio 2)
# ----------------------------------------------------------------------

def parse_browser_cookies(cookie_string: str) -> Dict[str, str]:
    """
    Funzione dichiarativa per il parsing dei cookie.
    Si concentra sul 'cosa' (ottenere key:value) e non sul 'come' (looping).
    
    Gestione Errore: Restituisce un dizionario vuoto in caso di input non valido.
    """
    if not cookie_string:
        return {}

    logger.debug("Parsing dei cookie in ambiente browser...")
    
    # Principio 3: List Comprehension per parsing dichiarativo
    cookies_dict = {}
    try:
        for cookie_pair in cookie_string.split(';'):
            # Garantisce che ci sia un '=', altrimenti salta l'elemento
            if '=' in cookie_pair:
                key, value = cookie_pair.split('=', 1)
                cookies_dict[key.strip()] = value
    except Exception as e:
        logger.error(f"Errore critico durante il parsing dei cookie: {e}")
        # Restituisce il dizionario parziale/vuoto per evitare il blocco
        return cookies_dict
        
    return cookies_dict

def tenta_recupero_sessione(session_value: str) -> Dict[str, Any]:
    """
    Tenta di eseguire la doppia 'eval' sulla stringa di sessione in modo sicuro.
    Gestisce eccezioni specifiche per tracciare il problema (Principio 1).
    """
    session_data: Dict[str, Any] = {}
    if not session_value or session_value == 'None':
        return session_data

    # Commento: La doppia eval è inusuale e potenzialmente non sicura. 
    # Mantenuta per aderenza al codice originale, ma raccomandata una revisione.
    for i in range(2):
        try:
            logger.debug(f"Tentativo di eval() su sessione (Passo {i+1}): {session_value}")
            # L'uso di `eval()` è intrinsecamente non sicuro. 
            # In un contesto reale, si preferirebbe `json.loads`.
            session_value = eval(session_value)
            
            # Se la prima eval non ha convertito in un tipo, si interrompe il loop.
            if not isinstance(session_value, str) and i == 0:
                 break
        except Exception as e:
            logger.warning(f"Errore durante l'eval() della sessione al passo {i+1}. Dettaglio: {e}")
            return {} # Fallimento del recupero della sessione
    
    if isinstance(session_value, dict):
        return session_value
        
    return {} # Non è un dizionario (o la doppia eval è fallita)

async def installa_dipendenze_browser() -> None:
    """Installa le dipendenze Python necessarie in ambiente Pyodide."""
    if sys.platform != "emscripten":
        return

    logger.info("Rilevato ambiente Pyodide. Avvio installazione dipendenze.")
    try:
        # Importiamo solo se necessario per evitare errori in ambienti non-browser
        import micropip 
        
        # 2. Ottimizzazione: Lista dichiarativa e compatta
        packages_to_install = [
            "kink", "tomli", "jinja2", "untangle", "bs4", "lxml", 
            # "webassets" (commentato come nell'originale)
        ]
        
        await micropip.install(packages_to_install)
        logger.info(f"Installazione di {len(packages_to_install)} pacchetti completata.")
        
    except ImportError:
        logger.critical("Dipendenze Pyodide (micropip) non disponibili, ma sys.platform è 'emscripten'.")
        # Rilancia un errore critico per debug immediato
        raise RuntimeError("Impossibile caricare micropip per l'installazione delle dipendenze.")

# ----------------------------------------------------------------------
# FUNZIONE PRINCIPALE DI BOOTSTRAP (Orchestratore)
# ----------------------------------------------------------------------

@language.asynchronous()
async def bootstrap_core() -> None:
    manager_loader_path = [
        {
            'path': 'framework/manager/messenger.py', # Percorso per resource'name': 'UserManager', # Chiave nel DI E nome della classe da estrarre
            'name': 'messenger', # Chiave nel DI E nome della classe da estrarre
            'config': { # Argomenti del costruttore
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['message'], # Dipendenze da risolvere dal DI
            'messenger': 'messenger' # Nome della chiave nel DI per la dipendenza
        },
        {
            'path': 'framework/manager/executor.py', # Percorso per resource'name': 'UserManager', # Chiave nel DI E nome della classe da estrarre
            'name': 'executor', # Chiave nel DI E nome della classe da estrarre
            'config': { # Argomenti del costruttore
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['actuator'], # Dipendenze da risolvere dal DI
            'messenger': 'executor' # Nome della chiave nel DI per la dipendenza
        }
    ]

    await language.load_di_entry(**{
        'path': 'infrastructure/message/console.py', # Percorso per resource
        'service': 'message', # Chiave nel DI per la lista dei provider
        'adapter': 'adapter', # Nome della classe da estrarre dal modulo
        'payload': { # Argomenti del costruttore (__init__)
            'host': 'smtp.corp.com', 
            'port': 587, 
            'secure': True
        }
    })

    # 1. Caricamento sequenziale dei manager essenziali e controllo del risultato
    for mgr in manager_loader_path:
        # Assumiamo che language.load_manager sollevi ResourceLoadError in caso di fallimento
        await language.load_di_entry(**mgr)

@language.asynchronous()
async def bootstrap() -> None:
    """
    Funzione principale di bootstrap che orchestra il caricamento del framework.
    """
    await bootstrap_core()
    
    dependency_executor = di['executor']
    dependency_messenger = di['messenger']
    print(dir(dependency_messenger))
    #print('EXEC-',dependency_messenger)
    await dependency_messenger.post(domain='debug', message="✅ Manager di base (Messenger, Executor) caricati e pronti.")

    await dependency_messenger.post(domain='debug', message="Avvio del processo di inizializzazione del Framework. Controllo ambiente...")
    await dependency_messenger.post(domain='debug', message=f"Sistema: Python {sys.version.split()[0]} su {sys.platform}")
    
    env_config: Dict[str, Any] = dict(os.environ)
    session_data: Dict[str, Any] = {}
    identifier_val: str = 'None'
    
    # Gestione Condizionale della Configurazione Browser/Server (omessa per brevità, è invariata)
    if sys.platform == "emscripten":
        import js # Accesso al DOM
        await installa_dipendenze_browser()
        cookies: Dict[str, str] = parse_browser_cookies(str(js.document.cookie))
        session_str = cookies.get('session', 'None')
        identifier_val = cookies.get('session_identifier', 'None')
        session_data = tenta_recupero_sessione(session_str)
        
        config_params = {**env_config, "session": session_data, "identifier": identifier_val}
        platform_type = "Browser (Pyodide)"
        dependency_messenger.post(domain='debug', message=f"Dipendenze Pyodide/Browser verificate e installate (se necessario).")
    else:
        # Assumiamo che language.get_config sia la funzione corretta
        config_params = env_config | {"session": session_data}
        platform_type = "Server (Standard)"
    await dependency_messenger.post(domain='debug', message=f"Configurazione ambiente preparata per: {platform_type}.")
    # Correzione del nome della funzione (get_confi -> get_config)
    
    text = await language.backend(path="pyproject.toml")
    config = await language.format(text,**config_params)
    await dependency_messenger.post(domain='debug', message=f"Configurazione caricata con successo (Ambiente: {platform_type}).")
    
    # LOGGING MIGLIORATO (Stato DI)
    await dependency_messenger.post(domain='debug', message=f"Container DI 'kink' inizializzato. Tentativo di caricamento manager essenziali...")
    
    # Manager principali (Caricamento Parallelo)

    """'path': 'infrastructure/email/smtp_adapter.py', # Percorso per resource
    'service': 'email_providers', # Chiave nel DI per la lista dei provider
    'adapter': 'EmailAdapter', # Nome della classe da estrarre dal modulo
    'payload': { # Argomenti del costruttore (__init__)
        'host': 'smtp.corp.com', 
        'port': 587, 
        'secure': True
    }"""

    manager_loader_path = [
        {
            'path': 'framework/manager/presenter.py',
            'name': 'presenter',
            'config': {
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['messenger'], # Dipendenze da risolvere dal DI
            'messenger': 'presenter' # Nome della chiave nel DI per la dipendenza
        },
        {
            'path': 'framework/manager/defender.py',
            'name': 'defender',
            'config': {
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['messenger','persistence'], # Dipendenze da risolvere dal DI
            'messenger': 'defender' # Nome della chiave nel DI per la dipendenza
        },
        {
            'path': 'framework/manager/storekeeper.py',
            'name': 'storekeeper',
            'config': {
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['messenger'], # Dipendenze da risolvere dal DI
            'messenger': 'storekeeper' # Nome della chiave nel DI per la dipendenza
        },
        {
            'path': 'framework/manager/tester.py',
            'name': 'tester',
            'config': {
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['messenger','persistence'], # Dipendenze da risolvere dal DI
            'messenger': 'tester' # Nome della chiave nel DI per la dipendenza
        }
    ]
    
    manager_tasks = [ asyncio.create_task(language.load_di_entry(**mgr), name=f"load_{mgr['name']}") for mgr in manager_loader_path]
    
    await dependency_messenger.post(domain='debug', message=f"Avvio del caricamento parallelo di {len(manager_tasks)} Manager...")
    await dependency_executor.all_completed(tasks=manager_tasks) 
    await dependency_messenger.post(domain='debug', message="Caricamento Manager completato. System-DI pronto.")

    '''dependency_storekeeper = di['storekeeper'](di)
    dependency_defender = di['defender'](di)
    dependency_presenter = di['presenter'](di)
    print('STORE-',dependency_storekeeper)
    print('DEFEN-',dependency_defender)
    print('PRESEN-',dependency_presenter)'''

    '''# --- FASE DI CARICAMENTO PROVIDER ---
    provider_tasks: List[asyncio.Task] = []
    MODULI_PRINCIPALI = ["presentation", "persistence", "message", "authentication", "actuator"]
    await dependency_messenger.post(domain='debug', message="Preparazione al caricamento dei Provider d'Infrastruttura...")
    
    for module_name in MODULI_PRINCIPALI:
        if module_name in config and isinstance(config.get(module_name), dict):
            for driver_name, setting_data in config[module_name].items():
                adapter_name = setting_data.get("adapter")
                if not adapter_name:
                    logger.error(f"Configurazione incompleta per '{module_name}/{driver_name}': Manca 'adapter'.")
                    continue
                
                payload_data = {**setting_data, "profile": driver_name, "project": config.get("project", "default")}
                
                task = asyncio.create_task(
                    language.load_provider(language, path=f"infrastructure/{module_name}/{adapter_name}.py", area="infrastructure", service=module_name, adapter=adapter_name, payload=payload_data),
                    name=f"load_provider_{module_name}_{driver_name}"
                )
                provider_tasks.append(task)
                logger.debug(f"Task creata: Provider {module_name} / Adattatore {adapter_name} ('{driver_name}').")
        else:
            logger.debug(f"Modulo '{module_name}' non configurato o non è un dizionario. Saltato.")

    logger.info(f"Avvio del caricamento parallelo di {len(provider_tasks)} Provider...")
    await dependency_executor.all_completed(tasks=provider_tasks)
    logger.info("Caricamento di tutti i Provider completato.")

    # --- FASE DI AVVIO DEGLI ELEMENTI DI PRESENTAZIONE ---
    # Uso l'interfaccia DI a dizionario, assumendo sia stata configurata
    presentation_elements: List[Any] = di["presentation"] 
    event_loop = asyncio.get_event_loop()
    logger.info(f"Avvio dei caricatori ({len(presentation_elements)}) per gli elementi di Presentazione.")

    for item in presentation_elements:
        item_name = getattr(item, '__class__', item)
        if hasattr(item, "loader"):
            try:
                item.loader(loop=event_loop)
                logger.debug(f"Loader eseguito con successo per {item_name}.")
            except Exception as e:
                logger.error(f"ERRORE GRAVE: Il 'loader' dell'elemento {item_name} ha fallito. Dettaglio: {e}")
        else:
            logger.debug(f"L'elemento {item_name} non ha un metodo 'loader'. Saltato.")

    logger.info("Framework avviato con successo. Sistema pronto e operativo.")'''