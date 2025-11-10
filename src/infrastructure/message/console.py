import sys
import logging
import time
imports = {}
from framework.service.language import get_transaction_id
# Controllo se il codice sta girando in Pyodide

if sys.platform == 'emscripten':
    from js import console
    from pyodide.ffi import to_js
    async def log_backend(self,level, message):
            """Logging in Pyodide tramite console JavaScript."""
            js_message = to_js(f"{level.upper()}: {message}")
            match level:
                case 'debug': console.log(js_message)
                case 'info': console.info(js_message)
                case 'warning': console.warn(js_message)
                case 'error': console.error(js_message)
                case 'critical': console.error(js_message)
                case _: console.log(js_message)
else:
    
    async def log_backend2(self,level, message):
        
        """Logging in ambiente Python nativo."""

        match level:
            case 'debug': self.logger.debug(message)
            case 'info': self.logger.info(message)
            case 'warning': self.logger.warning(message)
            case 'error': self.logger.error(message)
            case 'critical': self.logger.critical(message)
            case _: self.logger.info(message)
    async def log_backend(self, level, message, stack_level=1):
        """Logging in ambiente Python nativo."""

        # Il tuo 'adapter.post' chiama 'log_backend'. Il chiamante di 'adapter.post' è quello che ci interessa.
        # stacklevel=2 salta (1) log_backend e (2) adapter.post, raggiungendo la funzione utente.
        final_stack_level = stack_level + 1 # Passa stack_level=1 da post, aggiungi 1 qui.

        # Otteniamo il transaction id dal context (se presente) e lo passiamo come 'extra'
        try:
            tx = get_transaction_id()
        except Exception:
            tx = None

        extra = {'transaction_id': tx if tx else "-"}

        match level:
            case 'debug': self.logger.debug(message, stacklevel=final_stack_level, extra=extra)
            case 'info': self.logger.info(message, stacklevel=final_stack_level, extra=extra)
            case 'warning': self.logger.warning(message, stacklevel=final_stack_level, extra=extra)
            case 'error': self.logger.error(message, stacklevel=final_stack_level, extra=extra)
            case 'critical': self.logger.critical(message, stacklevel=final_stack_level, extra=extra)
            case _: self.logger.info(message, stacklevel=final_stack_level, extra=extra)

class adapter:
    
    ANSI_COLORS = {
        'DEBUG': "\033[96m",    # Ciano chiaro
        'INFO': "\033[92m",     # Verde
        'WARNING': "\033[93m",  # Giallo
        'ERROR': "\033[91m",    # Rosso
        'CRITICAL': "\033[95m"  # Magenta
    }
    RESET_COLOR = "\033[0m"  # Reset colori ANSI

    def __init__(self, **constants):
        
        #self.config = constants['config']
        self.history = dict()
        self.start_time = time.time()
        # Creazione del logger
        self.logger = logging.getLogger("self.config['project']['identifier']")
        self.logger.propagate = False 
        self.logger.setLevel(logging.DEBUG)
        self.processable = ['log']
        
        # Handler per la console
        ch = logging.StreamHandler()
        if constants['config']['project'].get('mode') == 'production':
            ch.setLevel(logging.INFO)  # In produzione, solo INFO e superiori (esclude DEBUG)
        else:
            ch.setLevel(logging.DEBUG)

        # 2. Modifica il Formatter per includere il campo 'domain' e transaction_id
        formatter = self.ColoredFormatter(
            constants.get('format', "%(asctime)s.%(msecs)03d | [T+%(delta_ms)s]ms | [ΔT%(delta_inter_ms)s]ms | %(levelname)-16s | %(filename)s:%(lineno)d | %(funcName)-25s | %(process)d | [tx:%(transaction_id)s] | %(message)s"),
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        ch.setFormatter(formatter)
        self.logger.addFilter(self._TimerFilter(self.start_time)) 
        self.logger.addHandler(ch)

    '''class _TimerFilter(logging.Filter):
        """Calcola e aggiunge il tempo trascorso (delta) dall'avvio del sistema."""
        def __init__(self, start_time):
            super().__init__()
            self.start_time = start_time

        def filter(self, record):
            # Calcola il delta time in secondi
            delta_seconds = record.created - self.start_time
            # Lo formatta in millisecondi con 3 decimali (es. 000000123.456)
            record.delta_ms = f"{delta_seconds * 1000:012.3f}"
            return True'''
    
    class _TimerFilter(logging.Filter):
        """Aggiunge il Delta Time Assoluto (T+) e il Delta Inter-Messaggio (T^)."""
        def __init__(self, start_time):
            super().__init__()
            self.start_time = start_time
            self.last_record_time = None # <--- Variabile per tracciare il tempo precedente

        def filter(self, record):
            
            # --- 1. Delta Assoluto (T+) ---
            delta_seconds_abs = record.created - self.start_time
            record.delta_ms = f"{delta_seconds_abs * 1000:012.3f}" 
            
            # --- 2. Delta Inter-Messaggio (T^) ---
            if self.last_record_time is None:
                # Primo record: il delta è zero o lo stesso del delta assoluto
                record.delta_inter_ms = f"{0.0:09.3f}"
            else:
                # Calcola il tempo trascorso dall'ultimo record
                delta_inter_seconds = record.created - self.last_record_time
                record.delta_inter_ms = f"{delta_inter_seconds * 1000:09.3f}" # Formato: 000.000
                
            # Aggiorna il tempo dell'ultimo record per la prossima iterazione
            self.last_record_time = record.created 
            
            return True

    class ColoredFormatter(logging.Formatter):
        """Classe per aggiungere colori ANSI ai livelli di log in console."""

        def format(self, record):
            color = adapter.ANSI_COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname}{adapter.RESET_COLOR}"

            # Se il record ha già 'transaction_id' (passato via extra) lo rispettiamo,
            # altrimenti proviamo a recuperarlo dal contextvar; fallback a '-'.
            existing_tx = getattr(record, 'transaction_id', None)
            if existing_tx not in (None, ""):
                record.transaction_id = existing_tx
            else:
                try:
                    tx = get_transaction_id()
                except Exception:
                    tx = None
                record.transaction_id = tx if tx else "-"

            return super().format(record)

    async def can(self, *services, **constants):
        return constants['name'] in self.processable

    async def post(self, *services, **constants):
        """Registra un messaggio di log con il colore corrispondente al livello."""
        domain = constants.get('domain', 'info')
        message = constants.get('message', '')
        # Non pre-iniettiamo più [tx:...] direttamente nel testo (lo fa il formatter tramite extra)
        try:
            tx = get_transaction_id()
        except Exception:
            tx = None

        stored_message = message  # mantiene il messaggio pulito in history
        # se vuoi salvare anche l'ID in history, puoi farlo come metadato separato
        self.history.setdefault(domain,[0,[]])[1].append(stored_message)

        # Passiamo il message al backend; log_backend recupera il transaction id e lo passa come extra
        await log_backend(self, domain, stored_message, stack_level=4)

    async def read(self, *services, **constants):
        domain = constants.get('domain', 'info')
        identity = constants.get('identity', '')
        results = []
        matching_domains = language.wildcard_match(self.history.keys(), domain)
        #print(f"Matching domains2: {matching_domains}",self.history.keys(),domain,self.history)
        for dom in matching_domains:
            last, messages = self.history.get(dom, [0, []])
            if last < len(messages):
                self.history[dom][0] += 1
                results.append({'domain': dom, 'message': messages[last:]})
                #results.extend(messages[last:])
        return results

        '''if domain in self.history:
            last,messages = self.history.get(domain,[0,[]])
            #last = last.get(identity,0)
            if last < len(messages):
                self.history[domain][0] += 1
                #self.history.get(domain,[{},[]])[0].get(identity) = len(messages)
                return messages[last:]'''
        return []