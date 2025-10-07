
import os
import aiofiles
import sys

# File System (FS)
if sys.platform == 'emscripten':
    import pyodide
else:
    import framework.service.flow as flow

class adapter():

    def __init__(self,**constants):
        self.config = constants['config']
        if sys.platform == 'emscripten':
            self.fs = pyodide.mountNativeFS("/mnt")

    async def query(self,**constants):
        pass

    #@flow.asynchronous(ports=('storekeeper',))
    async def read(self,storekeeper,**constants):
        try:
            async with aiofiles.open(constants['file'], mode="r") as file:
                content = await file.read()
                return storekeeper.builder('transaction',{'state': True,'action':'read','result':dict({'file':content})})
        except FileNotFoundError:
            return storekeeper.builder('transaction',{'state': False,'action':'read'})

    #@flow.asynchronous(ports=('storekeeper',))
    async def create(self,**constants):
        pass

    #@flow.asynchronous(ports=('storekeeper',))
    async def delete(self,**constants):
        pass

    #@flow.asynchronous(ports=('storekeeper',))
    async def update(self,**constants):
        try:
            async with aiofiles.open(constants['file'], mode="r") as file:
                content = await file.read()
                return content
        except FileNotFoundError:
            return "File non trovato."

    async def view(self,**constants):
        # restituisci 
        albero = []
        for elemento in os.listdir(constants['path']):
            percorso_completo = os.path.join(constants['path'], elemento)
            if os.path.isdir(percorso_completo):
                # Ricorsione per le sottodirectory
                #print(percorso_completo)
                # print(percorso_completo)
                fs_tree = await self.tree(path=percorso_completo)
                albero.append(('dir',percorso_completo,elemento,fs_tree))
            else:
                albero.append(('file',percorso_completo,elemento))
        return tuple(albero)