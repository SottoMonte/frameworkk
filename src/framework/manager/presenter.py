class presenter():
    def __init__(self,**constants):
        self.providers = constants['providers']

    async def selector(self,**constants):
        name = constants.get('name','')
        driver = language.last(self.providers)
        return await driver.selector(**constants)

    async def get_attribute(self,**constants):
        driver = language.last(self.providers)
        out = await driver.get_attribute(constants.get('widget'),constants.get('field'))
        return out

    async def builder(self,**constants):
        driver = language.last(self.providers)
        out = await driver.builder(**constants)
        return out
    
    async def navigate(self,**constants):
        driver = language.last(self.providers)
        out = await driver.apply_route(**constants)

    async def component(self,**constants):
        name = constants.get('name','')
        driver = language.last(self.providers)
        return driver.components[name]
        
    async def rebuild(self,**constants):
        driver = language.last(self.providers)
        await driver.rebuild(constants.get('id',''),constants.get('view',''),**constants.get('data',dict()))