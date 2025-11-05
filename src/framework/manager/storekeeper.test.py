imports = {
    'contract': 'framework/service/contract.py',
}

exports = {
    'presenter': 'presenter',
}

import asyncio
class Testpresenter(contract.Contract):

    def setUp(self):
        '''asyncio.run(language.load_di_entry(**{
            'path': 'framework/manager/messenger.py', # Percorso per resource'name': 'UserManager', # Chiave nel DI E nome della classe da estrarre
            'name': 'messenger', # Chiave nel DI E nome della classe da estrarre
            'config': { # Argomenti del costruttore
                'cache_enabled': True, 
                'log_level': 'INFO'
            },
            'dependency_keys': ['message'], # Dipendenze da risolvere dal DI
            'messenger': 'messenger' # Nome della chiave nel DI per la dipendenza
        }))'''
        print("Setting up the test environment...")

    async def test_selector(self):
        '''"""Verifica che language.get recuperi correttamente i valori da percorsi validi."""
        success = [
            {'args':(language),'kwargs':{'path':"framework/service/run.py"},'type':types.ModuleType},
            {'args':(language),'kwargs':{'path':"framework/schema/model.json"},'equal':model},
        ]

        failure = [
            {'args':(language),'kwargs':{'path':"framework/service/NotFound.py"}, 'error': FileNotFoundError},
        ]

        await self.check_cases(language.resource, success)
        await self.check_cases(language.resource, failure)'''
        pass