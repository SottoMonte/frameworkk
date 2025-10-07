import asyncio
import redis.asyncio as r
import framework.port.message as message
import framework.service.flow as flow
import datetime
from ast import literal_eval
import importlib
import json

class adapter(message.port):

    def __init__(self,**constants):
        self.config = constants['config'] 
        self.connection = self.loader()
        self.processable = dict()

    def loader(self,*managers,**constants):
        return r.from_url(f"redis://{self.config['host']}:{self.config['port']}")

    # Used for talk with other Workers
    @flow.asynchronous(args=('policy','name','value','identifier'),ports=('storekeeper',))
    async def post(self,storekeeper,**constants):
        #async with worker.app.broker.pubsub() as pubsub:
            #await worker.app.broker.publish(key, value)
        #asyncio.get_running_loop().create_task(worker.app.broker.publish(key, value))
        '''for key in constants['keys']:
            await constants['app'].broker.publish(key, constants['value'])'''
        '''identifier = constants['identifier'] if 'identifier' in constants else []  
        payload = constants['value'] if 'value' in constants else ''
        await self.connection.publish(identifier, payload)'''
        payload = constants['value'] if 'value' in constants else ''
        domain = [self.app+'.'+constants['name']] if 'name' in constants else [self.app]
        identifier = constants['identifier'] if 'identifier' in constants else ''
        #value = str(storekeeper.builder('action:'+constants['name'],payload))
        
        await self.signal(keys=domain,value=str(payload),identifier=identifier,name=constants['name'])
        #await worker.app.broker.xadd(key, {'message': value},maxlen=10)
        #b = await worker.app.broker.xlen(key)
        #print(b)

    @flow.asynchronous(ports=('storekeeper',))
    async def get(self,storekeeper,**constants):
        '''async def reader(channel):
            while True:
                await asyncio.sleep(0.01)
                print("########")
                message = await channel.get_message(ignore_subscribe_messages=True)
                if message is not None:
                    print(f"--------------------------------------(Reader) Message Received: {message}")
                    if message["data"].decode() == 'stop':
                        print("(Reader) STOP")
                        break
                    

        async with self.connection.pubsub() as pubsub:
            await pubsub.psubscribe(*constants['keys'])
            #if coroutine == None:
            #await pubsub.subscribe(**coroutine)
            future = asyncio.create_task(reader(pubsub))
            await future
            #await pubsub.psubscribe("tokens")'''
        identifier = constants['identifier']
        max = 0
        while max < 10:
            await asyncio.sleep(0.5)
            output = await storekeeper.get(model='transaction',identifier=identifier)
            if output != None and output['state']:
                await storekeeper.pull(model='transaction',identifier=identifier)
                return output
            max += 1
        return storekeeper.builder('transaction',{'identifier':identifier,'state':False})
        

    async def signal(self,**constants):
        for key in constants['keys']:
            #await constants['app'].broker.publish(key, constants['value'])
            #await constants['app'].broker.xadd(key,{ 'v': constants['value'] })
            pp = constants['value']
            await self.connection.xadd(self.app,{'identifier':constants['identifier'],'payload':pp,'domain':key,'action':constants['name'],'time':str(datetime.datetime.now())})
        
        #print( f"stream '{sname}' length: {r.xlen( stream_key )}")

    
    async def can(self,**constants):
        name = constants['name']
        #if constants['name'] in self.processable: return True
        #else: return False

        try:
            model = importlib.import_module(f"application.plug.action.{name}", package=None)
            action = getattr(model,name)
            self.processable[name] = action
            return True
        except ImportError:return False

    @flow.asynchronous(ports=('storekeeper','messenger'))
    async def react(self, storekeeper,messenger, **constants):
        while True:
            await asyncio.sleep(1.1)
            message = await self.connection.xread(count=1, streams={constants['domain']:0} )
            
            if len(message) != 0:
                id = message[0][1][0][0]
                payload = message[0][1][0][1]
               # print(l)
                #await constants['app'].broker.xack(constants['keys'][0],'',l[0][1][0][0])
                #print(payload)
                
                str_dict = {k.decode('utf-8'): v.decode('utf-8') for k, v in payload.items()}
                a = storekeeper.builder('event',str_dict)
                key = a['domain'].split('.')
                a['payload'] = literal_eval(a['payload'])
                name = key[len(key)-1]
                if name in self.processable:
                    
                    await self.connection.xdel(constants['domain'],id)
                    #print(a)
                    response = await self.processable[name](**a)
                    await messenger.post(name="log",value=f"Action start {name}")
                    #print(response)
                    if 'identifier' in a and  '' != a['identifier']:
                        await storekeeper.put(model='transaction',identifier=a['identifier'],value=response)