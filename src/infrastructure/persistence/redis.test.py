imports = {
    'redis': 'infrastructure/persistence/redis.py',
    'contract': 'framework/service/contract.py',
}

exports = {
    'adapter': 'adapter',
}

class Testadapter(contract.Contract):

    async def test_read(self):
        pass

    async def test_create(self):
        pass

    async def test_delete(self):
        pass

    async def test_write(self):
        pass