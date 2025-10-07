from abc import ABC, abstractmethod

# encrypted

class secure(ABC):

    @abstractmethod
    def loader(**constants):
        pass

    @abstractmethod
    def encryption(self,**constants):
        pass

    @abstractmethod
    def decryption(self,**constants):
        pass