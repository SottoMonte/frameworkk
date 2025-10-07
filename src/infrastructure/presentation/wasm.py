import sys

modules = {'flow': 'framework.service.flow','starlette': 'infrastructure.presentation.starlette'}
import urllib.parse
if sys.platform != 'emscripten':
  import os
  from starlette.responses import JSONResponse,HTMLResponse,RedirectResponse
else:
  import js
  from jinja2 import Environment, select_autoescape,FileSystemLoader,BaseLoader,ChoiceLoader,Template,DebugUndefined,Undefined
  import untangle
  import asyncio
  import pyodide
  import importlib
  import uuid
  import re
  import json
  import ast

  class MyLoader(BaseLoader):
      def get_source(self, environment, template):
          req = js.XMLHttpRequest.new()
          req.open("GET", f"application/view/layout/{template}", False)
          req.send()
          return req.response, None, None


class adapter(starlette.adapter):
  if sys.platform != 'emscripten':
    async def view(self,request):
        #html_page = await self.builder(url=self.views[request.url.path])
        #print('BOOM',self.views[request.url.path],html_page)
        #print('tututut',request.session)
        layout = 'application/view/layout/wasm.html'
        file = await self.host({'url':layout})
        css = await self.host({'url':layout.replace('.html','.css').replace('.xml','.css')})
        template = self.env.from_string(file.replace('{% block style %}','{% block style %}<style>'+css+'</style>'))
        html_template = template.render()
        #html_template = html_template.replace('<!-- Body -->',html_page)
        return HTMLResponse(html_template)
  else:
        def __init__(self, **constants):
          print("🚀 Inizializzazione del modulo WASM...")

          # Inizializza le variabili di istanza
          self.components = {}
          self.attributes = {}
          self.config = constants.get('config', {})  # Evita KeyError con .get()
          self.cash = {}
          self.cookies = {}
          self.data = {}
          self.views = {}
          # Configura il loader per i template
          http_loader = MyLoader()
          self.env = Environment(loader=http_loader, undefined=DebugUndefined, autoescape=select_autoescape(["html", "xml"]))
          self.env.filters['get'] = language.get_safe
          
          # Riferimento al documento JavaScript
          self.document = js.document

          # Attributi HTML diretti
          self.attributes['matter'] = {
                'id', 'type', 'name', 'component', 'draggable-event','height', 'width',
                'draggable-maker', 'droppable-data', 'identifier','draggable-component'
            }

          # Mappatura eventi
          self.attributes['event'] = {
                'click': ('click', self.event),
                'change': ('change', self.event),
                'route': ('click', self.route),
                'ddd': ('contextmenu', self.open_dropdown),
                'draggable': ('dragstart', self.on_drag_start),
                'droppable': ('drop', self.on_drop),
                'init': ('init', self.event),
            }
          
          # Mappatura eventi
          self.attributes['layout'] = {
            'space': lambda v: f"gap-{v}",
            'border': lambda v: f"border-{v}",
            'border-top': lambda v: f"border-top-{v}",
            'border-bottom': lambda v: f"border-bottom-{v}",
            'border-left': lambda v: f"border-start-{v}",
            'border-right': lambda v: f"border-end-{v}",
            'border-radius': lambda v: f"rounded-{v}",

            'margin': lambda v: ' '.join(v.strip() for v in v.split(';')),
            'margin-top': lambda v: 'mt-' + v,
            'margin-bottom': lambda v: 'mb-' + v,
            'margin-left': lambda v: 'ms-' + v,
            'margin-right': lambda v: 'me-' + v,

            'padding-top': lambda v: 'pt-' + v,
            'padding-bottom': lambda v: 'pb-' + v,
            'padding-left': lambda v: 'ps-' + v,
            'padding-right': lambda v: 'pe-' + v,
            'padding': lambda v: ' '.join(v.strip() for v in v.split(';')),

            'position': lambda v: {
                'static': 'position-static',
                'relative': 'position-relative',
                'absolute': 'position-absolute',
                'fixed': 'position-fixed',
                'sticky': 'position-sticky',
            }.get(v,''),
            'expand': lambda v: {
                'vertical': 'h-100',
                'horizontal': 'w-100',
                'full': 'w-100 h-100',
                'auto': 'col-auto',
                'dynamic': 'col'
            }.get(v, f"col-{v}"),
            'collapse': lambda v: 'd-none' if v == 'full' else 'invisible',
            'alignment-horizontal': lambda v: f"justify-content-{v}" if v in ['start', 'end', 'center', 'between', 'around', 'evenly'] else '',
            'alignment-vertical': lambda v: f"align-items-{v}" if v in ['start', 'end', 'center', 'baseline', 'stretch'] else '',
            'alignment-content': lambda v: {
                    'vertical': 'd-flex flex-column',
                    'horizontal': 'd-flex flex-row',
                    'center': 'd-flex justify-content-center align-items-center',
                    'between': 'd-flex justify-content-between align-items-center',
                    'around': 'd-flex justify-content-around align-items-center',
                    'evenly': 'd-flex justify-content-evenly align-items-center',    
                }.get(v, ''),
          }

          # Mappatura classi CSS
          self.attributes['style'] = {
                'background': lambda v: f"bg-{v}" if not v.startswith('#') else None,
                'background-color': lambda v: f"bg-{v}" if not v.startswith('#') else None,
                'text-color': lambda v: f"text-{v}",
                'text-size': lambda v: f"fs-{v}" if v.isdigit() else None,
                'shadow': lambda v: {
                    '0': 'shadow-none', '1': 'shadow-sm',
                    '2': 'shadow', '3': 'shadow-lg'
                }.get(v, ''),
                'opacity': lambda v: f"opacity-{v}" if v.isdigit() else None,
                'border': lambda v: f"border-{v}",
                'border-thickness': lambda v: f"border-{v}",
                'border-radius-size': lambda v: f"rounded-{v}",
                'border-color': lambda v: f"border-{v}",
                'border-radius': lambda v: {
                    'pill': "rounded-pill", 'circle': "rounded-circle",
                    'top': "rounded-top", 'bottom': "rounded-bottom",
                    'right': "rounded-start", 'left': "rounded-end"
                }.get(v, ''),
                'border-position': lambda v: {
                    'outer': "border", 'top': "border-top", 'bottom': "border-bottom",
                    'right': "border-start", 'left': "border-end"
                }.get(v, ''),
                'class': lambda v: v
            }

          print("✅ Modulo WASM inizializzato correttamente.")

        @flow.synchronous(managers=('storekeeper',))
        def loader(self, storekeeper, **constants):
          z = asyncio.create_task(self.bond(),name="bond")
          code = asyncio.create_task(self.async_loader(),name="loader")
          
        
        @flow.asynchronous(managers=("messenger", "storekeeper", "defender"))
        async def async_loader(self, messenger,storekeeper,defender, **constants):
              
              url = self.config['routes'].replace('src/','')
              data = await self.host({'url':url})
              self.mount_route(None,data)
              await messenger.post(domain="debug",message="🔄 Avvio async_loader...")
              # Estrai i cookie in modo più sicuro
              self.cookies = {
                  key.strip(): value
                  for cookie in js.document.cookie.split(';') if '=' in cookie
                  for key, value in [cookie.split('=', 1)]
              }
              
              await messenger.post(domain="debug",message=f"📜 Cookies: {self.cookies}")
              
              # Recupera il token di sessione in modo più sicuro
              session = self.cookies.get('session', 'None')
              session = eval(session)
              identifier = self.cookies.get('session_identifier', 'None')
              #session = eval(session)
              print(session,identifier,type(session),type(identifier),'TIKTIK')
              
              await defender.unionsession(session=session,identifier=identifier)
              #await messenger.post(domain="debug",message=f"🔑 Token recuperato: {session}")

              # Recupera i dati dell'utente con il token
              #transaction = await storekeeper.gather(model="user", token=token)
              transaction = await defender.whoami2(token=session)
              await messenger.post(domain="debug",message=f"📦 Transazione ricevuta: {transaction}")

              # Verifica se la transazione è riuscita
              transaction = {'state':False} if transaction == None else transaction
              user = transaction.get('result', {})[0] if transaction.get('state') else {}
              print(user,':USER')
              
              self.user = user

              # Costruisce l'HTML con i dati dell'utente
              #html_template = await self.builder(user=user,session=session)
              html_template = await self.builder()
              #html_page = await self.builder(url=self.views[js.window.location.pathname],user=user,session=session)
              html_page = await self.builder(url=self.views[js.window.location.pathname])

              # Rimuove l'elemento di caricamento
              loading_element = self.document.getElementById('loading')
              if loading_element:
                  loading_element.remove()
                  await messenger.post(domain="debug",message="✅ Elemento di caricamento rimosso.")

              # Aggiunge il contenuto alla pagina
              self.document.body.prepend(html_template)
              main = self.document.getElementById('main')
              main.appendChild(html_page)

              if transaction.get('state'):
                await messenger.post(domain="debug",message=f"👤 Dati utente: {user}")
                await messenger.post(domain="success",message="✅ Utente autenticato con successo.")
              else:
                await messenger.post(domain="error",message=transaction.get('error','Errore sconosciuto'))

              await messenger.post(domain="debug",message="✅ Contenuto aggiornato con i dati utente.")
              

        @flow.asynchronous(managers=('messenger',))
        async def bond(self,messenger,**constants):
          print("🔗 Avvio bond...")
          while True:
            print("🔄 Esecuzione del ciclo di polling...")
            msg = await messenger.read(domain="*")
            print(msg,'BONDmsg')
            domains = msg.get('domain',[])
            print(constants,'BOND',domains,msg)
            '''ok = []
            for x in self.data.keys():
                
                matching_domains = language.wildcard_match([domain], x)
                if len(matching_domains) == 1:
                    ok.append(x)
            print(ok,self.data)'''
            for domain in domains:
              for id  in self.data.get(domain,[]):
                self.components[id].setdefault('messenger',[]).append(msg)
                await self.rebuild(id,self.components[id].get('view'),message=msg)

            for id  in self.data.get('*',[]):
              self.components[id].setdefault('messenger',[]).append(msg)
              await self.rebuild(id,self.components[id].get('view'),message=msg)
              


        async def open_dropdown(self,event,**constants):
          
          if event.button == 2:  # Click sinistro del mouse
            # Ottieni l'elemento dropdown
            currentElement = event.target
            dropdown_button = None

            while not dropdown_button and currentElement:
              cerca = currentElement.querySelector('.dropdown-menu')
              if cerca:
                dropdown_button = currentElement
              currentElement = currentElement.parentElement

            if dropdown_button:
              # Ottieni le coordinate del click del mouse
              # Mostra il dropdown
              dropdown = js.bootstrap.Dropdown.getOrCreateInstance(dropdown_button)
              dropdown.toggle()       
            else:
                print("Elemento dropdown non trovato")
          

        async def route(self,event,**constants):
          currentElement = event.target
          attributeValue = None

          while not attributeValue: 
            attributeValue = currentElement.getAttribute('route')
            currentElement = currentElement.parentElement

          # Parsing dell'URL
          parsed = urllib.parse.urlparse(attributeValue)
          path = parsed.path
          query = urllib.parse.parse_qs(parsed.query)
          fragment = urllib.parse.parse_qs(parsed.fragment)
          print('BOOM',path,query,fragment)
          code = await self.builder(url=attributeValue,path=path,query=query,fragment=fragment)
          js.document.getElementById('main').innerHTML = ''
          js.document.getElementById('main').prepend(code)

        async def on_drag_start(self,event,**constants):
          #print('on_drag_start')
          '''for x in self.document.querySelectorAll(".drop-target"):
            x.className += " highlight"
          self.drag = event.target.id
          draggable_element = js.document.getElementById(event.target.id)
          self.drag_type = draggable_element.getAttribute('draggable-maker')
          print('BOOOM',self.self.drag_type)'''
          # Cerca tra il target e i suoi figli il primo elemento con draggable-maker
          def find_draggable_maker(element):
              if element.hasAttribute('draggable-maker'):
                  return element
              for child in element.children:
                  found = find_draggable_maker(child)
                  if found:
                      return found
              return None

          self.drag = event.target.id
          draggable_element = js.document.getElementById(event.target.id)
          maker_element = find_draggable_maker(draggable_element)
          if maker_element:
              self.drag_type = maker_element.getAttribute('draggable-maker')
              #print('BOOOM', self.drag_type)
          else:
              self.drag_type = None
              #print('Nessun draggable-maker trovato')

        async def on_drag_end(self, event, **constants):
          identifier = getattr(self, "drag", None)
          if identifier and identifier in self.components and self.components[identifier]:
              component_id = self.components[identifier].get('id')
              if component_id:
                  component = js.document.getElementById(component_id)
                  if component and 'opacity-25' in component.className:
                      component.className = component.className.replace(' opacity-25', '')

        @flow.asynchronous(managers=('executor',))
        async def on_drop(self,event,executor,**constants):
          event.preventDefault()
          #print('on_drop',self.drag)
          draggable_element = js.document.getElementById(self.drag)
          
          if self.drag in self.components:
            target = js.document.getElementById(event.target.id)
            #print(self.components[self.drag])
            data_drag = target.getAttribute('droppable-data')
            #print('data_drag',data_drag)
            name = self.components[self.drag].get('id')
            component = js.document.getElementById(name)
            component.className = component.className.replace(' opacity-25','')
            
            #component.className = component.className.replace('highlight','')
            if draggable_element.getAttribute('draggable-event'):
              await executor.act(action=draggable_element.getAttribute('draggable-event').replace(')',",data:'"+str(data_drag)+"')"))
          
          if self.drag_type == 'true' and self.drag in self.components:
            self.components.pop(self.drag)

          #for x in self.document.querySelectorAll(".drop-target"):
            #x.className = x.className.replace('highlight','')
        
        async def on_drag_leave(self,event,**constants):
          pass
          #event.target.className = event.target.className.replace('highlight','')
        
        async def on_drag_over(self,event,**constants):
          event.preventDefault()
          draggable_element = js.document.getElementById(self.drag)
          #print(draggable_element.getAttribute('draggable-domain'),event.target.getAttribute('draggable-domain'))
          if draggable_element and draggable_element.getAttribute('draggable-domain') == event.target.getAttribute('draggable-domain'):
            
            component = draggable_element.getAttribute('draggable-component')
            
            identifier = self.drag
            
            if component and identifier not in self.components:
                self.components[identifier] = ""
                #self.components[identifier] = identifier
                  #self.components[identifier] = dict({'id':identifier,'selected':[],'pageCurrent':1,'pageRow':10,'sortField':'CardName','sortAsc':True})
                url = f'application/view/component/{component}.xml'
                #view = await self.builder(url=url,component=self.components[identifier])
                attr = dict()
                for i in list(draggable_element.attributes):
                  attr[i.name] = i.value
                view = await self.builder(url=url,**attr)
                view.className += ' opacity-25'
                self.components[identifier] = {'id':view.getAttribute('id')}
                  #self.components[identifier]['id'] = view.getAttribute('id')
                #view.className += ' highlight'
                event.target.appendChild(view)
                #print("BOOOOOM")
                
            else:
              if identifier in self.components and self.components[identifier] != '':
                #component = js.document.getElementById(self.components[identifier])
                component = js.document.getElementById(self.components[identifier]['id'])
                #print(component)
                if 'opacity-25' not in event.target.className:
                  component.className += ' opacity-25'
                if event.target != component and component.parentNode != event.target:
                  mouseY = event.clientY
                  containerRect = event.target.getBoundingClientRect()
                  containerTop = containerRect.top

                  # Trova il figlio più vicino alla posizione del mouse
                  inserted = False
                  for child in event.target.children:
                      childRect = child.getBoundingClientRect()
                      if mouseY < (childRect.top + childRect.height / 2):
                          event.target.insertBefore(component, child)
                          inserted = True
                          break
                  if not inserted:
                      event.target.appendChild(component)
                '''if event.target != component and component.parentNode != event.target:
                  mouseY = event.clientY # Posizione verticale del mouse rispetto al viewport
                  containerRect = event.target.getBoundingClientRect() # Ottieni la posizione e dimensione dell'elemento di destinazione
                  containerTop = containerRect.top # La posizione in alto dell'elemento di destinazione
                  containerHeight = containerRect.height # Altezza dell'elemento di destinazione

                  # Calcola la posizione relativa del mouse all'interno dell'elemento di destinazione
                  mousePos = mouseY - containerTop

                  # Se il mouse è nella parte superiore dell'elemento, inserisci sopra, altrimenti sotto
                  if (mousePos < containerHeight / 2):
                    event.target.insertBefore(component, event.target.firstChild)
                  else:
                    event.target.appendChild(component)    '''     
        
        @flow.asynchronous(managers=('executor',))
        async def event(self,event,executor,**constants):
          #action = event.target.getAttribute('click')
          event_type = event.type
          print("Tipo di evento:", event_type)
          currentElement = event.target
          attributeValue = None

          while not attributeValue: 
            attributeValue = currentElement.getAttribute(event_type)
            currentElement = currentElement.parentElement

          _ = await executor.act(action=attributeValue)
        
        @flow.synchronous(managers=('executor',))
        def att2(self,element,attributes,executor):
          # 'property'
          base = ['id','opacity','color','shadow','border','class','width','height','visibility','position','padding','margin','expand','style','matter'],
          tt = {
            'div':[],
            'p':[],
            'matter':['color','size','alignment','position'],
            'text':['color','size','alignment','position'],
            'style':['border','opacity','class'],
            'border':['color','thickness','radius','opacity','position','style'],
          }

          sizes = ['0','1','2','3','4','5']
          events = ['click']
          colors = ['primary','primary-subtle','secondary','secondary-subtle','success','success-subtle','danger','danger-subtle','warning','warning-subtle','info','info-subtle','light','light-subtle','dark','dark-subtle','black','white']
          
          for key in attributes:
            value = attributes[key]
            match key:
              # Property
              case 'identifier':
                element.setAttribute('name',value)
              case 'name':
                element.setAttribute(key,value)
              case 'space':
                element.className += f" gap-{value}"
              case 'id':
                element.setAttribute(key,value)
              case 'width':
                style = element.getAttribute('style') if type(element.getAttribute('style')) == type('') else ''
                style += f" max-width:{value};width:{value};"
                element.setAttribute('style',style)
              case 'height':
                style = element.getAttribute('style') if type(element.getAttribute('style')) == type('') else ''
                style += f" max-height:{value};height:{value};"
                element.setAttribute('style',style)
              case 'margin':
                if ';' in value:
                  pp = value.split(';')
                  for x in pp:
                    element.className += ' '+x
                else:
                  element.className += ' '+value
              case 'padding':
                if ';' in value:
                  pp = value.split(';')
                  for x in pp:
                    element.className += ' '+x
                else:
                  element.className += ' '+value
              case 'alignment-horizontal':
                enums = ['start','end','center','between','around','evenly']
                if value in enums:
                  element.className += f" justify-content-{value}"
              case 'alignment-vertical':
                enums = ['start','end','center','baseline','stretch']
                if value in enums:
                  element.className += f" align-items-{value}"
              case 'alignment-content':
                #enums = ['start','end','center','baseline','stretch']
                match value:
                  case 'vertical':
                    element.className += " d-flex flex-column"
                  case 'horizontal':
                    element.className += " d-flex flex-row"
                  case 'center':
                    element.className += " d-flex justify-content-center align-items-center"
                  case 'between':
                    element.className += " d-flex justify-content-between align-items-center"
                  case 'around':
                    element.className += " d-flex justify-content-around align-items-center"
                  case 'evenly':
                    element.className += " d-flex justify-content-evenly align-items-center"
              case 'expand':
                match value:
                  case 'vertical':
                    element.className += " h-100"
                  case 'horizontal':
                    element.className += " w-100"
                  case 'full':
                    element.className += " w-100 h-100"
                  case 'auto':
                    element.className += " col-auto"
                  case 'dynamic':
                    element.className += " col"
                  case _:
                    element.className += f" col-{value} "
              case 'collapse':
                match value:
                  case 'full':
                    element.className += " d-none"
                  case 'visibility':
                    element.className += " invisible"
              case 'flow':
                match value:
                  case 'auto':element.className += f" overflow-{value} "
                  case 'hidden':element.className += f" overflow-{value} "
                  case 'visible':element.className += f" overflow-{value} "
                  case 'scroll':element.className += f" overflow-{value} "
              case 'type':
                element.setAttribute(key,value)
              case 'component':
                element.setAttribute(key,value)
              # Style
              case 'text-size':
                if 'px' in value:
                  style = element.getAttribute('style') if type(element.getAttribute('style')) == type('') else ''
                  style += f' font-size: {value};'
                  element.setAttribute('style',style)
                elif value in sizes:
                  element.className += f" fs-{value}"
              case 'text-font':pass
              case 'text-color':
                if value in colors:
                  element.className += f" fs-{value}"
              case 'text-style':pass
              case 'style':
                style = element.getAttribute('style') if type(element.getAttribute('style')) == type('') else ''
                style += ' '+value
                element.setAttribute('style',style)
              case 'background':
                if '#' in value:
                    style = element.getAttribute('style') if type(element.getAttribute('style')) == type('') else ''
                    style += f" background:{value};"
                    element.setAttribute('style',style)
                else:
                  element.className += f" bg-{value}"
              case 'background-opacity':pass
              case 'background-color':pass
              case 'shadow':
                match value:
                  case'none': element.className += " shadow-none"
                  case 'lg':  element.className += " shadow-lg"
                  case'md': element.className += " shadow"
                  case'sm': element.className += " shadow-sm"
              case 'class':
                element.className += f' {value}'
              case 'border':
                element.className += f" border-{value}"
              case 'border-position':
                match value:
                  case 'outer': element.className += " border"
                  case 'top': element.className += " border-top"
                  case 'bottom': element.className += " border-bottom"
                  case 'right': element.className += " border-start"
                  case 'left': element.className += " border-end"
              case 'border-thickness':
                if value in sizes:
                  element.className += f" border-{value}"
              case 'border-radius-size':
                if value in sizes:
                  element.className += f" rounded-{value}"
              case 'border-color':
                if value in colors:
                  element.className += f" border-{value}"
              case 'border-radius':
                match value:
                  case 'pill': element.className += " rounded-pill"
                  case 'circle': element.className += " rounded-circle"
                  case 'top': element.className += " rounded-top"
                  case 'bottom': element.className += " rounded-bottom"
                  case 'right': element.className += " rounded-start"
                  case 'left': element.className += " rounded-end"
              # Event
              case 'hide':
                mode,target = value.split(':')
                mode = mode.strip().lower()
                target = target.strip()
                element.setAttribute('data-bs-dismiss',mode)
              case 'show':
                mode,target = value.split(':')
                mode = mode.strip().lower()
                target = target.strip()
                match mode:
                  case 'modal':
                    element.setAttribute('data-bs-target','#'+target)
                    element.setAttribute('data-bs-toggle',mode)
                  case 'offcanvas':
                    element.setAttribute('data-bs-target','#'+target)
                    element.setAttribute('data-bs-toggle',mode)
                  
              case 'ddd':
                element.addEventListener('contextmenu',pyodide.ffi.create_proxy(self.open_dropdown))
              case 'link':
                element.setAttribute('href',value)
              case 'route':
                if ':' in value:
                  mode,target = value.split(':',1)
                  mode = mode.strip().lower()
                  target = target.strip()
                  match mode:
                    case 'link':
                      element.setAttribute('href',target)
                    case _:
                      element.setAttribute('data-bs-toggle',mode)
                      element.setAttribute('href','#'+target)
                else:
                  element.setAttribute('url',value)
                  element.addEventListener('click',pyodide.ffi.create_proxy(self.route))
              case 'click':
                element.setAttribute(key,value)
                element.addEventListener('click',pyodide.ffi.create_proxy(self.event))
              case 'onchange':
                element.setAttribute(key,value)
                element.addEventListener('change',pyodide.ffi.create_proxy(self.event))
              case 'init':
                element.setAttribute(key,value)
                asyncio.create_task(executor.act(action=value))
              case 'droppable':
                element.setAttribute('ondragover','allowDrop(event)')
                element.setAttribute('draggable-domain',value)
                element.addEventListener('drop',pyodide.ffi.create_proxy(self.on_drop))
                element.addEventListener('dragover',pyodide.ffi.create_proxy(self.on_drag_over))
                element.addEventListener('dragleave',pyodide.ffi.create_proxy(self.on_drag_leave))
              case 'draggable':
                element.setAttribute(key,'true')
                element.setAttribute('ondragstart','drag(event)')
                element.setAttribute('draggable-domain',value)
                element.addEventListener('dragstart',pyodide.ffi.create_proxy(self.on_drag_start))
                element.addEventListener('dragend',pyodide.ffi.create_proxy(self.on_drag_end)) 
              case 'draggable-component':
                element.setAttribute(key,value)
              case 'draggable-event':
                element.setAttribute(key,value)
              case 'draggable-maker':
                element.setAttribute(key,value)
              case 'droppable-data':
                element.setAttribute(key,value)
              
        @flow.synchronous(managers=('executor',))
        def att(self, element, attributes, executor):

            def set_style(css):
                style = element.getAttribute('style') or ''
                style += f" {css}"
                element.setAttribute('style', style)

            def add_class(cls):
                element.className += f" {cls}"

            for key, value in attributes.items():
                if key in self.attributes['matter']:
                    if key == 'width':
                      set_style(f'max-width:{value};width:{value};')
                    elif key == 'height':
                      set_style(f'max-height:{value};height:{value};')
                    else:
                      element.setAttribute(key, value)

                elif key in self.attributes['event']:
                    if key == 'init':
                        #print(f"[DEBUG] Executor: {executor}",value,key)
                        asyncio.create_task(executor.act(action=value))
                    elif key == 'hide':
                        mode, _ = map(str.strip, value.split(':'))
                        element.setAttribute('data-bs-dismiss', mode)
                    elif key == 'show':
                        mode, target = map(str.strip, value.split(':'))
                        element.setAttribute('data-bs-target', f'#{target}')
                        element.setAttribute('data-bs-toggle', mode)
                    elif key == 'route' and ':' in value:
                        mode, target = map(str.strip, value.split(':', 1))
                        if mode == 'link':
                            element.setAttribute('href', target)
                        else:
                            element.setAttribute('data-bs-toggle', mode)
                            element.setAttribute('href', f'#{target}')
                    elif key == 'link':
                        element.setAttribute('href', value)
                    elif key == 'draggable':
                        element.setAttribute(key,'true')
                        element.setAttribute('ondragstart','drag(event)')
                        element.setAttribute('draggable-domain',value)
                        element.addEventListener('dragstart',pyodide.ffi.create_proxy(self.on_drag_start))
                        element.addEventListener('dragend',pyodide.ffi.create_proxy(self.on_drag_end))
                    elif key == 'droppable':
                        element.setAttribute('ondragover','allowDrop(event)')
                        element.setAttribute('draggable-domain',value)
                        element.addEventListener('drop',pyodide.ffi.create_proxy(self.on_drop))
                        element.addEventListener('dragover',pyodide.ffi.create_proxy(self.on_drag_over))
                        element.addEventListener('dragleave',pyodide.ffi.create_proxy(self.on_drag_leave))
                    else:
                      event_name, handler_fn = self.attributes['event'][key]
                      #element.setAttribute('event', value)
                      element.setAttribute(key, value)
                      element.addEventListener(event_name, pyodide.ffi.create_proxy(handler_fn))

                elif key in self.attributes['style']:
                    mapping = self.attributes['style'][key]
                    cls = mapping(value) if callable(mapping) else mapping.get(value, f"{key}-{value}")
                    if cls:
                        add_class(cls)
                    elif key == 'background-color' and value.startswith('#'):
                        set_style(f'background-color:{value};')
                    elif key == 'text-size' and 'px' in value:
                        set_style(f'font-size: {value};')
                    elif key == 'style':
                        set_style(value)
                elif key in self.attributes['layout']:
                    mapping = self.attributes['layout'][key]
                    cls = mapping(value) if callable(mapping) else mapping.get(value, f"{key}-{value}")
                    if cls:
                        add_class(cls)
                       

        async def rebuild(self, id, tag, **data):
          try:
              #url = f"application/view/component/{tag}.xml"
              url = tag
              #new_component = await self.builder(url=url, **{'component':self.components.get(id,{})}|data)
              print('BOOM',self.components.get(id,{}))
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
              print(f"Errore durante la ricostruzione del componente '{id}': {e}")

        '''async def mount_css(self,constants):
          elements = constants.querySelectorAll('[component]')
          for element in elements:
            text = await self.host({'url':f"application/view/component/{element.getAttribute('component')}.css"})
            print(element.getAttribute('component'),'mount_css:',text)'''
        async def mount_css(self, constants):
          elements = constants.querySelectorAll('[component]')
          
          for element in elements:
              component_name = element.getAttribute('component')

              # Controlla se lo style è già presente nel <head>
              existing_styles = self.document.querySelectorAll(f'style[data-component="{component_name}"]')
              if existing_styles.length > 0:
                  #print(f"{component_name} style already mounted.")
                  continue  # Salta questo componente, lo style è già presente

              # Altrimenti scarica e aggiungi lo style
              css_text = await self.host({'url': f"application/view/component/{component_name}.css"})
              #print(component_name, 'mount_css:', css_text)

              # Crea nuovo tag <style>
              style_element = self.document.createElement('style')
              style_element.setAttribute('data-component', component_name)
              style_element.textContent = css_text

              # Inserisce lo <style> nel <head>
              self.document.head.appendChild(style_element)

        def mount_route(self, routes, url):
          route_map = {
              'model': self.model,
              'view': self.view,
              'action': self.action,
              'logout': self.logout,
              'login': self.login
          }

          for setting in untangle.parse(url).get_elements()[0].get_elements():
              path = setting.get_attribute('path')
              method = setting.get_attribute('method')
              typee = setting.get_attribute('type')
              view = setting.get_attribute('view')

              self.views[path] = view
              #route = Mount('/static', app=StaticFiles(directory='/public'), name='static') \
              #    if setting == 'Mount' else Route(path, endpoint=route_map.get(typee), methods=[method])

              #routes.append(route)

        def code_update(self, view, attr={}, inner=[], position='end'):
          """
          Modifica un elemento DOM esistente:
          - aggiorna gli attributi secondo 'attr'
          - aggiunge i figli di 'inner' (lista di elementi DOM o stringhe HTML)
            in base a 'position': 'start' (inizio) o 'end' (fine, default)
          """
          # Aggiorna attributi
          for key in attr:
              view.setAttribute(key, attr[key])

          # Aggiungi nuovi figli
          if isinstance(inner, list):
              if position == 'start':
                  # Inserisci in ordine inverso per mantenere l'ordine originale
                  for item in reversed(inner):
                      if hasattr(item, 'nodeType'):
                          view.insertBefore(item, view.firstChild)
                      elif isinstance(item, str):
                          temp = js.document.createElement('div')
                          temp.innerHTML = item
                          # Inserisci ogni nodo figlio all'inizio
                          for child in reversed(list(temp.childNodes)):
                              view.insertBefore(child, view.firstChild)
              else:  # 'end' (default)
                  for item in inner:
                      if hasattr(item, 'nodeType'):
                          view.append(item)
                      elif isinstance(item, str):
                          temp = js.document.createElement('div')
                          temp.innerHTML = item
                          for child in temp.childNodes:
                              view.append(child)
          elif isinstance(inner, str):
              if position == 'start':
                  temp = js.document.createElement('div')
                  temp.innerHTML = inner
                  for child in reversed(list(temp.childNodes)):
                      view.insertBefore(child, view.firstChild)
              else:
                  view.innerHTML += inner

          return view

        def code(self,tag,attr,inner=[]):
          tag = js.document.createElement(tag)
          for key in attr:
            tag.setAttribute(key,attr[key])

          if type(inner) == type([]):
            for item in inner:
              tag.append(item)
          elif type(inner) == type(''):
            tag.innerHTML += inner
          else:
            pass
          return tag
        
        async def host(self,constants):
          if 'url' not in constants:
            url="application/view/layout/app.xml"
          else:
            url = constants['url']
          if url not in self.cash:
            response = js.fetch(url,{'method':'GET'})
            file = await response
            aa = await file.text()
            self.cash[url] = aa
            return aa
          else:
            return self.cash[url]