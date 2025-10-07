from unittest import IsolatedAsyncioTestCase

class port(IsolatedAsyncioTestCase):
    
    @classmethod
    def setUpClass(cls):
        """
        Configura il test adapter una sola volta per tutti i test.
        """
        cls.test = cls.adapter(config=cls.config)

        # Assicura che i metodi astratti siano implementati
        for method in cls.port.__abstractmethods__:
            if not hasattr(cls.test, method):
                raise AssertionError(f"{type(cls.test).__name__} non implementa il metodo astratto '{method}'")
