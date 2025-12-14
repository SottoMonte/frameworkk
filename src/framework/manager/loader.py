import framework.service.load as load_service
from framework.service.context import container

class loader:
    """
    Manager that handles resource loading and bootstrapping by delegating to the load service.
    """
    def __init__(self, **constants):
        self.config = constants
        pass

    async def resource(self, **kwargs):
        """
        Loads a resource using the load service.
        """
        return await load_service.resource(**kwargs)

    async def bootstrap(self):
        """
        Bootstraps the framework.
        """
        return await load_service.bootstrap()
    
    async def register(self, **kwargs):
        """
        Registers a dependency injection entry.
        """
        return await load_service.register(**kwargs)