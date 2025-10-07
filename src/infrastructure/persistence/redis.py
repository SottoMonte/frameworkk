import redis.asyncio as r
import framework.port.persistence as persistence
import json
import framework.service.flow as flow

class adapter(persistence.port):
    conn = None
    engine = None
    def __init__(self,**constants):
        self.config = constants['config'] 
        self.conn = r.from_url(f"redis://{self.config['host']}:{self.config['port']}")
    
    async def query(self, *services, **constants):
        pass

    @flow.asynchronous(ports=('storekeeper','messenger'))
    async def read(self, storekeeper, messenger, **constants):
        identifier = constants['identifier'] if 'identifier' in constants else 'test'
        boolean = await self.conn.exists(identifier)
        if boolean:
            typ = await self.conn.type(identifier)
            match typ.decode('ascii'):
                case 'list':
                    value = await self.conn.lrange(identifier, 0, -1)
                    #return VARIABLE(worker,typ.decode('ascii'),identifier,[x.decode('ascii') for x in value])
                    return None
                case 'string':
                    value = await self.conn.get(identifier)
                    
                    #return json.loads(value.decode('utf-8'))
                    return storekeeper.builder('transaction',{'state': True,'action':'read','result':json.loads(value.decode('utf-8'))})
                case 'set':
                    await self.conn.sadd(identifier, value)
                case 'dict':
                    return await self.conn.mget(identifier)
                case 'hash':
                    value = await self.conn.hgetall(identifier)
                    cov_dict = dict()

                    for x in value: cov_dict[x.decode("utf-8")] = value[x].decode("utf-8")

                    #return VARIABLE(worker,typ.decode('ascii'),identifier,{x.decode('ascii'):value[x].decode('ascii') for x in value})
                    return cov_dict
        else:
            typ = await self.conn.type(identifier)
            return storekeeper.builder('transaction',{'state': False,'action':'read','remark':'not found data'})

    @flow.asynchronous(ports=('storekeeper','messenger'))
    async def create(self, storekeeper, messenger, **constants):
        data = constants['value']
        identifier = constants['identifier'] if 'identifier' in constants else '#'
        boolean = await self.conn.exists(identifier)
        typee = str(type(data))

        if not boolean:
            #print(f'{worker.app.identifier}.{data.identifier}',data.value)
            #await worker.app.broker.mset({f'{worker.app.identifier}.{data.identifier}': XML(worker,data)})
            #await worker.app.broker.rpush(data.identifier, *data.value)
            
            match typee:
                case 'list':
                    await self.conn.rpush(identifier, *data)
                case 'string':
                    await self.conn.set(identifier, data)
                case 'set':
                    await self.conn.sset(identifier, data)
                case "<class 'dict'>":
                    #await worker.app.broker.mset(data.value)
                    try:
                        kwarg = dict()
                        if 'expiry' in self.config:kwarg['ex'] = int(self.config['expiry'])
                        await self.conn.set(identifier, json.dumps(data),**kwarg)
                    except Exception as e:
                        return storekeeper.builder('transaction',{'state': False,'action':'create','remark':f"{e}"})
                case 'hash':
                    await self.conn.hmset(identifier, data)
                case _:
                    try:
                        await self.conn.set(identifier, json.dumps(data))
                    except Exception as e:
                        print("ERRORE TIPO",typee)
                        return storekeeper.builder('transaction',{'state': False,'action':'create','remark':f"{e}"})
            return storekeeper.builder('transaction',{'state': True,'action':'create','remark':f"new identifier:{identifier} created"})
        else:    
            return storekeeper.builder('transaction',{'state': False,'action':'create','remark':f"this identifier:{identifier} already exists"})

    @flow.asynchronous(ports=('storekeeper',))
    async def delete(self, storekeeper, **constants):
        identifier = constants['identifier']
        typ = await self.conn.type(identifier)
        #print(f"REM::{identifier}",typ)
        boolean = await self.conn.exists(identifier)
        if boolean:
            
            match 'dict':
                case 'list':
                    #await worker.app.broker.lpop(identifier,2)
                    a = await self.conn.ltrim(identifier,0,10)
                    return storekeeper.builder('transaction',{'state': True,'action':'delete'})
                    #firma_funzione = inspect.signature(worker.app.broker.ltrim)
                    #print(firma_funzione)
                case 'string':
                    #print(dir(worker.app.broker))
                    a = await self.conn.delete(identifier)
                    return storekeeper.builder('transaction',{'state': True,'action':'delete'})
                case 'set':       
                    a = await self.conn.delete(identifier)
                    return storekeeper.builder('transaction',{'state': True,'action':'delete'})
                case 'dict':
                    #await worker.app.broker.hdel(identifier)
                    a = await self.conn.delete(identifier)
                    return storekeeper.builder('transaction',{'state': True,'action':'delete'})
                case 'hash':
                    keys = await self.conn.hkeys(identifier)
                    for key in keys:
                        id = f"{identifier}.{key.decode('ascii')}"
                        #print(id)
                        boolean = await self.conn.exists(id)
                        if boolean:
                            await self.delete(id)
                    await self.conn.hdel(identifier,*[key.decode('ascii') for key in keys])
                    return storekeeper.builder('transaction',{'state': True,'action':'delete'})
                case _:
                    try:
                        a = await self.conn.delete(identifier)
                        return storekeeper.builder('transaction',{'state': True,'action':'delete'})
                    except Exception as e:
                        return storekeeper.builder('transaction',{'state': False,'action':'delete','remark':f"{e}"})

    @flow.asynchronous(ports=('storekeeper',))
    async def write(self, storekeeper, **constants):
        identifier = constants['identifier']
        value = constants['value']
        boolean = await self.conn.exists(identifier)
        if boolean:
            typ = await self.conn.type(identifier)
            print(f"SET::{identifier}",typ)
            match typ.decode('ascii'):
                case 'list':
                    #print('list')
                    a = await self.conn.rpush(identifier, value)
                    return a
                case 'string':
                    #print('string')
                    await self.conn.set(identifier, str(value))
                case 'set':
                    #print('set')
                    await self.conn.sset(identifier, value)
                case 'dict':
                    #print('dict')
                    await self.conn.mset(identifier,value)
                case 'hash':
                    #print('hash')
                    await self.conn.hmset(identifier,value)
            #await SPEAK(worker,identifier,"change event")
        else:
            await self.create(constants)

    async def tree(self, *services, **constants):
        pass