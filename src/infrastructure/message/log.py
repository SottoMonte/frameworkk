import logging

modules = {'flow': 'framework.service.flow'}

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

        match domain:
            case 'debug': self.logger.debug(message)
            case 'info': self.logger.info(message)
            case 'warning': self.logger.warning(message)
            case 'error': self.logger.error(message)
            case 'critical': self.logger.critical(message)
            case _: self.logger.info(message)

    async def read(self, *services, **constants):
        pass