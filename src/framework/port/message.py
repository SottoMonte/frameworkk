# internal external dove viaggiano i dati

from abc import ABC, abstractmethod

class port(ABC):

    @abstractmethod
    def loader(self,*services,**constants):
        pass

    @abstractmethod
    async def post(self,*services,**constants):
        pass

    @abstractmethod
    async def get(self,*services,**constants):
        pass

    @abstractmethod
    async def can(self,*services,**constants):
        pass