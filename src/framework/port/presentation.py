from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from jinja2 import Environment, select_autoescape,FileSystemLoader,BaseLoader,ChoiceLoader,Template,DebugUndefined
from html import escape
import uuid
import untangle
import markupsafe
import re

import itertools

imports = {
    'tags': 'framework/scheme/tags.json',
    #'language': 'framework/service/language.py'
}

class port(ABC):

    def initialize(self):
        self.components = {}
        self.data = {}
        self.routes = {}
        # DOM
        self.document = {}
        fs_loader = FileSystemLoader("src/application/view/layout/")

        #http_loader = MyLoader()
        #choice_loader = ChoiceLoader([fs_loader, http_loader])

        ui_kit = [
            'breadcrumb',
            #'table',
            'badge',
            'input',
            'action',
            'text',
            #'media',
            'window',
            'card',
            #'navigation',
            'pagination',
            'group',
            'row',
            'column',
            'container',
            'defender',
            'messenger',
            'message',
            'storekeeper',
            'presenter',
            'view',
            'divider',
            'icon',
            'accordion',
            #'resource',
        ]
        
        for widget in ui_kit:
            if widget not in self.WIDGETS:
                raise NotImplementedError(f"Tag '{widget}' non gestito in compose_view")
        
        self.env = Environment(loader=fs_loader,autoescape=select_autoescape(["html", "xml"]),undefined=DebugUndefined)
        self.env.filters['route'] = language.route

    @abstractmethod
    async def get_attribute(self, widget, field):
        pass

    @abstractmethod
    async def set_attribute(self, widget, field, value):
        pass

    @abstractmethod
    async def selector(self, **constants):
        pass

    @abstractmethod
    async def mount_view(self, *services, **constants):
        pass

    @abstractmethod
    async def mount_route(self, *services, **constants):
        pass

    @abstractmethod
    async def mount_css(self, *services, **constants):
        pass

    '''@abstractmethod
    async def mount_widget(self, tag, inner, attributes):
        pass'''
    
    @language.asynchronous(managers=('defender','storekeeper'))
    async def builder(self, defender, storekeeperr, **constants):
        if 'text' in constants:
            text = constants['text']
        else:
            text = await language.fetch(path=constants.get('file',''))

        template = self.env.from_string(text)
        if 'data' not in constants:
            constants['data'] = {}
        if 'view' not in constants:
            constants['view'] = {}
        
        if 'inner' in constants:
            inner = constants['inner']
            placeholder = markupsafe.Markup('<Text>aaa</Text>')
            #placeholder = '<Text>aaa</Text>'
            ppp = await self.mount_widget('Text', ['aaa'], {'type':'text'})
            constants['inner'] = placeholder

        if 'user' not in constants:
            user = await defender.whoami(storekeeperr,identifier=constants.get('identifier'))
        else:
            user = {}
        
        #print(constants)

        content = template.render(constants|{'user':user})
        #print('Content:---------------------------*******************',content)
        xml = ET.fromstring(content)
        #print(xml)
        view = await self.render_view(xml,constants|{'user':user})
        #print('View:---------------------------*******************',type(view))
        #await self.render_css(view,view))
        if 'inner' in constants:
            if isinstance(inner, list):
                inner = ''.join(str(x) for x in inner)
            view = view.replace(ppp,inner)
        #print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!2",view,constants)
        return view

    async def rebuild(self, id, tag, **data):
          try:
              #url = f"application/view/component/{tag}.xml"
              url = tag
              #new_component = await self.builder(url=url, **{'component':self.components.get(id,{})}|data)
              #print('BOOM',self.components.get(id,{}))
              new_component = await self.builder(url=url, component=self.components.get(id,{}) , **data)
              old_component = self.document.getElementById(id)
              #old_component.innerHTML = new_component.innerHTML

              if old_component is None:
                  raise ValueError(f"Elemento con id '{id}' non trovato nel documento.")

              parent = old_component.parentNode
              if parent is None:
                  raise ValueError(f"L'elemento con id '{id}' non ha un nodo genitore.")

              # Sostituzione corretta
              #for x in new_component.childNodes:
              #  old_component.append(x)
              parent.replaceChild(new_component, old_component)

          except Exception as e:
              #print(f"Errore durante la ricostruzione del componente '{id}': {e}")
              pass
    
    async def render_widget(self, tag, inner, attributes, **context):

        widget = await self.mount_widget(tag, inner, attributes,**context)

        # Mount properties
        #for key in attributes:
        #    widget = await self.set_attribute(widget, key, attributes[key])

        # Ensure widget has an id
        wid = self.get_attribute(widget, 'id')
        if not wid:
            self.set_attribute(widget, 'id', str(uuid.uuid4()))
        
        return widget

    async def render_css(self, *services, **constants):
        await self.apply_css(*services)

    async def parse_route(self):
        # Regex per opzioni multiple senza virgolette (es. {a|b})
        regex_simple_options = r'\{([a-zA-Z0-9_|]+)\}'
        # Regex per parametri dinamici tipo {$id} -> {id}
        regex_dynamic_param = r'\{\$([a-zA-Z0-9_]+)\}'
        rotta = f"application/policy/presentation/{self.config.get('project',).get('policy').get('presentation')}"
        file = await language.fetch(path=rotta)
        policy = await language.convert(file,dict,'toml')
        routes = policy.get('store').get('data').get('routes')
        try:
            for setting in routes:
                path_attribute = setting.get('path')
                method = setting.get('method')
                typee = setting.get('type')
                view = setting.get('view')
                layout = setting.get('layout')

                if view:
                    view = 'application/view/page/' + view
                    if not path_attribute:
                        path_attribute = view.replace('.xml', '')

                # 🔥 Normalizza subito i parametri dinamici {$id} → {id}
                path_attribute = re.sub(regex_dynamic_param, r'{\1}', path_attribute)

                # Trova tutte le parti dinamiche con opzioni multiple
                all_matches = re.finditer(regex_simple_options, path_attribute)
                dynamic_parts = []
                options_sets = []

                for match in all_matches:
                    dynamic_parts.append(match.group(0))  # es. "{means|product}"
                    options_str = match.group(1)          # es. "means|product"
                    options = options_str.split('|')      # es. ["means", "product"]
                    options_sets.append(options)

                if dynamic_parts:
                    # Caso 1: opzioni multiple → espandi combinazioni
                    for combination in itertools.product(*options_sets):
                        new_path = path_attribute
                        for i, part in enumerate(dynamic_parts):
                            # sostituisci solo le opzioni multiple, NON i parametri dinamici
                            if '|' in part:
                                new_path = new_path.replace(part, combination[i], 1)
                        self.routes[new_path] = {
                            'view': view, 'type': typee,
                            'method': method, 'layout': layout
                        }
                else:
                    # Caso 2/3: percorsi statici o con parametri dinamici
                    self.routes[path_attribute] = {
                        'view': view, 'type': typee,
                        'method': method, 'layout': layout
                    }

        except Exception as e:
            #print(f"Si è verificato un errore durante il parsing del file: {e}")
            pass

    @language.asynchronous(managers=('storekeeper','messenger'))
    async def render_view(self,root,data,storekeeper,messenger):
        inner = []

        tag = root.tag
        attributes = root.attrib
        text = root.text
        elements = list(root)

        #and tag in self.tags
        if len(elements) > 0:
            for element in elements:
                mounted = await self.render_view(element, data)
                inner.append(mounted)
        
        
        
        if tag in tags:
            schema = tags[tag]

            schema_data = await language.normalize({tag:attributes},{tag:schema.copy()})
            attributes |= schema_data.get(tag,{})
            #print('Schema:',tttt)
            #print('Rendering tag:',tag,attributes,schema)
            
            
            
            if '_return' in schema:
                function = schema['_return']['function']
                args = [attributes[arg] for arg in schema['_return'].get('args',[]) if arg in attributes]
                input_type = schema.get('_input','inner')
                if input_type == 'text':
                    inner = str(text)
                if input_type == 'mixed' and text is not None:
                    inner.append(str(text))

                #print('Function#################################:',inner)
                match function:
                    case 'mount_view':
                        #print('Mounting view:',args)
                        if 'route' in attributes:
                            return await self.mount_view(*args,**{'model':['ok']})
                        else:
                            ok = await self.builder(file="application/view/content/"+attributes.get('view'),inner=inner,**{'view':attributes,'url':data.get('url',''),'storekeeper':data.get('storekeeper',{}),'component':data.get('component',{})})
                            return ok
                    case 'render_widget':
                        #print('Rendering widget:',data)
                        return await self.render_widget(*schema['_return'].get('args',[]), inner, attributes, **{'url':data.get('url',''),'storekeeper':data.get('storekeeper',{})})
                    case 'render_widget_storekeeper':
                        
                        #print('Rendering widget:',data)
                        if attributes.get('filter'):
                            filtro = language.convert(attributes.get('filter',''),'dict')
                            #print(filtro)
                        else:
                            filtro = {}
                        
                        transaction = await storekeeper.gather(repository=attributes.get('repository',''),filter=filtro,payload={})
                        
                        #exit(10) 'eq': {'id':'10'}
                        #return await self.render_widget(*schema['_return'].get('args',[]), inner, attributes, **{'url':data.get('url',''),'storekeeper':transaction})
                        #print(inner)
                        inner = []
                        if len(elements) > 0:
                            for element in elements:
                                mounted = await self.render_view(element, data|{'storekeeper':transaction})
                                inner.append(mounted)
                        ok= await self.builder(file="src/application/view/component/Tiat.xml",text='<Row>{{inner|safe}}</Row>',**{'inner':inner,'url':data.get('url',''),'storekeeper':transaction})
                        #print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",ok)
                        #exit(10)
                        return ok              
            if '_type' in schema:
                schema_type = schema['_type'].get(attributes.get('type', ''))
                input_type = schema.get('_input','inner')
                if input_type == 'text':
                    inner = str(text)
                if input_type == 'mixed' and text is not None:
                    inner.append(str(text))
                if schema_type:
                    if input_type == 'inner':
                        return await self.render_widget(schema_type, inner, attributes, **{'url':data.get('url',''),'storekeeper':data.get('storekeeper',{})})
                    elif input_type == 'text':
                        return await self.render_widget(schema_type, text, attributes, **{'url':data.get('url',''),'storekeeper':data.get('storekeeper',{})})
                    elif input_type == 'mixed':
                        return await self.render_widget(schema_type, inner, attributes, **{'url':data.get('url',''),'storekeeper':data.get('storekeeper',{})})
                    else:
                        #print('Unknown input type:',input_type)
                        pass
                #print('Mounting widget:',schema_type,tag,attributes.get('type',''))
        else:
            return await self.render_widget(tag, inner, attributes, **{'url':data.get('url',''),'mode':['component'],'storekeeper':data.get('storekeeper',{})})

    async def mount_widget(self, tag, children, user_attrs, **context):
        #print(tag,'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!',context)
        """Mounts a widget using data-driven config."""
        user_attrs = user_attrs or {}
        widget_name = tag.lower()

        widget_config = self.WIDGETS.get(widget_name)
        
        if not widget_config:
            widget_config = {'component':tag}
            #return self.code('p', {'class': 'text'}, f"Widget non implementato: {tag}")
            
            

        # Merge attributi: unisci config + user, con gestione speciale della classe
        default_attrs = widget_config.get('attributes', {})
        #merged_attrs = {**default_attrs, **user_attrs}
        #print("USERS",user_attrs)

        element_tag = widget_config.get('tag')
        
  
        element_attrs = default_attrs | user_attrs
        if "class" in default_attrs and "class" in user_attrs:
            element_attrs["class"] = f"{default_attrs['class']} {user_attrs['class']}"

         # Gestione dell'ordine di esecuzione
        execution_order = widget_config.get('order', ['case', 'test', 'wrapper_each', 'inner_overwrite', 'inner_last', 'inner_first', 'wrapper_once', 'inner_append', 'in', 'component','overwrite_each'])

        hooks = {
            'case': (widget_config.get('case'), 0),
            'test': (widget_config.get('test'), 1),
            'wrapper_each': (widget_config.get('wrapper_each'), 1),
            'inner_overwrite': (widget_config.get('inner_overwrite'), 1),
            'inner_last': (widget_config.get('inner_last'), 2),
            'inner_first': (widget_config.get('inner_first'), 2),
            'wrapper_once': (widget_config.get('wrapper_once'), 1),
            'inner_append': (widget_config.get('inner_append'), 1),
            'in': (widget_config.get('in'), 1),
            'component': (widget_config.get('component'), 5),
            'overwrite_each': (widget_config.get('overwrite_each'), 6),
        }

        mass = ['last','first','each']
        targets = ['last','first','each','inner']
        acts = ['overwrite','append','']
        
        for hook_name in execution_order:
            if hook_name not in hooks or hooks[hook_name][0] is None:
                continue

            hook, arg_type = hooks[hook_name]
            match arg_type:
                case 0:
                    hook_result = hook(element_attrs)
                case 1:
                    hook_result = hook(self, element_attrs, children)
                case 2:
                    hook_result = hook(self, element_attrs, children, user_attrs)
                    #print("HOOK RESULT:",user_attrs)
                case 5:
                    hook_result = hook
                    pass
                case 6:
                    hook_result = []
                    for cc in children:
                        hook_result.append(hook(self, element_attrs, cc))


            match hook_name:
                case 'case':
                    element_tag, temp = hook_result
                    #temp |= element_attrs | user_attrs

                    if "class" in element_attrs:
                        temp["class"] += f" {element_attrs['class']}"
                    element_attrs = element_attrs|temp
                    
                case 'wrapper_each':
                    if callable(hook_result):
                        children = [hook_result(self, element_attrs, child) for child in children]
                case 'wrapper_once':
                    if callable(hook_result):
                        children = hook_result(self, element_attrs, children)
                case 'inner_overwrite':
                    if hook_result:
                        overwrite_attrs, _ = hook_result
                        #print(children,'BOOOOOOOOOOOOOOOOOOOOOOOM KTWWWWWWWWWWWWWWWWWWWWWWWWWW')
                        
                        children = [self.code_update(child, overwrite_attrs) for child in children]
                case 'overwrite_each':
                    temp = []
                    if hook_result:
                        for xx in range(len(hook_result)):
                            overwrite_attrs, _ = hook_result[xx]
                            temp.append(self.code_update(children[xx], overwrite_attrs))
                    children = temp
                case 'inner_last':
                    if hook_result:
                        overwrite_attrs, ggg = hook_result
                        if ggg == '':
                            mode = []
                        else:
                            mode = ['replace']
                        children[-1] = self.code_update(children[-1], overwrite_attrs,ggg,mode)
                case 'inner_first':
                    if hook_result:
                        overwrite_attrs, ggg = hook_result
                        if ggg == '':
                            mode = []
                        else:
                            mode = ['replace']
                        children[0] = self.code_update(children[0], overwrite_attrs,ggg,mode)
                case 'inner_append':
                    if hook_result:
                        tagg,overwrite_attrs, inn = hook_result
                        children.append(self.code(tagg, overwrite_attrs,inn))
                case 'test':
                    if hook_result:
                        if isinstance(hook_result, tuple):
                            overwrite_attrs, ggg = hook_result
                            children = await self.builder(file=overwrite_attrs,inner=ggg,**{'url':context.get('url',''),'storekeeper':context.get('storekeeper',{})})
                            #return children
                            #inner.append(ggg)
                            #children = await self.builder(file=overwrite_attrs,inner=ggg,mode=['layout'])
                case 'component':
                    #print('Component#############################################################11111#111#111#:',hook_result,element_attrs,children)
                    #exit(1)
                    def elements_to_xml_string(elements):
                        # Crea un elemento root temporaneo
                        root = ET.Element('root')
                        
                        # Aggiungi tutti gli elementi alla root temporanea
                        for element in elements:
                            root.append(element)
                        
                        # Converti l'elemento root temporaneo in una stringa XML
                        xml_string = ET.tostring(root, encoding='unicode', method='xml')
                        
                        # Rimuovi il tag root temporaneo
                        xml_string = xml_string.replace('<root>', '').replace('</root>', '').replace('<root />','').strip()
                        
                        return xml_string
                    
                    '''if 'inner' in data:
                        data.pop('inner')
                    if 'component' in data:
                        data.pop('component')'''
                    
                    #xml_string = elements_to_xml_string(elements)
                    url = f'application/view/component/{hook_result}.xml'
                    #print('Component#############################################################11111#111#111#:',url,element_attrs,children)
                    #attrii = ''.join(x.outerHTML for x in att)
                    id = element_attrs['id'] if 'id' in element_attrs else str(uuid.uuid1())
                    if id not in self.components:
                        self.components[id] = {'id': id}
                        self.components[id]['view'] = f'application/view/component/{tag}.xml'
                        #attributes = " ".join([f"{key}='{value}'" for key, value in att.items()])
                        #self.components[id]['inner'] = f"<{tag} id='{id}' >{markupsafe.Markup(xml_string)}{data.get('code','')}</{tag}>"
                        self.components[id]['attributes'] = element_attrs
                        #self.components[id]['storekeeper'] = data.get('storekeeper',dict())

                    '''inner = markupsafe.Markup(xml_string)+data.get('code','')
                    if 'text' in data:
                        data.pop('text')
                        pass'''
                    #await messenger.post(domain='debug',message=f"✅ Elemento: {tag}|{id} creato.")
                    
                    argg = {
                        'component':self.components.get(id,{}),
                        'file':url,
                        'inner':children,
                        #'storekeeper':context.get('storekeeper',{})
                    }
                    argg = context|argg
                    #print(att,data.get('storekeeper',{}).get('component',{}),id,tag,'DATA|COM',data)
                    #print(att,data.get('storekeeper',{}).get('component',{}),id,tag,'DATA|arg',argg)
                    # Creiamo la vista per il componente
                    
                    view = await self.builder(**argg)

                    #view = await self.mount_view(root,data)

                    self.att(view, {'component':tag})
                    return view

        for key in widget_config.get('!attributes', {}):
            value = widget_config.get('!attributes', {}).get(key, [])
           
            if key in element_attrs and element_attrs.get('type') in value:
                
                # Se l'attributo è presente in !attributes, lo rimuoviamo da user_attrs
                # per evitare conflitti con gli attributi predefiniti del widget
                #del user_attrs[key]
                element_attrs.pop(key)
        #print(element_tag,'-----------------------------------------FINAL ATTRS:-------------------------------',element_attrs)
        return self.code(element_tag, element_attrs, children)


    @staticmethod
    @language.asynchronous(managers=('messenger','presenter','executor'))
    async def action_form(messenger,presenter,executor,**constants):
        target = constants.get('id','')
        action = constants.get('action','')
        form_data = {}
        # Ottieni il form e i dati
        
        form = await presenter.selector(id=target)
        #print(type(form))
        elements = await presenter.get_attribute(widget=form[-1],field="elements")
        #print('form:',form,target,elements)
        for input in elements:
            name = await presenter.get_attribute(widget=input,field="name")
            if name:
                if name.endswith('[]'):
                    key = name[:-2]
                    form_data.setdefault(key, []).append(input.value)
                else:
                    form_data[name] = input.value
        #print(form_data)

        max_len = max((len(v) for v in form_data.values() if isinstance(v, list)), default=1)
        items = []
        # Cicla su ogni elemento da aggiornare
        for i in range(max_len):
            item = {}
            for key, value in form_data.items():
                if isinstance(value, list):
                    item[key] = value[i] if i < len(value) else None
                else:
                    item[key] = value
            items.append(item)

        #print('items:', items,form_data)
        #await executor.act(action=action,**form_data|{'items':items})
        
        if not any(isinstance(v, list) for v in form_data.values()):
            #print('Single item submission')
            await executor.act(action=action, **form_data)
        else:
            for item in items:
                await executor.act(action=action, **item)