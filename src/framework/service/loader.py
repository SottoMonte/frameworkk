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

async def bootstrap() -> None:
    """
    Funzione principale di bootstrap che orchestra il caricamento del framework.
    Contiene un Catch-All finale per garantire la tracciabilità di ogni crash.
    """
    
    # 🎯 PUNTO CHIAVE: L'unico try...except avvolge l'intera logica.
    try:
        logger.info("Avvio del processo di inizializzazione del Framework. Controllo ambiente...")
        
        # LOGGING MIGLIORATO (Informazioni sull'Ambiente)
        logger.info(f"Sistema: Python {sys.version.split()[0]} su {sys.platform}")
        
        env_config: Dict[str, Any] = dict(os.environ)
        session_data: Dict[str, Any] = {}
        identifier_val: str = 'None'
        
        await installa_dipendenze_browser()
        logger.info("Dipendenze Pyodide/Browser verificate e installate (se necessario).")
        
        # Gestione Condizionale della Configurazione Browser/Server (omessa per brevità, è invariata)
        if sys.platform == "emscripten":
            import js # Accesso al DOM
            
            cookies: Dict[str, str] = parse_browser_cookies(str(js.document.cookie))
            session_str = cookies.get('session', 'None')
            identifier_val = cookies.get('session_identifier', 'None')
            session_data = tenta_recupero_sessione(session_str)
            
            config_params = {**env_config, "session": session_data, "identifier": identifier_val}
            platform_type = "Browser (Pyodide)"
        else:
            # Assumiamo che language.get_config sia la funzione corretta
            config_params = env_config | {"session": session_data}
            platform_type = "Server (Standard)"
            
        # Correzione del nome della funzione (get_confi -> get_config)
        
        print(dir(language))  # Debug: Verifica le funzioni disponibili in language
        config = language.get_config(**config_params) 
        logger.info(f"Configurazione caricata con successo (Ambiente: {platform_type}).")
        
        # LOGGING MIGLIORATO (Stato DI)
        logger.info(f"Container DI 'kink' inizializzato. Tentativo di caricamento manager essenziali...")
        
        # --- FASE DI CARICAMENTO MANAGER ESSENZIALI ---
        # 🎯 GESTIONE ERRORI MIGLIORATA
        manager_loader_path = [
            {"provider": "message", "name": "messenger", "path": "framework/manager/messenger.py"},
            {"provider": "actuator", "name": "executor", "path": "framework/manager/executor.py"},
        ]

        # 1. Caricamento sequenziale dei manager essenziali e controllo del risultato
        essential_managers_ready = True
        for mgr in manager_loader_path:
            try:
                # Assumiamo che language.load_manager sollevi ResourceLoadError in caso di fallimento
                await language.load_manager(language, **mgr)
                logger.info(f"✅ Manager {mgr['name']} caricato.")
            except Exception as e:
                logger.error(f"❌ Fallimento Caricamento Manager Essenziale '{mgr['name']}' ({mgr['path']}). Causa: {type(e).__name__}. L'applicazione non è stabile.", exc_info=False)
                essential_managers_ready = False
        
        if not essential_managers_ready:
            # Se un manager essenziale fallisce, solleviamo un errore che verrà catturato dal catch-all
            raise RuntimeError("Impossibile avviare il Framework: Manager essenziali mancanti o falliti.")
            
        logger.info("Manager di base (Messenger, Executor) caricati e pronti.")
        
        # 🎯 GESTIONE ERRORE FATALE: AttributeError sul Container DI
        dependency_executor: Optional[ExecutorManager] = None

        # 2. Controllo esplicito e uso del metodo DI raccomandato da KINK (.get_instance)
        if hasattr(di, "get_instance"):
            try:
                # Metodo preferito per kink: get_instance (più esplicito per la risoluzione)
                dependency_executor = di.get_instance(ExecutorManager)
            except Exception as e:
                 # Questo cattura la possibile KeyError se l'ExecutorManager non è stato registrato
                logger.critical(f"Manager 'ExecutorManager' non trovato o risoluzione DI fallita. Dettaglio: {e}")
                raise LookupError("Il manager 'executor' non è stato registrato nel Container DI.") from e
        elif hasattr(di, "get"):
            # Metodo .get() che era implicito nel log originale (anche se fallito)
            dependency_executor = di.get("executor")
        elif isinstance(di, dict) and "executor" in di:
            # Fallback all'interfaccia a dizionario
            dependency_executor = di["executor"]
        else:
            # Causa del tuo AttributeError: l'oggetto di non ha il metodo .get() o .get_instance()
            logger.critical(f"Il Container DI ({type(di).__name__}) non supporta i metodi 'get_instance' o 'get'.")
            raise AttributeError("Interfaccia del Container DI non valida. Verificare l'inizializzazione di 'kink'.")
            
        if not dependency_executor:
            raise LookupError("Il manager 'executor' non è stato trovato nel DI. Verificare l'iniezione.")
        
        # Da qui in poi, `dependency_executor` è garantito essere valido.
        
        # Manager principali (Caricamento Parallelo)
        manager_tasks: List[asyncio.Task] = [
            asyncio.create_task(language.load_manager(language, provider="presentation", name="presenter", path="framework/manager/presenter.py"), name="load_presenter"),
            asyncio.create_task(language.load_manager(language, provider="authentication", name="defender", path="framework/manager/defender.py"), name="load_defender"),
            asyncio.create_task(language.load_manager(language, provider="persistence", name="storekeeper", path="framework/manager/storekeeper.py"), name="load_storekeeper"),
            asyncio.create_task(language.load_manager(language, provider="authentication", name="tester", path="framework/manager/tester.py"), name="load_tester"),
        ]
        
        logger.info(f"Avvio del caricamento parallelo di {len(manager_tasks)} Manager...")
        await dependency_executor.all_completed(tasks=manager_tasks) 
        logger.info("Caricamento Manager completato. System-DI pronto.")

        # ... (il resto della logica rimane identico) ...

        # --- FASE DI CARICAMENTO PROVIDER ---
        provider_tasks: List[asyncio.Task] = []
        MODULI_PRINCIPALI = ["presentation", "persistence", "message", "authentication", "actuator"]
        logger.info("Preparazione al caricamento dei Provider d'Infrastruttura...")
        
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

        logger.info("Framework avviato con successo. Sistema pronto e operativo.")

    # 🛑 CATTURA TUTTI GLI ERRORI (Catch-All Universale)
    except Exception as e:
        # Questo blocco cattura tutti i fallimenti inaspettati
        
        # Aggiungo un messaggio più chiaro sulla causa finale.
        final_message = f"Inizializzazione fallita. Errore: {type(e).__name__}."
        if isinstance(e, AttributeError):
            final_message += " (Possibile errore nell'interfaccia del Container DI: metodo 'get' mancante)."
        elif isinstance(e, LookupError):
             final_message += " (Manager/Dipendenza non registrata nel Container DI)."
        
        logger.critical(
            f"ERRORE FATALE e INASPETTATO durante il bootstrap! Causa: {type(e).__name__}. L'applicazione non può avviarsi. ",
            exc_info=True, # Logga il traceback completo
            stack_info=True 
        )
        
        # Rilancia per bloccare l'applicazione
        raise ImportError(final_message) from e