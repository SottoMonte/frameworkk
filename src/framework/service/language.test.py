imports = {
    'contract': 'framework/service/contract.py',
    #'language': 'framework/service/language.py',
    #'model': 'framework/schema/model.json',
}

exports = {
    #Pubblico/privato
    'fetch':'resource',
    'asynchronous':'asynchronous',
    'synchronous':'synchronous',
    'register':'load_di_entry',
    'format':'format',
    'transform':'transform',
    'generate':'generate',
    'convert':'convert',
    'route':'route',
    'normalize':'normalize',
    'put':'put',
    'get':'get'
}

class TestModule(contract.Contract):

    def setUp(self):
        self.data = {
            "nome": "Progetto A",
            "versioni": [
                {"id": 1, "status": "completo"},
                {"id": 2, "status": "in_corso", "dettagli": {"tester": "Mario"}},
                {"id": 3, "status": "fallito"}
            ],
            "config": {
                "timeout": 30,
                "log_livello": "DEBUG"
            }
        }
        import framework.service.language as language
        self.language = language
        
        print("Setting up the test environment...")


    async def test_transform(self):
        pass

    async def test_resource(self):
        """Verifica che language.get recuperi correttamente i valori da percorsi validi."""
        '''success = [
            {'args':(language),'kwargs':{'path':"framework/service/run.py"},'type':types.ModuleType},
            {'args':(language),'kwargs':{'path':"framework/schema/model.json"},'equal':model},
        ]

        failure = [
            {'args':(language),'kwargs':{'path':"framework/service/NotFound.py"}, 'error': FileNotFoundError},
        ]

        await self.check_cases(language.resource, success)
        await self.check_cases(language.resource, failure)'''
    
    async def test_route(self):
        pass

    async def test_put(self):
        pass

    async def test_get(self):
        # Casi di successo (Output atteso != Valore di default)
        success = [
            # 1. Accesso Base
            {'args': (self.data, "nome"), 'equal': "Progetto A"},
            
            # 2. Accesso Nidificato
            {'args': (self.data, "config.timeout"), 'equal': 30},
            
            # 3. Accesso a Lista tramite Indice (primo elemento)
            {'args': (self.data, "versioni.0.status"), 'equal': "completo"},
            
            # 4. Accesso Complesso (indice e nidificazione)
            {'args': (self.data, "versioni.1.dettagli.tester"), 'equal': "Mario"},
            
            # 5. Uso del Carattere Jolly '*' (estrazione di un campo)
            {'args': (self.data, "versioni.*.status"), 'equal': ["completo", "in_corso", "fallito"]},
            
            # 6. Uso del Carattere Jolly '*' (estrazione di un altro campo)
            {'args': (self.data, "versioni.*.id"), 'equal': [1, 2, 3]},
        ]

        # Casi di fallimento (Output atteso == Valore di default)
        # Questi test verificano che venga restituito il valore di default
        failure = [
            # 7. Chiave non esistente (default è None)
            {'args': (self.data, "chiave.sconosciuta"), 'equal': None},
            
            # 8. Chiave non esistente (default specificato)
            {'args': (self.data, "config.porta", 80), 'equal': 80},
            
            # 9. Indice fuori limite (default specificato)
            {'args': (self.data, "versioni.99", "N/A"), 'equal': "N/A"},
            
            # 10. Tentativo di accesso a chiave in lista (senza indice o *)
            # La funzione dovrebbe restituire il default perché 'nome' è una stringa non traversabile
            {'args': (self.data, "nome.sub_chiave"), 'equal': None},
        ]

        await self.check_cases(self.language.get, success + failure)

    async def test_asynchronous(self):
        pass

    async def test_synchronous(self):
        pass
    
    async def test_load_di_entry(self):
        pass

    async def test_format(self):
        pass

    async def test_generate(self):
        pass

    async def test_convert(self):
        pass

    async def test_normalize(self):
        pass

    '''async def test_model(self):
        success = [
            #1 Recupera il modello
            {'args':(self.schema,{'user': {'name':'marco','items': [{'id': 123, 'name': 'Prodotto A'}]}}),'equal':{'user': {'name':'marco','items': [{'id': 123, 'name': 'Prodotto A'}]}}},
        ]

        failure = [
            #1 Campo mancante
            {'args':(self.schema,{'user': {'ok':'m','name':'marco','items': [{'id': 123, 'name': 'Prodotto A'}]}}),'error': ValueError},
        ]

        await self.check_cases(language.model, success)
        await self.check_cases(language.model, failure)

    async def test_put(self):
        # Definisci il tuo schema Cerberus
        

        # --- CASI DI SUCCESSO ---
        # Gli args devono essere un tuple che contiene TUTTI gli argomenti per `put`
        success_cases = [
            #1 Inserimento iniziale, crea 'user' come dict
            {'args': ({}, 'user.name', 'Alice', self.schema), 'equal': {'user': {'name': 'Alice'}}},
            #2 Crea 'address' come dict
            {'args': ({'user': {'name': 'Alice'}}, 'user.address.street', 'Via Roma', self.schema), 'equal': {'user': {'name': 'Alice', 'address': {'street': 'Via Roma'}}}},
            #3 Crea 'items' come lista e il primo elemento come dict
            {'args': ({'user': {'name': 'Alice'}}, 'user.items.0.id', 123, self.schema), 'equal': {'user': {'name': 'Alice', 'items': [{'id': 123}]}}},
            #4 Aggiunge nome al primo elemento della lista
            {'args': ({'user': {'items': [{'id': 123}]}}, 'user.items.0.name', 'Prodotto A', self.schema), 'equal': {'user': {'items': [{'id': 123, 'name': 'Prodotto A'}]}}},
            #5 Aggiorna un valore esistente
            {'args': ({'user': {'name': 'Bob'}}, 'user.name', 'Charlie', self.schema), 'equal': {'user': {'name': 'Charlie'}}},
        ]

        # --- CASI DI FALLIMENTO ---
        failure_cases = [
            #1 Campo non definito nello schema
            {'args': ({}, 'user.invalid_field', 'Value', self.schema), 'error': IndexError},
            #2 Tipo di nodo intermedio sbagliato (tentativo di usare indice su dict quando lo schema attende stringa)
            {'args': ({}, 'user.0.name', 'Alice', self.schema), 'error': IndexError},
            #3 Tipo non corrispondente allo schema (stringa per int)
            {'args': ({'user': {}}, 'user.age', '30', self.schema), 'error': ValueError},
            #4 Regex non corrispondente
            {'args': ({'user': {'address':{}}}, 'user.address.zip', 'ABCDE', self.schema), 'error': ValueError},
            #5 Tentativo di accedere con chiave stringa a una lista (se lo schema attende una lista, ma viene data una stringa)
            {'args': ({'user': {'items':[]}}, 'user.items.my_item.id', 1, self.schema), 'error': IndexError},
            #6 Indice di lista negativo
            #{'args': ({'user': {'items':[]}}, 'user.items.-1.id', 1, my_schema), 'error': IndexError},
            #7 Dominio vuoto
            {'args': ({}, '', 'value', self.schema), 'error': ValueError},
        ]

        await self.check_cases(language.put, success_cases) # Passa la funzione put (non language.put)
        await self.check_cases(language.put, failure_cases) # Passa la funzione put

    async def test_extract_params(self):
        success = [
            {'args':("func(name: 'Alice', age: 30, city: 'New York')"),'equal':{'name': 'Alice', 'age': 30, 'city': 'New York'}},
            {'args':("process(id: 123, options: {'mode': 'fast', 'verbose': True})"),'equal':{'id': 123, 'options': {'mode': 'fast', 'verbose': True}}},
            {'args':("analyze(data: [1, 2, 3, {'x': 10}], threshold: 0.5)"),'equal':{'data': [1, 2, 3, {'x': 10}], 'threshold': 0.5}},
            {'args':("send(message: \"Hello, world!\", priority: 5)"),'equal':{'message': "Hello, world!", 'priority': 5}},
            {'args':("empty_func()"),'equal':{}}, # Funzione senza parametri
            {'args':("some_action(status: None, debug: False)"),'equal':{'status': None, 'debug': False}},
            {'args':("another_func(data: [1, 'two', 3], complex: {'a': [1,2], 'b': 'nested'})"),'equal':{'data': [1, 'two', 3], 'complex': {'a': [1, 2], 'b': 'nested'}}},
        ]

        failure_cases = [
            # Caso 1: Stringa JSON/Python malformata (es. virgole, apici mancanti)
            {'args':("bad_syntax(param: {'key': value)"), 'error': SyntaxError}, # Assumi che un parsing fallito dia SyntaxError o ValueError
            {'args':("incomplete(param: 'value'"), 'error': SyntaxError}, # Mancanza di chiusura parentesi
            {'args':("simple(name: Bob)"), 'error': ValueError}, # Valore non quotato che non è un tipo Python valido (int, float, bool, None)

            # Caso 2: Nomi di parametri invalidi
            # {'args':("invalid(0name: 'value')"), 'error': ValueError}, # Se la tua funzione convalida i nomi
            
            # Caso 3: Input non previsto per la funzione (es. non una stringa)
            {'args': (123,), 'error': TypeError}, # Se 'extract_params' si aspetta una stringa come input
            {'args': ({'a':1},), 'error': TypeError},
        ]

        failure = [
            {'args':("problematic(key: 'value with , comma', another: {nested_key: 'value, inside'})"),'equal':{'key': 'value with , comma', 'another': {'nested_key': 'value, inside'}}},
            {'args':("simple(name: Bob)"),'equal':{}}, # Chiave non quotata e valore non quotato non stringa   
        ]

        await self.check_cases(language.extract_params, success)
        await self.check_cases(language.extract_params, failure)

    async def test_get(self):
        """Verifica che language.get recuperi correttamente i valori da percorsi validi."""
        success = [
            {'args':({'name': 'test_name'}, 'name'),'equal':'test_name'},
            {'args':({'url': {'path': '/api'}}, 'url.path', ),'equal':'/api'},
            {'args':({'url': {'path': '/api', 'query': {'id': 123}}}, 'url.query.id'),'equal':123},
            {'args':({'data': [1, 2, 3]}, 'data.1'),'equal':2},
            {'args':({'data': [{'item': 'value'}]}, 'data.0.item'),'equal':'value'},
            {'args':({'nested': {'key': 'value'}}, 'nested.key'),'equal':'value'},
            {'args':({'list': [1, 2, 3]}, 'list.2'),'equal':3},
            {'args':({'mixed': {'a': 1, 'b': [10, 20]}}, 'mixed.b.1'),'equal':20},
            {'args':({'complex': {'a': {'b': 1}}}, 'complex.a.b'),'equal':1},
            {'args':({'empty_dict': {}}, 'empty_dict.non_existent', 'default_value'),'equal':'default_value'}, # Chiave inesistente con default
            {'args':({}, 'none_value', 'fallback'),'equal':'fallback'}, # Accesso a None con default
            {'args':({'list_data': [10, 20]}, 'list_data.0'),'equal':10}, # Accesso a lista con indice
            {'args':({'list_data': [{'item': 'val'}]}, 'list_data.0.item'),'equal':'val'}, # Accesso a lista di dizionari
            {'args':({}, 'a'),'equal':None}, # Verifica None esplicito come valore
            {'args':(['ciao'], '0'),'equal':'ciao'}, # Accesso a lista con indice

        ]

        failure = [
            {'args':(123,'id'), 'error': TypeError}, # Accesso a un intero, dovrebbe fallire
        ]

        await self.check_cases(language.get, success)
        await self.check_cases(language.get, failure)

    async def test_translation(self):
        """Verifica la mappatura base dei nomi dei campi senza trasformazioni."""
        api = {'version': {'type': 'float'}, 'active': {'type': 'boolean'},'users': {'type': 'dict', 'schema': {'name': {'type': 'string'}, 'age': {'type': 'integer'}}}}

        mapper = {
            'config.version': {'API': 'version','GITHUB': 'v'},
            'config.active': {'API': 'active','GITHUB': 'active'},
            'user.name': {'API': 'users.name','GITHUB': 'name'},
            'user.age': {'API': 'users.age','GITHUB': 'age'}
        }
        
        values = {} # Nessuna trasformazione dei valori

        success_cases = [
            {'args': ({'version':1.1,'active':True}, mapper, values, api, self.schema), 'equal': {'config': {'version': 1.1,'active': True}}},
            {'args': ({'config': {'version': 1.1,'active': True}}, mapper, values, self.schema, api), 'equal': {'version':1.1,'active':True}},
            {'args': ({'users': {'name': 'marco','age': 18}}, mapper, values, api, self.schema), 'equal': {'user': {'name': 'marco','age': 18}}},
            {'args': ({'user': {'name': 'marco','age': 18}}, mapper, values, self.schema, api), 'equal': {'users': {'name': 'marco','age': 18}}},
            #{'args': ({'version':1.1,'active':True}, self.schema, mapper, values, 'MODEL', 'API'), 'equal': {'config': {'version': 1.1,'active': True}}}
        ]

        failure = [
            #1 Errori di tipo nei parametri
            {'args': ("{'version':1.1,'active':True,'sss':'a'}", mapper, values, api, self.schema), 'error': TypeError},
            # 2 Mapper non è un dizionario
            {'args': ({'version':1.1,'active':True}, [], values, api, self.schema), 'error': TypeError},
            # 3 Valori non sono un dizionario
            {'args': ({'version':1.1,'active':True,'sss':'a'}, mapper, (1,2,3), api, self.schema), 'error': TypeError},
            # 4 Input non è un dizionario
            {'args': ({'version':1.1,'active':True}, mapper, values, 'not_a_dict', self.schema), 'error': TypeError},
            # 5 Output non è un dizionario
            {'args': ({'version':1.1,'active':True}, mapper, values, self.schema, 'not_a_dict'), 'error': TypeError},
            # 6 Mapper non è un dizionario
            {'args': ({'version':1.1,'active':True}, mapper, values, self.schema), 'error': TypeError},
            # 7 Valori non sono un dizionario
            {'args': (), 'error': TypeError},
            #{'args': ({'config': {'version': 1.1,'active': True}}, mapper, values, self.schema, api), 'error': ValueError},
            #{'args': ({'version':1.1,'active':True}, self.schema, mapper, values, 'MODEL', 'API'), 'equal': {'config': {'version': 1.1,'active': True}}}
        ]

        await self.check_cases(language.translation, success_cases)
        await self.check_cases(language.translation, failure)

    async def test_get_config(self):
        """Verifica che language.get recuperi correttamente i valori da percorsi validi."""
        success = [
            {'args':({'name': 'test_name'}, 'name'),'equal':'test_name'},
            {'args':({'url': {'path': '/api'}}, 'url.path', ),'equal':'/api'},
            {'args':({'url': {'path': '/api', 'query': {'id': 123}}}, 'url.query.id'),'equal':123},
            {'args':({'data': [1, 2, 3]}, 'data.1'),'equal':2},
            {'args':({'data': [{'item': 'value'}]}, 'data.0.item'),'equal':'value'},
            {'args':({'nested': {'key': 'value'}}, 'nested.key'),'equal':'value'},
            {'args':({'list': [1, 2, 3]}, 'list.2'),'equal':3},
            {'args':({'mixed': {'a': 1, 'b': [10, 20]}}, 'mixed.b.1'),'equal':20},
            {'args':({'complex': {'a': {'b': 1}}}, 'complex.a.b'),'equal':1},
            {'args':({'empty_dict': {}}, 'empty_dict.non_existent', 'default_value'),'equal':'default_value'}, # Chiave inesistente con default
            {'args':({}, 'none_value', 'fallback'),'equal':'fallback'}, # Accesso a None con default
            {'args':({'list_data': [10, 20]}, 'list_data.0'),'equal':10}, # Accesso a lista con indice
            {'args':({'list_data': [{'item': 'val'}]}, 'list_data.0.item'),'equal':'val'}, # Accesso a lista di dizionari
            {'args':({}, 'a'),'equal':None}, # Verifica None esplicito come valore
            {'args':(['ciao'], '0'),'equal':'ciao'}, # Accesso a lista con indice

        ]

        failure = [
            {'args':(123,'id'), 'error': TypeError}, # Accesso a un intero, dovrebbe fallire
        ]

        await self.check_cases(language.get, success)
        await self.check_cases(language.get, failure)'''