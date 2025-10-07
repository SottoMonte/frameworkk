import sys
import logging
modules = {'flow': 'framework.service.flow'}
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
    
    async def log_backend(self,level, message):
        """Logging in ambiente Python nativo."""
        match level:
            case 'debug': self.logger.debug(message)
            case 'info': self.logger.info(message)
            case 'warning': self.logger.warning(message)
            case 'error': self.logger.error(message)
            case 'critical': self.logger.critical(message)
            case _: self.logger.info(message)

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
        self.config = constants['config']
        self.history = dict()
        # Creazione del logger
        self.logger = logging.getLogger(self.config['project']['identifier'])
        self.logger.setLevel(logging.DEBUG)
        self.processable = ['log']
        
        # Handler per la console
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # Formatter con formattazione avanzata e colori ANSI
        formatter = self.ColoredFormatter(
            constants.get('format', "%(asctime)s | %(levelname)-8s | %(process)d | %(message)s"),
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    class ColoredFormatter(logging.Formatter):
        """Classe per aggiungere colori ANSI ai livelli di log in console."""

        def format(self, record):
            color = adapter.ANSI_COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname}{adapter.RESET_COLOR}"
            record.msg = f"{record.msg}"
            return super().format(record)

    async def can(self, *services, **constants):
        return constants['name'] in self.processable

    async def post(self, *services, **constants):
        """Registra un messaggio di log con il colore corrispondente al livello."""
        domain = constants.get('domain', 'info')
        message = constants.get('message', '')
        #print(f"POSTING {domain} {message}")
        #if domain not in self.history:
        #self.history.setdefault(domain,[0,[]])[1].append(message)
        self.history.setdefault(domain,[0,[]])[1].append(message)

        
        #self.history.get(domain)[1].append()
        
        await log_backend(self,domain,message)

    async def read(self, *services, **constants):
        domain = constants.get('domain', 'info')
        identity = constants.get('identity', '')
        results = []
        matching_domains = language.wildcard_match(self.history.keys(), domain)
        print(f"Matching domains2: {matching_domains}",self.history.keys(),domain,self.history)
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