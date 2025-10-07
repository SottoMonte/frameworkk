try:
    from js import WebSocket
    import json
    JS_ENV = True
except ImportError:
    import asyncio, websockets, json
    JS_ENV = False

import asyncio, fnmatch

class adapter:
    def __init__(self, **constants):
        self.config = constants.get("config", {})
        self.url = self.config.get("url", "wss://localhost:8000/messenger")
        self.socket = None
        self.history = dict()
        self.listeners = dict()

        if JS_ENV:
            self.connect_js()
        else:
            asyncio.get_event_loop().create_task(self.connect_py())

    def connect_js(self):
        try:
            self.socket = WebSocket.new(self.url)
            self.socket.onopen = lambda e=None: print(f"🟢 JS WebSocket opened: {self.url}")
            self.socket.onclose = lambda e=None: print("🔴 WebSocket closed")
            self.socket.onerror = lambda e=None: print("⚠️ WebSocket error")
            self.socket.onmessage = self.handle_message
        except Exception as e:
            print(f"❌ JS WebSocket init failed: {e}")

    async def connect_py(self):
        await asyncio.sleep(2)
        try:
            async with websockets.connect(self.url) as ws:
                self.socket = ws
                print(f"🟢 PY WebSocket connected: {self.url}")
                async for msg in ws:
                    self.handle_message(msg)
        except Exception as e:
            print(f"❌ PY WebSocket error: {e}")

    def handle_message(self, payload):
        payload = payload.data
        
        payload = json.loads(payload) if isinstance(payload, str) else payload
        domain = payload.get("domain", [])
        message = payload.get("message", [])

        ok = []
        for x in self.listeners.keys():
            
            matching_domains = language.wildcard_match(domain, x)
            if len(matching_domains) == 1:
                ok.append(x)

        print(ok,self.listeners)
        
        for x in ok:
            listener = self.listeners.get(x)
            listener.put_nowait(payload)
            '''for listener in listeners:
                #asyncio.create_task(messenger.post(domain='*',message='ok'))

                listener.put_nowait(payload)'''

        #for q in self.listeners:
        #    q.put_nowait(payload)

        '''for pattern, queues in self.listeners.items():
            if "*" in pattern and fnmatch.fnmatch(domain, pattern):
                for q in queues:
                    q.put_nowait(payload)'''

    def send(self, **data):
        if not self.socket: return
        msg = json.dumps(data)
        if JS_ENV:
            if self.socket.readyState == WebSocket.OPEN:
                self.socket.send(msg)
        else:
            asyncio.create_task(self.socket.send(msg))

    async def post(self, **data):
        if data.get("message"):
            self.send(**data)

    async def read(self, **data):
        domain = data.get("domain", "info")
        if domain not in self.listeners:
            q = asyncio.Queue()
            self.listeners[domain] = q
            return await q.get()
        else:
            q = self.listeners[domain]
            return await q.get()

    def close(self):
        if JS_ENV and self.socket:
            self.socket.close()
        elif self.socket:
            asyncio.create_task(self.socket.close())