imports = {
    'contract': 'framework/service/contract.py',
}

exports = {
    'repository': 'repository',
}

class TestModule(contract.Contract):
    async def test_repository(self):
        pass