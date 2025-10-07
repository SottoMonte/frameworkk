#from ldap3 import Server, Connection, ALL

from abc import ABC, abstractmethod

class port(ABC):
    def __init__(self, ldap_server, user_dn, password):
        #self.server = Server(ldap_server, get_info=ALL)
        #self.user_dn = user_dn
        #self.password = password
        pass

    @abstractmethod
    def authenticate(self):
        pass