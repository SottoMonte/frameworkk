imports = {
    'console': 'infrastructure/message/console.py',
    'contract': 'framework/service/contract.py',
}

exports = {
    'adapter': 'adapter',
}

import unittest

class Testadapter(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        
        print("Setting up the test environment...")

    async def test_post(self):
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
        print("Running test_post...")
        assert True, "Not implemented yet."