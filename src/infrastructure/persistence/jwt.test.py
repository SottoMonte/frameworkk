import unittest

import json
import framework.port.persistence as persistence
import framework.service.flow as flow
import framework.service.language as language
from infrastructure.persistence.jwt import adapter

from unittest import IsolatedAsyncioTestCase

class AdapterTest(IsolatedAsyncioTestCase):
    def __init__(self, *args,**kwargs):
        super(AdapterTest, self).__init__(*args, **kwargs)  # Chiamata al costruttore di unittest.TestCase
        try:
            config = {'adapter':"jwt",'url':"https://api.github.com",'app_id': "1057329",'installation_id':"57923539",'key':"public/colosso-cloud.2024-11-24.private-key.pem",'autologin':"true"}
            self.test = adapter(config=config)  # Inizializza il tuo adapter qui
        except Exception as e:
            print(e)

    async def test_query(self, *services, **constants):
        """
        Esegue una query generica verso l'API GitHub.
        """
        self.assertEqual('1', '1')

    async def test_create(self, *services, **constants):
        """
        Metodo per creare risorse.
        """
        data = await self.test.create(repo='colosso-cloud/test',content='main',file_path="create.xml")
        gg = await self.test.create(repo='colosso-cloud/test',content='main',file_path="wr.xml")
        self.assertEqual(data.get('state',False), True)
    
    async def test_write(self, *services, **constants):
        """
        Metodo per scrivere risorse.
        """
        data = await self.test.write(repo='colosso-cloud/test',content='testt messaggio',file_path="wr.xml")
        self.assertEqual(data.get('state',False), True)

    async def test_read(self, *services, **constants):
        """
        Metodo per leggere risorse.
        """
        data = await self.test.read(repo='colosso-cloud/test',file_path="wr.xml")
        self.assertEqual(data.get('state',False), True)

    async def test_delete(self, *services, **constants):
        """
        Metodo per cancellare risorse.
        """
        data = await self.test.delete(repo='colosso-cloud/test',file_path="create.xml")
        self.assertEqual(data.get('state',False), True)

    async def test_tree(self):
        """
        Ottieni l'albero di una repository.
        """
        data = await self.test.tree('SottoMonte/framework','main')
        self.assertEqual(data.get('state',False), True)
