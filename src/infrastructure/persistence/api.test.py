from framework.port.persistence import port
from framework.service.test import test
from infrastructure.persistence.api import adapter


class AdapterTest(test):
    adapter = adapter
    port = port
    config = {'adapter': "api", 'url': "https://api.github.com", 'token': ""}

    async def test_query(self, *services, **constants):
        """
        Esegue una query generica verso l'API GitHub.
        """
        self.assertEqual('1', '1')

    async def test_create(self, *services, **constants):
        """
        Metodo per creare risorse.
        """
        payload = {
            "message": "Creating new file",
            "content": "main"  # Content should be base64-encoded
        }
        data = await self.test.create(repo='colosso-cloud/test',content='main',file_path="create.xml")
        gg = await self.test.create(repo='colosso-cloud/test',content='main',file_path="wr.xml")
        self.assertEqual(data.get('state',False), True)
    
    async def test_update(self, *services, **constants):
        """
        Metodo per scrivere risorse.
        """
        data = await self.test.update(repo='colosso-cloud/test',content='testt messaggio',file_path="wr.xml")
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

    async def test_view(self):
        """
        Ottieni l'albero di una repository.
        """
        data = await self.test.view('SottoMonte/framework','main')
        self.assertEqual(data.get('state',False), True)