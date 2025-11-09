from unittest import IsolatedAsyncioTestCase

exports = {
    'asynchronous':'asynchronous',
    'synchronous':'synchronous',
}

class TestModule(IsolatedAsyncioTestCase):

    async def test_asynchronous(self):
        pass

    async def test_synchronous(self):
        pass