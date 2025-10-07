import asyncio

imports = {
    'factory': 'framework/service/factory.py',
    'flow': 'framework/service/flow.py',
    'contract': 'framework/service/contract.py',
    'model': 'framework/schema/model.json',
}

class TestModule():

    def setUp(self):
        
        print("Setting up the test environment...")

    async def test_application(self):
        """Verifica che language.get recuperi correttamente i valori da percorsi validi."""
        success = [
            {'args':(language),'kwargs':{'path':"framework/service/run.py"},'type':types.ModuleType},
            {'args':(language),'kwargs':{'path':"framework/schema/model.json"},'equal':model},
        ]

        failure = [
            {'args':(language),'kwargs':{'path':"framework/service/NotFound.py"}, 'error': FileNotFoundError},
        ]

        await self.check_cases(language.resource, success)
        await self.check_cases(language.resource, failure)