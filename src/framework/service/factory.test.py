import asyncio

imports = {
    'factory': 'framework/service/factory.py',
    'contract': 'framework/service/contract.py',
}

exports = {
    'repository':'repository'
}

class Testrepository(contract.Contract):
    def setUp(self):
        '''self.repo = factory.repository(
            location={
                "dev": [
                    "repos/{payload.location}/contents/{payload.path}",
                    "repos/{payload.location}/contents/{payload.path}/{payload.name}",
                ]
            },
            mapper={},
            values={},
            payloads={},
            model=model
        )
        print("Setting up the test environment...",self.repo,__file__)'''
        pass

    # === do_format ===
    '''def test_do_format(self):
        template = "repos/{payload.location}/contents/{payload.path}"
        data = {
            "payload": {
                "location": "user/repo",
                "path": "src"
            }
        }
        
        formatted = self.repo.do_format(template, data)
        self.assertEqual(formatted, "repos/user/repo/contents/src")'''

    # === parameters (async) ===
    async def test_find_first_formattable_template(self):
        pass

    async def test_can_format(self):
        pass

    async def test_do_format(self):
        pass

    async def test_parameters(self):
        
        '''payloads = {}
        self.repo.payloads = payloads
        inputs = {
            "payload": {
                "location": "user/repo",
                "path": "src"
            }
        }
        result = await self.repo.parameters("crud_op", "dev", **inputs)
        self.assertEqual(result["location"], "repos/user/repo/contents/src")
        self.assertEqual(result["provider"], "dev")
        self.assertEqual(result["payload"], {"location": "user/repo", "path": "src"})'''
        pass

    # === results (async) ===
    async def test_results(self):
        '''self.repo.fields = ['location']
        transaction = {
            "result": [{"location": "loc1"}, {"location": "loc2"}]
        }
        data = {"transaction": transaction, "profile": "dev"}
        #self.repo.language = MockLanguage
        result = await self.repo.results(**data)
        self.assertEqual(len(result["result"]), 2)
        self.assertEqual(result["result"][0]["location"], "loc1")'''
        pass

