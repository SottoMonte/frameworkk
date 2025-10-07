modules = {'flow': 'framework.service.flow',}

import sys
import json
import asyncio
import datetime
import xml.etree.ElementTree as ET
import os
from jinja2 import Template

if sys.platform == 'emscripten':
    import pyodide

    async def backend(method, url, headers, payload):
        if method == 'GET':
            response = await pyodide.http.pyfetch(url, method=method, headers=headers)
        else:
            payload = json.dumps(payload if isinstance(payload, dict) else {})
            response = await pyodide.http.pyfetch(url, method=method, headers=headers, body=payload)
        if response.status in [200, 201]:
            return {"state": True, "result": await response.json()}
        else:
            return {"state": False, "result": [], "remark": f"Request failed with status {response.status}"}
else:
    import aiohttp

    async def backend(method, url, headers, payload):
        async with aiohttp.ClientSession() as session:
            async with session.request(method=method, url=url, headers=headers, json=payload) as response:
                rr = await response.json()
                print(rr)
                if response.status in [200, 201]:
                    return {"state": True, "result": rr}
                else:
                    return {"state": False, "remark": f"Request failed with status {response.status}"}


import os
import json
import subprocess
import datetime
import xml.etree.ElementTree as ET
from jinja2 import Template


class adapter:
    def __init__(self, **constants):
        self.config = constants.get('config', {})
        self.api_url = self.config.get('url', '')
        self.token = self.config.get('token', '')
        self.authorization = self.config.get('authorization', 'Bearer')
        self.accept = self.config.get('accept', 'application/json')
        self.scheduled_jobs = []
        self.cases = {}


        aaa = """
<flow>
  <case name="invite-collaborator">
    <description>Invita collaboratore a un repo GitHub</description>
    <action>
      <https>
        <url>https://api.github.com/repos/{{owner}}/{{repo}}/collaborators/{{username}}</url>
        <method>PUT</method>
        <headers>
          <header name="Authorization">Bearer {{ token }}</header>
          <header name="Accept">application/vnd.github+json</header>
          <header name="Content-Type">application/json</header>
        </headers>
        <payload>{"permission": "push"}</payload>
      </https>
    </action>
  </case>
</flow>
"""
        self.load_flow_config_from_string(aaa,'github')  # tua directory XML

    def load_flow_config_from_string(self, xml_string: str, module_name: str = "default", **constants):
        """Carica job da una stringa XML Jinja2 renderizzata e popola solo self.cases."""
        try:
            root = ET.fromstring(xml_string)
            cases_dict = {}

            for case_elem in root.findall('case'):
                case_name = case_elem.attrib.get('name', 'unknown')
                description = case_elem.findtext('description', '')
                action_elem = case_elem.find('action')

                if action_elem is None or len(action_elem) == 0:
                    continue

                action_type_elem = list(action_elem)[0]
                action_type = action_type_elem.tag.lower()

                job = {
                    'name': case_name,
                    'description': description,
                    'type': action_type,
                    'location': '',
                    'method': '',
                    'headers': {},
                    'payload': {}
                }

                match action_type:
                    case 'https':
                        job['location'] = action_type_elem.findtext('url', '')
                        job['method'] = action_type_elem.findtext('method', 'GET')

                        for h in action_type_elem.findall('./headers/header'):
                            name = h.attrib.get('name')
                            value = h.text
                            if name and value:
                                job['headers'][name] = value

                        payload_text = action_type_elem.findtext('payload')
                        if payload_text:
                            try:
                                job['payload'] = json.loads(payload_text)
                            except json.JSONDecodeError:
                                job['payload'] = {}

                    case 'shell':
                        job['location'] = action_type_elem.findtext('url', '')
                        job['method'] = 'shell'

                    case _:
                        print(f"⚠️ Tipo azione non supportato: {action_type}")
                        continue

                cases_dict[case_name] = job

            self.cases[module_name] = cases_dict

        except Exception as e:
            print(f"❌ Errore nel parsing XML: {e}")
        
    '''async def run_job_by_name(self, job_name: str):
        for job in self.scheduled_jobs:
            if job.get("name") == job_name:
                return await self.actuate(**job)
        raise ValueError(f"Job '{job_name}' non trovato.")'''
    
    async def actuate(self, **variables):
        name = variables.get('case', '')
        variables = variables | self.config  # Unisce le variabili passate con la configurazione
        
        job = language.get_safe(self.cases, name)
        print(f"▶️ Eseguo job: {name} con variabili: {variables}")
        
        action_type = job.get("type", "")

        match action_type:
            case "https":
                return await self._handle_https(job)
            case "shell":
                return await self._handle_shell(job)
            case _:
                raise NotImplementedError(f"Azione non supportata: {action_type}")

    async def _handle_https(self, job):
        variables = self.config.copy()
        variables.update(job)  # puoi aggiungere altre variabili se necessario

        # Renderizza location (URL)
        if job.get("location"):
            job["location"] = Template(job["location"]).render(variables)
        # Renderizza payload
        if job.get("payload"):
            payload_str = json.dumps(job["payload"])
            rendered_payload = Template(payload_str).render(variables)
            job["payload"] = json.loads(rendered_payload)
        # Renderizza headers
        if job.get("headers"):
            rendered_headers = {}
            for k, v in job["headers"].items():
                rendered_headers[k] = Template(str(v)).render(variables)
            job["headers"] = rendered_headers

        headers = job.get("headers", {}).copy()
        headers.setdefault("Authorization", f"{self.authorization} {self.token}")
        headers.setdefault("Accept", self.accept)
        headers.setdefault("Content-Type", "application/json")

        method = job.get("method", "GET")
        payload = job.get("payload", {})
        url = job.get("location")

        if not url.startswith("http"):
            url = f"{self.api_url.rstrip('/')}/{url.lstrip('/')}"

        return await backend(method, url, headers, payload)

    async def _handle_shell(self, job):
        command = job.get("location", "")
        print(f"▶️ Shell: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
'''import sys

if sys.platform == 'emscripten':
    import pyodide
    import json

    async def backend(method,url,headers,payload):
        match method:
            case 'GET':
                response = await pyodide.http.pyfetch(url, method=method, headers=headers)
            case _:
                if type(payload) == dict:
                    payload = json.dumps(payload)
                else:
                    payload = json.dumps({})
                response = await pyodide.http.pyfetch(url, method=method, headers=headers,body=payload)
        if response.status in [200, 201]:
            data = await response.json()
            print(data)
            return {"state": True, "result": data}
        else:
            return {"state": False, "result":[],"remark": f"Request failed with status {response.status}"}
                
else:
    import aiohttp
    import json

    #@flow.asynchronous
    async def backend(method,url,headers,payload):
        async with aiohttp.ClientSession() as session:
            async with session.request(method=method, url=url, headers=headers, json=payload) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    
                    return {"state": True, "result": data}
                else:
                    return {"state": False, "remark": f"Request failed with status {response.status}"}

class adapter():
    
    def __init__(self, **constants):
        self.config = constants['config']
        self.api_url = self.config['url']
        self.token = self.config['token']
        self.authorization = self.config['authorization'] if 'authorization' in self.config else 'token '
        self.accept = self.config['accept'] if 'accept' in self.config else 'application/vnd.github+json'

    @flow.asynchronous(outputs='transaction')
    async def load(self, *services, **constants):
        return await self.actuate(**constants | {'method': 'PUT'})

    async def actuate(self, **constants):
        print('request:',constants)
        headers = {
            "Authorization": f"{self.authorization} {self.token}",
            "Accept": self.accept,
        }
        location = constants.get('location','').replace('//','/')
        method = constants.get('method','')
        payload = constants.get('payload',{})
        url = f"{self.api_url}/{location}"

        #if payload and method == 'GET':
        #    url += '?' + urlencode(payload)
        
        ok = await backend(method,url,headers,payload)
        print('request:',constants,'output:',ok)
        return ok  
    
    @flow.asynchronous(outputs='transaction')
    async def activate(self,*services,**constants):
        return await self.actuate(**constants|{'method':'PUT'})

    @flow.asynchronous(outputs='transaction')
    async def deactivate(self,*services,**constants):
        pass

    @flow.asynchronous(outputs='transaction')
    async def calibrate(self,*services,**constants):
        pass

    @flow.asynchronous(outputs='transaction')
    async def status(self,*services,**constants):
        pass

    @flow.asynchronous(outputs='transaction')
    async def reset(self,*services,**constants):
        pass'''