from abc import ABC, abstractmethod

class port(ABC):

    @abstractmethod
    def loader(self,*services,**constants):
        pass

    @abstractmethod
    async def activate(self,*services,**constants):
        pass

    @abstractmethod
    async def deactivate(self,*services,**constants):
        pass

    @abstractmethod
    async def calibrate(self,*services,**constants):
        pass

    @abstractmethod
    async def status(self,*services,**constants):
        pass

    @abstractmethod
    async def reset(self,*services,**constants):
        pass