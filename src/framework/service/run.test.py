import framework.service.contract as contract

imports = {
    'contract': 'framework/service/contract.py',
}

exports = {
    'application': 'application'
}

class TestModule(contract.Contract):
    async def test_application(self):
        """Test dummy per permettere l'export di 'application'"""
        pass