import asyncio
import importlib

imports = {
}

class storekeeper():

    def __init__(self,**constants):
        self.providers = constants['providers']

    async def preparation(self, **constants):
        operations = []
        operation = constants.get('operation', 'read')
        repository_name = constants.get('repository', '')

        try:
            repository_module = await language.fetch(path=f"application/repository/{repository_name}.py")
            repository = repository_module.repository()
        except Exception as e:
            print(f"Errore durante il caricamento del modulo repository '{repository_name}': {e}")
            return None, []
        
        
        for provider in self.providers.get('persistence'):
            print(self.providers,provider)
            try:
                profile = provider.config.get('profile', '').upper()
                print(self.providers,provider,profile)
                if not profile:
                    print(f"Provider {provider} non ha un profilo configurato.")
                    continue

                if profile in repository.location:
                    try:
                        task_args = await repository.parameters(operation, profile, **constants)
                    except Exception as e:
                        print(f"Errore durante l'ottenimento dei parametri per {profile}: {e}")
                        continue

                    # Controllo che il metodo esista nel provider
                    method = getattr(provider, operation, None)
                    if not callable(method):
                        print(f"Il metodo '{operation}' non è disponibile per il provider {profile}.")
                        continue

                    task = asyncio.create_task(method(**task_args), name=profile)
                    task.parameters = task_args
                    operations.append(task)
                else:
                    print(f"Provider {provider} non ha un profilo trovato.")
            except Exception as e:
                print(f"Errore imprevisto durante la preparazione per il provider {provider}: {e}")
        print(repository,operations)
        return repository, operations
    
    # overview/view/get
    @language.asynchronous(inputs='storekeeper',outputs='transaction',managers=('executor',))
    async def overview(self, executor, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'view'})
        return await executor.first_completed(operations=operations,success=repository.results)

    # gather/read/get
    @language.asynchronous(inputs='storekeeper',outputs='transaction',managers=('executor',))
    async def gather(self, executor, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'read'})
        return await executor.first_completed(operations=operations,success=repository.results)
    
    # store/create/put
    @language.asynchronous(inputs='storekeeper',outputs='transaction',managers=('executor',))
    async def store(self, executor, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'create'})
        return await executor.first_completed(operations=operations,success=repository.results)
    
    # remove/delete/delete
    @language.asynchronous(inputs='storekeeper',outputs='transaction',managers=('executor',))
    async def remove(self, executor, **constants):
        repository,operations = await self.preparation(**constants|{'operation':'delete'})
        return await executor.first_completed(operations=operations,success=repository.results)
    
    # change/update/patch
    @language.asynchronous(inputs='storekeeper',outputs='transaction',managers=('executor',))
    async def change(self,executor,**constants):
        repository,operations = await self.preparation(**constants|{'operation':'update'})
        return await executor.first_completed(operations=operations,success=repository.results)