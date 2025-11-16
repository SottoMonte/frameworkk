from abc import ABC, abstractmethod

class port(ABC):
    def __init__(self, ldap_server, user_dn, password):
        #self.server = Server(ldap_server, get_info=ALL)
        #self.user_dn = user_dn
        #self.password = password
        pass

    @abstractmethod
    def authorized(self):
        """
        Verifica se l'identità data è autorizzata a eseguire l'azione 
        sulla risorsa specificata.
        """
        pass

    @abstractmethod
    def permission(self):
        """
        Interroga per ottenere l'elenco delle azioni consentite 
        per l'identità sulla risorsa.
        """
        pass
    