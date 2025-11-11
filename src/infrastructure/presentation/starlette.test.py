imports = {
    'starlette': 'infrastructure/presentation/starlette.py',
    'contract': 'framework/service/contract.py',
    #'port': 'framework/port/presentation.test.py',

    #'model': 'framework/schema/model.json',
}

exports = {
    'adapter': 'adapter',
}

class Testadapter(contract.Contract):

    def setUp(self):
        """
        Questo metodo viene eseguito prima di ogni test.
        Serve per inizializzare l'ambiente di test.
        """
        test_config = {
            #'route': 'test_route',
            'host': '127.0.0.1',
            'port': 8000
        }

        self.adapter = starlette.adapter(config=test_config)
        #self.adapter = starlette.adapter

    def tearDown(self):
        """
        Questo metodo viene eseguito dopo ogni test.
        Serve per pulire l'ambiente di test.
        """
        # Qui puoi aggiungere codice per pulire l'ambiente di test, se necessario
        pass

    async def test_builder(self):
        pass

    async def test_code(self):
        pass

    async def test_att(self):
        pass

    async def test_code_update(self):
        pass

    async def test_rebuild(self):
        pass

    async def test_render_view(self):
        pass

    async def test_render_css(self):
        pass

    async def test_render_widget(self):
        pass

    async def test_mount_route(self):
        pass 
    
    async def test_starlette_view(self):
        pass 
       
    async def test_login(self):
        pass 

    async def test_logout(self):
        pass 

    async def test_action(self):
        pass 

    async def test_loader(self):
        pass

    async def test_mount_view(self):
        pass

    async def test_mount_widget(self):
        
        success = [
            # 1. Recupera un modello di base
            {'args': ('video', [], {}), 'equal': '<video/>'},

            # 2. Widget con attributi
            {'args': ('image', [], {'src': 'image.jpg', 'alt': 'My Image'}), 'equal': '<img src="image.jpg" alt="My Image"/>'}, # Nota: <img> è self-closing, ma il test potrebbe aspettarsi la chiusura esplicita

            # 3. Widget con contenuto di testo
            {'args': ('text', ['Hello World!'], {}), 'equal': '<p class="text">Hello World!</p>'},

            # 4. Widget con attributi e contenuto di testo
            {'args': ('text', ['Page Title'], {'class': 'title'}), 'equal': '<p class="title">Page Title</p>'},

            # 5. Widget con attributi booleani (ad es. 'controls' per <video>)
            {'args': ('video', [], {'controls': True, 'autoplay': False}),'equal': '<video controls="True" autoplay="False"/>'}, # Assumendo che `autoplay: False` rimuova l'attributo

            # 6. Widget con attributi numerici (dovrebbero essere convertiti in stringhe)
            {'args': ('container', [], {'data-id': 123, 'data-value': 45.67}), 'equal': '<div class="container-fluid" data-id="123" data-value="45.67"/>'},

            # 7. Widget con attributi con valori None (dovrebbero essere rimossi)
            {'args': ('action', [], {'type': 'submit', 'disabled': None}), 'equal': '<button class="btn" type="submit"/>'},

            # 8. Widget con contenuto HTML interno (come gestito da mount_widget?)
            {'args': ('container', ['<span>Inner HTML</span>'], {}), 'equal': '<div class="container-fluid"><span>Inner HTML</span></div>'},

            # 9. Test con tag HTML in maiuscolo (se il parser lo gestisce)
            {'args': ('TEXT', [], {'id': 'container'}),'equal': '<p class="text" id="container"></p>'}, # Dipende se il tuo parser preserva il case

            # 10. Test con più attributi e contenuto misto
            {'args': ('action', ['Click Me'], {'href': '#', 'type': 'link'}), 'equal': '<a class="btn btn-link" href="#">Click Me</a>'},
        ]

        failure = [
            # 1. Nome widget non valido (es. None o non stringa)
            {'args': (None, [], {}), 'error': ValueError}, # O il tipo di errore che ti aspetti
            {'args': (123, [], {}), 'error': TypeError},

            # 2. Attributi non validi (es. non dizionario)
            {'args': ('div', 'not_a_dict', {}), 'error': TypeError},

            # 3. Contenuto non valido (es. non stringa per _text)
            {'args': ('p', [], {'_text': 123}), 'error': TypeError},
        ]
        await self.check_cases(self.adapter.mount_widget, success)
        #await self.check_cases(self.adapter.mount_widget, failure)

    async def test_set_attribute(self):
        
        success = [
            # 1. Aggiunta di un nuovo attributo a un tag senza attributi esistenti
            {'args': ('<video></video>', 'width', '100px'), 'equal': '<video width="100px"></video>'},
            
            # 2. Modifica di un attributo esistente con valore
            {'args': ('<video width="100px"></video>', 'width', '200px'), 'equal': '<video width="200px"></video>'},
            
            # 3. Modifica di un attributo esistente con un valore diverso per un tag con altri attributi
            #{'args': ('<video width="100px" height="50px"></video>', 'height', '100px'), 'equal': '<video width="100px" height="100px"></video>'},
            
            # 4. Aggiunta di un nuovo attributo a un tag con attributi esistenti
            #{'args': ('<video autoplay></video>', 'width', '300px'), 'equal': '<video autoplay width="300px"></video>'},
            
            # 5. Impostazione di un attributo booleano (impostando il valore a None, che dovrebbe rimuoverlo o renderlo booleano)
            {'args': ('<video autoplay="true"></video>', 'autoplay', None), 'equal': '<video></video>'},
            
            # 6. Impostazione di un attributo booleano esistente a un valore (lo trasforma in un attributo con valore)
            {'args': ('<video controls></video>', 'controls', 'false'), 'equal': '<video controls="false"></video>'},

            # 7. Impostazione di un attributo con un valore che contiene spazi o caratteri speciali
            {'args': ('<div class="old"></div>', 'class', 'new-class with spaces'), 'equal': '<div class="new-class with spaces"></div>'},
            {'args': ('<img data-info="old" />', 'data-info', '{"key": "value"}'), 'equal': '<img data-info=\'{"key": "value"}\'/>'},
            
            # 8. Gestione della capitalizzazione del tag HTML
            #{'args': ('<VIDEO></VIDEO>', 'width', '400px'), 'equal': '<VIDEO width="400px"></VIDEO>'},
            
            # 9. Gestione della capitalizzazione dell'attributo esistente
            {'args': ('<video WIDTH="100px"></video>', 'width', '500px'), 'equal': '<video width="500px"></video>'},

            # 10. Impostazione di un attributo a un tag che è auto-chiudente
            {'args': ('<img />', 'alt', 'descrizione'), 'equal': '<img alt="descrizione"/>'},
            {'args': ('<input type="text" />', 'value', 'test'), 'equal': '<input type="text" value="test"/>'},

            # 11. Impostazione dell'attributo `class` (gestito separatamente in alcuni parser, ma qui testiamo l'impostazione generica)
            {'args': ('<div class="initial"></div>', 'class', 'updated-class'), 'equal': '<div class="updated-class"></div>'},
        ]

        failure = [
            # 1. HTML malformato (manca il ">" finale del tag)
            # Ci si aspetta che la funzione non modifichi l'HTML o sollevi un errore,
            # o che restituisca una stringa vuota/None a seconda della tua implementazione.
            # Qui ci aspettiamo che non avvenga la modifica, quindi l'output è uguale all'input.
            #{'args': ('<video width="100px"', 'height', '50px'), 'equal': None},
            
            # 2. Input del widget non valido (es. None o non una stringa)
            # Ci aspettiamo che sollevi un errore o restituisca l'input originale o None.
            # Se la tua funzione solleva TypeError, dovrai usare pytest.raises.
            {'args': (None, 'width', '100px'), 'equal': None}, # Se restituisce None per input non stringa
            {'args': ('', 'width', '100px'), 'equal': ''}, # Se l'input è una stringa vuota, l'output è lo stesso

            # 3. Nome dell'attributo non valido (es. None, stringa vuota, o con spazi)
            {'args': ('<video></video>', None, '10px'), 'equal': '<video></video>'}, # Nome attributo None
            {'args': ('<video></video>', '', '10px'), 'equal': '<video></video>'}, # Nome attributo vuoto
            {'args': ('<video></video>', 'data-my attribute', 'value'), 'equal': '<video></video>'}, # Nome attributo con spazio

            # 4. Input del valore non valido (se la tua funzione lo gestisce, altrimenti potrebbe convertirlo in stringa)
            {'args': ('<video></video>', 'data-num', 123), 'equal': '<video data-num="123"></video>'}, # Se converte il numero in stringa
            # Se invece ti aspetti che un numero o un None come valore sollevino un errore o non modifichino, adattalo.
        ]

        await self.check_cases(self.adapter.set_attribute, success)
        await self.check_cases(self.adapter.set_attribute, failure)

    async def test_get_attribute(self):
        success = [
            # 1. Recupero dell'attributo base
            {'args':('<video width="100px" ></video>','width'),'equal': '100px'},
            # 2. Recupero dell'attributo non presente
            {'args':('<video width="100px" ></video>','height'),'equal': None},
            # 3. Recupero dell'attributo con percorso/URL
            {'args':('<video src="/home.mp4" />','src'),'equal': '/home.mp4'},
            # 4. Recupero dell'attributo da un widget senza attributi espliciti (attributo non presente)
            {'args':('<video  ></video>','width'),'equal': None},
            # 5. Recupero dell'attributo da un widget con attributi multipli
            {'args':('<video width="100px" height="200px" ></video>','height'),'equal': '200px'},
            # 6. Recupero di un attributo booleano (senza valore esplicito)
            {'args':('<video width="100px" height="200px" autoplay ></video>','autoplay'),'equal': None},
            # 7. Attributo con valore vuoto
            {'args':('<input value="" />', 'value'), 'equal': ''},
            # 8. Attributo con spazi bianchi nel valore
            {'args':('<div data-info="  "></div>', 'data-info'), 'equal': '  '},
            # 9. Attributo con case-insensitive (nome attributo maiuscolo)
            {'args':('<img ALT="Descrizione Immagine" />', 'alt'), 'equal': 'Descrizione Immagine'},
            # 10. Attributo con case-insensitive (nome attributo misto)
            {'args':('<a HrEf="link.html">Link</a>', 'href'), 'equal': 'link.html'},
            # 11. Valori di attributi con caratteri speciali (JSON, URL encoded)
            {'args':('<div data-json=\'{"id":1, "name":"test"}\'></div>', 'data-json'), 'equal': '{"id":1, "name":"test"}'},
            {'args':('<a href="?param1=value1&amp;param2=value2">Link</a>', 'href'), 'equal': '?param1=value1&amp;param2=value2'},
            # 12. Attributo presente ma non il primo
            {'args':('<div id="first" class="second"></div>', 'class'), 'equal': 'second'},
            # 13. Attributo con un numero come valore
            {'args':('<circle r="50"></circle>', 'r'), 'equal': '50'},
        ]

        # Considera di dividere i test di fallimento in test specifici che verificano le eccezioni, se applicabile.
        failure = [
            # 1. HTML malformato: chiusura tag mancante
            {'args':('<div width="100px"', 'width'), 'equal': None}, # O solleva un'eccezione
            # 2. Input stringa vuota
            {'args':('', 'any_attribute'), 'equal': None}, # O solleva un'eccezione
            # 3. HTML valido ma attributo non stringa
            {'args':('<div class="test"></div>', None), 'equal': None}, 
            # 4. HTML valido ma attributo non stringa
            {'args':('<div class="test"></div>', 123), 'equal': None}, 
            # 5. Attributo con nome malformato (dipende dal parser)
            # Se la tua implementazione gestisce nomi di attributi non standard come questi,
            # altrimenti il test dovrebbe aspettarsi None.
            {'args':('<div data-my attribute="value"></div>', 'data-my attribute'), 'equal': None},
        ]

        await self.check_cases(self.adapter.get_attribute, success)
        await self.check_cases(self.adapter.get_attribute, failure)