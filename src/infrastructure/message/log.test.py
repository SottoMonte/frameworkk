import unittest

import framework.port.persistence as persistence
import framework.service.flow as flow
import framework.service.language as language
from infrastructure.presentation.starlette import adapter

from unittest import IsolatedAsyncioTestCase

class AdapterTest(IsolatedAsyncioTestCase):
    def __init__(self, *args,**kwargs):
        super(AdapterTest, self).__init__(*args, **kwargs)  # Chiamata al costruttore di unittest.TestCase
        #config = {}
        #self.test = adapter(config=config)  # Inizializza il tuo adapter qui

    async def test_builder(self, *services, **constants):
        """
        Esegue una query generica verso l'API GitHub.
        """
        self.assertEqual('1', '1')