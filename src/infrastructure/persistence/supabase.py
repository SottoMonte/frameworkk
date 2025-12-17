import sys
import json
import os

# Determina l'ambiente di esecuzione (backend o frontend con Pyodide)
SUPABASE_ENV = os.environ.get('SUPABASE_ENV', 'BACKEND')

if SUPABASE_ENV == 'FRONTEND':
    try:
        import js
        from js import supabase
        import pyodide
    except ImportError:
        # Gestione di un errore, nel caso in cui le librerie non siano disponibili
        print("Warning: Pyodide environment specified but libraries not found.", file=sys.stderr)
        supabase = None
        pyodide = None
else:
    # Per l'ambiente backend
    try:
        from supabase import create_client, Client
    except ImportError:
        print("Error: Supabase Python library not found. Please install with `pip install supabase`", file=sys.stderr)
        create_client = None

# Aggiusta il percorso del modulo se necessario, come nel tuo codice originale
imports = {
    'flow': 'framework/service/flow.py',
}


class adapter:
    def __init__(self, **config):
        """Inizializza il client Supabase in base all'ambiente."""
        self.config = config.get('config', {})
        self.capabilities = {'speed': 'low', 'latency': 'high'}
        self.is_frontend = SUPABASE_ENV == 'FRONTEND'
        self.client = None
        self.js_client = None

        if self.is_frontend:
            if not supabase or not pyodide:
                raise RuntimeError("Pyodide environment dependencies not met.")
            
            # Inizializza il client JS
            js_code = f"""
            globalThis.supabaseClient = supabase.createClient("{self.config.get('url', '')}", "{self.config.get('key', '')}");
            console.log("✅ Supabase initialized for Pyodide!");
            """
            pyodide.code.run_js(js_code)
            self.js_client = js.globalThis.supabaseClient
        else:
            if not create_client:
                raise RuntimeError("Backend Supabase dependencies not met.")
            
            # Inizializza il client Python per il backend
            self.client: Client = create_client(self.config['url'], self.config['key'])
            print("✅ Supabase initialized for Backend!")

        self.set_token(self.config.get('token', ''),self.config.get('token', ''))

    def set_token(self, token,token2):
        """Imposta il token di autenticazione dell'utente."""
        self.token = token
        if self.is_frontend and self.js_client:
            self.js_client.auth.setSession({"access_token": token,'refresh_token':''})
        elif self.client:
            try:
                if token and token2:
                    self.client.auth.set_session(token, token2)
                else: 
                    # If we don't have tokens, maybe we don't set session?
                    # The hardcoded one was likely for testing.
                    pass 
            except Exception as e:
                print(f"Warning: Failed to set Supabase session: {e}")

    def _apply_filters_to_query(self, query, filters):
        """Applica dinamicamente i filtri alla query."""
        if not filters:
            return query
        
        for op, params in filters.items():
            if op == 'pagination':
                start = params.get('start', 1)
                end = params.get('end', 10)
                start_index, end_index = (start - 1) * end, start * end - 1
                query = query.range(start_index, end_index)
            elif op == 'in':
                for field, values in params.items():
                    query = query.in_(field, values)
            else: # Gestisce 'eq', 'neq', 'like', 'ilike'
                for field, value in params.items():
                    query = getattr(query, op)(field, value)
        return query

    async def query(self, **constants):
        """Esegue una query su Supabase in base all'ambiente."""
        payload = constants.get('payload', {})
        method = constants.get('method', '').upper()
        location = constants.get('location', '')
        filters = constants.get('filter', {})

        if not location:
            return {"state": False, "error": "Location not specified."}
        
        if self.is_frontend:
            return await self._query_frontend(method, location, payload, filters)
        else:
            return self._query_backend(method, location, payload, filters)

    async def _query_frontend(self, method, location, payload, filters):
        """Logica di query per Pyodide (frontend) usando JS."""
        
        # Semplificazione della gestione dei filtri per JS
        filter_code = ""
        if filters:
            for op, params in filters.items():
                if op == 'pagination':
                    start = params.get('start', 1)
                    end = params.get('end', 10)
                    start_index, end_index = (start - 1) * end, start * end - 1
                    filter_code += f".range({start_index}, {end_index})"
                elif op == 'in':
                    for field, values in params.items():
                        js_values = json.dumps(values)
                        filter_code += f".in('{field}', {js_values})"
                else:
                    for field, value in params.items():
                        js_value = json.dumps(value)
                        filter_code += f".{op}('{field}', {js_value})"

        js_code = f"""
        async function run_query() {{
            let query = globalThis.supabaseClient.from("{location}");
            let response;

            switch ("{method}") {{
                case "GET":
                    query = query.select("*"){filter_code};
                    response = await query;
                    break;
                case "POST":
                    response = await query.insert({json.dumps(payload)}){filter_code};
                    break;
                case "PUT":
                    // Per UPDATE, i filtri sono usati per "match"
                    response = await query.update({json.dumps(payload)});
                    
                    // Applica i filtri come match (necessario per l'API JS)
                    if (filters && filters.eq) {{
                        for (const [key, value] of Object.entries(filters.eq)) {{
                             query = query.eq(key, value);
                        }}
                    }}
                    response = await query;
                    break;
                case "DELETE":
                    // Per DELETE, i filtri sono usati per "match"
                    response = await query;

                    if (filters && filters.eq) {{
                        for (const [key, value] of Object.entries(filters.eq)) {{
                             query = query.eq(key, value);
                        }}
                    }}
                    response = await query.delete();
                    break;
                default:
                    return {{ state: false, error: "Invalid method" }};
            }}

            return response.error 
                ? {{ state: false, error: response.error.message, input: {{ method, payload, location }} }}
                : {{ state: true, result: response.data, input: {{ method, payload, location }} }};
        }}
        run_query();
        """
        
        try:
            result = await pyodide.code.run_js(js_code)
            return result.to_py()
        except Exception as e:
            return {"state": False, "error": f"JS execution error: {str(e)}"}

    def _query_backend(self, method, location, payload, filters):
        """Logica di query per il backend usando la libreria Python."""
        try:
            query = self.client.table(location)
            response = None
            
            if method == 'GET':
                query = self._apply_filters_to_query(query.select('*'), filters)
                response = query.execute()

            elif method == 'PUT':
                # Per PUT e DELETE, i filtri 'eq' vengono usati per la clausola `match`
                match_filters = filters.get('eq', {})
                if not match_filters:
                    return {"state": False, "error": "Match filters required for update."}
                
                response = query.update(payload).match(match_filters).execute()

            elif method == 'POST':
                response = query.insert(payload).execute()

            elif method == 'DELETE':
                match_filters = filters.get('eq', {})
                if not match_filters:
                    return {"state": False, "error": "Match filters required for delete."}
                
                response = query.delete().match(match_filters).execute()
            
            else:
                return {"state": False, "error": "Invalid method"}
            
            if response.data is None:
                # La libreria Python di Supabase non solleva eccezioni per errori HTTP
                return {"state": False, "error": response.data, "result": None}

            return {"state": True, "result": response.data}
        except Exception as e:
            return {"state": False, "error": str(e)}

    # Metodi di alias per le operazioni CRUD
    @flow.asynchronous(outputs='transaction')
    async def create(self, **constants):
        return await self.query(**constants | {'method': 'POST'})

    @flow.asynchronous(outputs='transaction')
    async def delete(self, **constants):
        return await self.query(**constants | {'method': 'DELETE'})

    @flow.asynchronous(outputs='transaction')
    async def read(self, **constants):
        return await self.query(**constants | {'method': 'GET'})

    @flow.asynchronous(outputs='transaction')
    async def update(self, **constants):
        return await self.query(**constants | {'method': 'PUT'})