from abc import ABC, abstractmethod

class port(ABC):
    @abstractmethod
    async def create(self,*services,**constants):
        pass

    @abstractmethod
    def read(self,*services,**constants):
        pass

    @abstractmethod
    async def update(self,*services,**constants):
        pass

    @abstractmethod
    async def delete(self,*services,**constants):
        pass

    @abstractmethod
    async def query(self,*services,**constants):
        pass

    @abstractmethod
    async def view(self,*services,**constants):
        pass