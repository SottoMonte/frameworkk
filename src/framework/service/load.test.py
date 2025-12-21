import asyncio

imports = {
    #'factory': 'framework/service/factory.py',
    'contract': 'framework/service/contract.py',
    #'model': 'framework/schema/model.json',
}

exports = {
    'bootstrap':'bootstrap',
    'bootstrap_core':'bootstrap_core',
    'generate_checksum': 'generate_checksum',
    'resource': 'resource',
}

class TestModule(contract.Contract):

    def setUp(self):
        print("Setting up the test environment...")

    async def test_generate_checksum(self):
        pass

    async def test_resource(self):
        pass

    async def test_bootstrap_core(self):
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

    async def test_bootstrap(self):
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