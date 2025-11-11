import sys
import asyncio

imports = {
}

class messenger():

    def __init__(self,**constants):
        #print('MES-',constants)
        self.providers = constants['providers']['message']
        pass

    @language.asynchronous(inputs='messenger',outputs='transaction')
    async def post(self,**constants):
        '''operations = []
        map_tasks = dict()
        # email -> email | log,fs -> messaggio | app -> evento
        #sender, receiver 
        receiver = None

        # Adds operation if profile matches
        for provider in self.providers:
            profile = provider.config['profile'].upper()
            domain_provider = provider.config.get('domain','*').split(',')
            domain_message = constants.get('domain',[])
            #print(f"Domain: {domain_message} - Provider: {domain_provider}",[match for item in domain_provider for match in language.wildcard_match(domain_message, item)])
            if len([match for item in domain_provider for match in language.wildcard_match(domain_message, item)]) > 0:
                #can = await provider.can(**constants)
                #if can or profile in allowed:
                operations.append(provider.post(location=profile, **constants))
                map_tasks[len(operations)-1] = profile

        # Commit all operations at the same time   
        transactions = await asyncio.gather(*operations)'''
        for provider in self.providers:
            #profile = provider.config['profile'].upper()
            #domain_provider = provider.config.get('domain','*').split(',')
            #domain_message = constants.get('domain',[])
            await provider.post(**constants)

    #@flow.asynchronous(inputs='messenger',outputs='transaction')
    async def read(self,**constants):
        prohibited = constants['prohibited'] if 'prohibited' in constants else []
        allowed = constants['allowed'] if 'allowed' in constants else ['FAST']
        operations = []
        
        for provider in self.providers:
            profile = provider.config['profile'].upper()
            domain_provider = provider.config.get('domain','*').split(',')
            domain_message = constants.get('domain',[])
            #print(f"Domain: {domain_message} - Provider: {domain_provider}",[match for item in domain_provider for match in language.wildcard_match(domain_message, item)])
            #if len([match for item in domain_provider for match in language.wildcard_match(domain_message, item)]) > 0:
            #if profile in allowed:
            task = asyncio.create_task(provider.read(location=profile,**constants))
            operations.append(task)
        
        finished, unfinished = await asyncio.wait(operations, return_when=asyncio.FIRST_COMPLETED)
        for operation in finished:
            return operation.result()
        #return finished[0].result()
        '''while operations:
            
            finished, unfinished = await asyncio.wait(operations, return_when=asyncio.FIRST_COMPLETED)
            
            
            for operation in finished:
                transaction = operation.result()
                if transaction['state']:
                    result = transaction['result']

                    for task in unfinished:
                        task.cancel()
                    if unfinished:
                        await asyncio.wait(unfinished)
                    
                    return result
                else:
                    if len(operations) == 1:
                        return transaction

            operations = unfinished'''