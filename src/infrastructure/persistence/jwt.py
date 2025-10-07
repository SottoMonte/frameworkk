import sys

modules = {'flow': 'framework.service.flow','persistence': 'framework.port.persistence'}

if sys.platform == 'emscripten':
    import pyodide
    import json
else:
    import aiohttp
    import time
    import jwt
    import json
    import base64

class adapter(persistence.port):
    
    def __init__(self, **constants):
        """
        Inizializza l'adapter JWT con i parametri specificati.
        
        :param api_url: URL dell'API da utilizzare
        :param app_id: ID dell'applicazione
        :param key: Percorso del file della chiave privata
        :param installation_id: ID dell'installazione (facoltativo, necessario per GitHub o applicazioni simili)
        """
        self.config = constants['config']
        self.api_url = self.config['url']
        self.app_id = self.config['app_id']
        self.installation_id = self.config['installation_id']
        # Leggi la chiave privata dal file
        with open(self.config['key'], "r") as f:
            self.private_key = f.read()

        self.token_expiry = int(time.time()) + (10 * 60)  # Scadenza di 10 minuti per il token
        self.token = self.generate_jwt()
    
    def generate_jwt(self):
        """
        Genera un JWT per autenticazione con un servizio.
        """
        payload = {
            "iat": int(time.time()),  # Tempo corrente
            "exp": self.token_expiry,  # Scadenza (10 minuti)
            "iss": self.app_id,  # ID dell'app
        }
        
        return jwt.encode(payload, self.private_key, algorithm="RS256")
    
    def is_token_expired(self):
        """
        Verifica se il token è scaduto.
        """
        return int(time.time()) > self.token_expiry

    async def refresh_token(self):
        """
        Rigenera il JWT se è scaduto.
        """
        if self.is_token_expired():
            self.token = self.generate_jwt()
            self.token_expiry = int(time.time()) + (10 * 60)  # Reset della scadenza
        return self.token

    async def get_access_token(self):
        """
        Ottieni un token di accesso per l'installazione della GitHub App.
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.api_url}/app/installations/{self.installation_id}/access_tokens"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            }
            async with session.post(url, headers=headers) as response:
                if response.status == 201:
                    data = await response.json()
                    return data["token"]
                else:
                    raise Exception(f"Failed to get access token: {response.status}")
    
    async def query(self, **constants):
        """
        Effettua una richiesta API generica.
        
        :param method: Metodo HTTP (GET, POST, PUT, DELETE)
        :param url: Percorso della risorsa API
        :param payload: Dati da inviare (opzionale)
        :return: Risultato della richiesta
        """
        url = constants.get('url','')
        payload = constants.get('payload','')
        method = constants.get('method','')
        await self.refresh_token()  # Verifica e rinnova il token se necessario
        self.access_token = await self.get_access_token()
        '''async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    file_data = await response.json()
                    # Decode the content (base64)
                    content = 
                    return {"state": True, "content": content}
                else:
                    return {"state": False, "remark": f"Failed to read file: {response.status}"}'''
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }

            async with session.request(method=method, url=url, headers=headers, json=payload) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    match method:
                        case 'GET':
                            # Decode the content (base64)
                            content = base64.b64decode(data['content']).decode('utf-8')
                            return {"state": True, "content": data}
                        case _:
                            return {"state": True, "content": data}
                else:
                    return {"state": False, "remark": f"Request failed with status {response.status}"}

    async def create(self, *services, **constants):
        """
        Metodo per creare risorse (ad esempio, un nuovo file in un repository).
        """
        
        if 'repo' not in constants or 'file_path' not in constants or 'content' not in constants:
            return {"state": False, "remark": "Repository, file_path, and content are required to create a resource."}
        
        url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
        payload = {
            "message": "Creating new file",
            "content": base64.b64encode(constants['content'].encode()).decode()  # Content should be base64-encoded
        }
        a = await self.query(method="PUT",url=url,payload=payload)
        return a

    async def delete(self, *services, **constants):
        """
        Metodo per cancellare risorse (ad esempio, un file in un repository).
        """
        if 'repo' not in constants or 'file_path' not in constants:
            return {"state": False, "remark": "Repository and file_path are required to delete a resource."}

        file = await self.read(**constants)
        sha = file['content']["sha"]
        # Now delete the file
        url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
        payload = {
            "message": "Deleting file",
            "sha": sha
        }
        return await self.query(method="DELETE",url=url,payload=payload)

    async def read(self, *services, **constants):
        """
        Metodo per leggere risorse (ad esempio, leggere un file in un repository).
        """
        if 'repo' not in constants or 'file_path' not in constants:
            return {"state": False, "remark": "Repository and file_path are required to read a resource."}

        url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
        return await self.query(method="GET",url=url,payload={})  

    async def update(self, *services, **constants):
        """
        Metodo per scrivere risorse (ad esempio, aggiornare un file in un repository).
        """

        if 'repo' not in constants or 'file_path' not in constants or 'content' not in constants:
            return {"state": False, "remark": "Repository, file_path, and content are required to write a resource."}

        file = await self.read(**constants)
        sha = file['content']["sha"]

        # Update the file
        url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
        payload = {
            "message": "Updating file",
            "content": base64.b64encode(constants['content'].encode()).decode(),
            "sha": sha
        }
        return await self.query(method="PUT",url=url,payload=payload)
            

    async def view(self, repo, branch):
        """
        Ottieni l'albero di una repository specifica.
        """
        self.access_token = await self.get_access_token()
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }

            # Ottieni lo SHA del branch
            branch_url = f"{self.api_url}/repos/{repo}/branches/{branch}"
            async with session.get(branch_url, headers=headers) as branch_response:
                if branch_response.status != 200:
                    return {"state": False, "remark": "Failed to get branch details"}
                
                branch_data = await branch_response.json()
                tree_sha = branch_data["commit"]["commit"]["tree"]["sha"]

            # Ottieni la struttura dell'albero
            tree_url = f"{self.api_url}/repos/{repo}/git/trees/{tree_sha}?recursive=1"
            async with session.get(tree_url, headers=headers) as tree_response:
                if tree_response.status != 200:
                    return {"state": False, "remark": "Failed to get repository tree"}
                
                tree_data = await tree_response.json()
                return {"state": True, "tree": self.build_tree_dict(tree_data["tree"])}

    def build_tree_dict(self, tree):
        """
        Converte una lista di oggetti GitHub in una struttura ad albero.
        """
        tree_dict = {}
        for item in tree:
            path_parts = item["path"].split("/")
            current = tree_dict
            for part in path_parts[:-1]:
                current = current.setdefault(part, {})
            current[path_parts[-1]] = {"type": item["type"], "sha": item["sha"]}
        return tree_dict

class adaptertest(persistence.port):
    
    def __init__(self, **constants):
        self.config = constants['config']
        self.ssl = bool(self.config.get('ssl', True))
        self.api_url = self.config['url']
        self.app_id = self.config['app_id']
        f = open(self.config['key'], "r")
        self.private_key = f.read()
        self.installation_id = self.config['installation_id']
        self.token = self.generate_jwt()

    def generate_jwt(self):
        """
        Genera un JSON Web Token (JWT) per autenticare come GitHub App.
        """
        payload = {
            "iat": int(time.time()),  # Tempo corrente
            "exp": int(time.time()) + (10 * 60),  # Scadenza (10 minuti)
            "iss": self.app_id,  # ID della GitHub App
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_access_token(self):
        """
        Ottieni un token di accesso per l'installazione della GitHub App.
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.api_url}/app/installations/{self.installation_id}/access_tokens"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            }
            async with session.post(url, headers=headers) as response:
                if response.status == 201:
                    data = await response.json()
                    return data["token"]
                else:
                    raise Exception(f"Failed to get access token: {response.status}")

    async def query(self, *services, **constants):
        """
        Esegue una query generica verso l'API GitHub.
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }
            url = f"{self.api_url}/{constants['path']}"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"state": False, "remark": f"Query failed with status {response.status}"}

    async def create(self, *services, **constants):
        """
        Metodo per creare risorse (ad esempio, un nuovo file in un repository).
        """
        self.access_token = await self.get_access_token()
        if 'repo' not in constants or 'file_path' not in constants or 'content' not in constants:
            return {"state": False, "remark": "Repository, file_path, and content are required to create a resource."}

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }
            url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
            payload = {
                "message": "Creating new file",
                "content": base64.b64encode(constants['content'].encode()).decode()  # Content should be base64-encoded
            }
            async with session.put(url, headers=headers, json=payload) as response:
                if response.status == 201:
                    return {"state": True, "data": await response.json()}
                else:
                    return {"state": False, "remark": f"Failed to create file: {response.status}"}

    async def delete(self, *services, **constants):
        """
        Metodo per cancellare risorse (ad esempio, un file in un repository).
        """
        self.access_token = await self.get_access_token()
        if 'repo' not in constants or 'file_path' not in constants:
            return {"state": False, "remark": "Repository and file_path are required to delete a resource."}

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }
            # Get the current file information (to retrieve SHA for deletion)
            url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return {"state": False, "remark": f"File not found: {response.status}"}

                file_data = await response.json()
                sha = file_data["sha"]

            # Now delete the file
            delete_url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
            delete_payload = {
                "message": "Deleting file",
                "sha": sha
            }
            async with session.delete(delete_url, headers=headers, json=delete_payload) as delete_response:
                if delete_response.status == 200:
                    return {"state": True, "remark": "File deleted successfully."}
                else:
                    return {"state": False, "remark": f"Failed to delete file: {delete_response.status}"}

    async def read(self, *services, **constants):
        """
        Metodo per leggere risorse (ad esempio, leggere un file in un repository).
        """
        self.access_token = await self.get_access_token()
        if 'repo' not in constants or 'file_path' not in constants:
            return {"state": False, "remark": "Repository and file_path are required to read a resource."}

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }
            url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    file_data = await response.json()
                    # Decode the content (base64)
                    content = base64.b64decode(file_data['content']).decode('utf-8')
                    return {"state": True, "content": content}
                else:
                    return {"state": False, "remark": f"Failed to read file: {response.status}"}

    async def write(self, *services, **constants):
        """
        Metodo per scrivere risorse (ad esempio, aggiornare un file in un repository).
        """
        self.access_token = await self.get_access_token()
        if 'repo' not in constants or 'file_path' not in constants or 'content' not in constants:
            return {"state": False, "remark": "Repository, file_path, and content are required to write a resource."}

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }
            # Get the current file information (to retrieve SHA for writing)
            url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    file_data = await response.json()
                    sha = file_data["sha"]
                else:
                    sha = None  # If file doesn't exist, it's a new file

            # Update the file
            write_url = f"{self.api_url}/repos/{constants['repo']}/contents/{constants['file_path']}"
            payload = {
                "message": "Updating file",
                "content": base64.b64encode(constants['content'].encode()).decode(),
                "sha": sha
            }
            async with session.put(write_url, headers=headers, json=payload) as write_response:
                if write_response.status == 200:
                    return {"state": True, "data": await write_response.json()}
                else:
                    return {"state": False, "remark": f"Failed to write file: {write_response.status}"}

    async def tree(self, repo, branch):
        """
        Ottieni l'albero di una repository specifica.
        """
        self.access_token = await self.get_access_token()
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github+json",
            }

            # Ottieni lo SHA del branch
            branch_url = f"{self.api_url}/repos/{repo}/branches/{branch}"
            async with session.get(branch_url, headers=headers) as branch_response:
                if branch_response.status != 200:
                    return {"state": False, "remark": "Failed to get branch details"}
                
                branch_data = await branch_response.json()
                tree_sha = branch_data["commit"]["commit"]["tree"]["sha"]

            # Ottieni la struttura dell'albero
            tree_url = f"{self.api_url}/repos/{repo}/git/trees/{tree_sha}?recursive=1"
            async with session.get(tree_url, headers=headers) as tree_response:
                if tree_response.status != 200:
                    return {"state": False, "remark": "Failed to get repository tree"}
                
                tree_data = await tree_response.json()
                return {"state": True, "tree": self.build_tree_dict(tree_data["tree"])}

    def build_tree_dict(self, tree):
        """
        Converte una lista di oggetti GitHub in una struttura ad albero.
        """
        tree_dict = {}
        for item in tree:
            path_parts = item["path"].split("/")
            current = tree_dict
            for part in path_parts[:-1]:
                current = current.setdefault(part, {})
            current[path_parts[-1]] = {"type": item["type"], "sha": item["sha"]}
        return tree_dict