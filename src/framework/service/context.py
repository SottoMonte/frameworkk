from dependency_injector import containers, providers
import logging

class Container(containers.DeclarativeContainer):
    
    # wiring_config removed to avoid circular imports. 
    # Modules using explicit container access do not need wiring.
    # If @inject is used, wire in bootstrap.

    # Core components
    config = providers.Configuration()
    
    # Logging buffer (replacing di['log_buffer'])
    log_buffer = providers.Singleton(list)
    
    # Module cache (replacing di['module_cache'])
    module_cache = providers.Singleton(dict)
    
    # Loading stack (replacing di['loading_stack'])
    loading_stack = providers.Singleton(set)
    
    import asyncio
    module_cache_lock = providers.Singleton(asyncio.Lock)

    
    # We will add other providers dynamically at runtime
    
# Global container instance
container = Container()
