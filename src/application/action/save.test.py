modules = {'flow':'framework.service.flow'}

import js
from js import ace,console
@flow.asynchronous(managers=('messenger','storekeeper','presenter'))
async def save(messenger,storekeeper,presenter,**constants):
    identifier = constants.get('identifier','')
    model = constants.get('model','')
    target = constants.get('target','')
    component = await presenter.component(name=target.replace('block-editor-',''))
    value = component['editor'].getValue()
    
    response = await storekeeper.change(model='file', repo='SottoMonte/framework',file_path=identifier, content=value)