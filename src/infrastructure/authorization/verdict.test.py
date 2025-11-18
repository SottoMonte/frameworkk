imports = {
    'verdict': 'infrastructure/authorization/verdict.py',
    'contract': 'framework/service/contract.py',
}

exports = {
    'adapter': 'adapter',
}

class Testadapter(contract.Contract):

    async def test_check(self):
        import infrastructure.authorization.verdict as verdict
        engine = verdict.adapter(config={})

        request = {
            "principal": {
                "id": "user-101",
                "roles": ["premium"]
            },
            "resource": {
                "id": "doc-456",
                "status": "PUBLISHED",
                "owner_id": "user-202"
            }
        }

        print(engine.check("document_access", request))
        pass

    async def test_load_policy(self):
        pass

    async def test_load_data_store(self):
        pass

    async def test_load_policies(self):
        pass