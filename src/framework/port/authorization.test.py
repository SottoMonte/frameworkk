imports = {
    'contract': 'framework/service/contract.py',
    #'model': 'framework/schema/model.json',
}

exports = {
    'port': 'port',
}

class Testport(contract.Contract):

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

        #self.adapter = starlette.adapter(config=test_config)
        #self.adapter = starlette.adapter

    def tearDown(self):
        """
        Questo metodo viene eseguito dopo ogni test.
        Serve per pulire l'ambiente di test.
        """
        # Qui puoi aggiungere codice per pulire l'ambiente di test, se necessario
        pass

    async def test_authorized(self):
        """
        Verifica se l'identità data è autorizzata a eseguire l'azione 
        sulla risorsa specificata.
        """
        pass

    async def test_allowed(self):
        """
        Interroga per ottenere l'elenco delle azioni consentite 
        per l'identità sulla risorsa.
        """
        pass