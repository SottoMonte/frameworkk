import sys

imports = {
    'user': 'framework/scheme/user.json',
    'scheme_session':'framework/scheme/session.json'
}
    
if sys.platform == 'emscripten':
    import js
    from js import supabase
    import pyodide


    async def backend_registration(supabase,**data):
        data_js = pyodide.ffi.to_js(data)
        print(data_js)
        user = await supabase.auth.signUp(data_js)
        user_dict = user.to_py()
        print(user_dict.get('error',None))
        print("SERVIZIO DI REGISTRAZIONE2")
        return user_dict.get('session',{}).get('access_token',None)
    
    async def backend_login(supabase,**data):
        print("SERVIZIO DI LOGIN2",data)
        data_js = pyodide.ffi.to_js(data)
        user = await supabase.auth.signInWithPassword(data_js)
        user_dict = user.to_py()
        print(user_dict,'login')
        return user_dict.get('data',{})
else:
    import supabase

    async def backend_registration(supabase,**data):
        user = supabase.auth.sign_up(data)

        return user.get('session',{}).get('access_token',None)
    
    async def backend_login(supabase,**data):
        """
        Effettua il login e restituisce una sessione utente semplificata.
        
        :param supabase: istanza del client Supabase
        :param credentials: dict con 'email' e 'password'
        :return: dict con dati sessione ordinati
        """
        user_response = supabase.auth.sign_in_with_password(data)
        auth_data = user_response.dict()

        raw_user = auth_data.get("user", {})
        raw_session = auth_data.get("session", {})

        # Struttura ordinata
        session = {
            "user": {
                "id": raw_user.get("id"),
                "email": raw_user.get("email"),
                "email_verified": raw_user.get("user_metadata", {}).get("email_verified"),
                "provider": raw_user.get("app_metadata", {}).get("provider", "email"),
                "created_at": raw_user.get("created_at").isoformat() if raw_user.get("created_at") else None,
                "last_sign_in_at": raw_user.get("last_sign_in_at").isoformat() if raw_user.get("last_sign_in_at") else None,
                "is_anonymous": raw_user.get("is_anonymous", False),
                "role": raw_user.get("role", "authenticated"),
            },
            "tokens": {
                "access_token": raw_session.get("access_token"),
                "refresh_token": raw_session.get("refresh_token"),
                "expires_at": raw_session.get("expires_at"),
                "token_type": raw_session.get("token_type", "bearer")
            },
            "metadata": raw_user.get("user_metadata", {})
            #"provider": raw_session.get("user", {}).get("app_metadata", {}).get("provider", "email"),
            #"session_id": raw_session.get("session_id", None),
            #"auth_time": datetime.utcnow().isoformat(),
        }

        return session

class adapter:
    def __init__(self, **constants):
        self.config = constants['config']
        self.url = self.config['url']
        self.key = self.config['key']
        
        if sys.platform == 'emscripten':
            print("Emscripten platform detected",dir(supabase))
            self.supabase =  supabase.createClient(self.url, self.key)
            print("Supabase client created",dir(self.supabase),dir(self.supabase.auth))
        else:
            self.supabase = supabase.create_client(self.url, self.key)
            pass
            
    @language.asynchronous(outputs='transaction',managers=('messenger',))
    async def whoami(self, messenger, **data):
        print("Autenticazione con Supabase",user.user)
        result = await self.supabase.auth.getUser()
        result_dict = result.to_py()
        print(result_dict)
        if result_dict.get('error',None) != None:
            state = False
        else:
            state = True
        return {'state':state,'result':[result_dict.get('data',{}).get('user',{})]}
    
        

    async def registration(self,**data):
        try:
            return await backend_registration(self.supabase,**data)
        except Exception as e:
            print(f"Errore di autenticazione: {e}")

    async def logout(self,**data):
        try:
            print("Logout")
            await self.supabase.auth.signOut()
        except Exception as e:
            print(f"Errore di autenticazione: {e}")

    async def authenticate(self, **data):
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        #if not email or not password:
        #    await messenger.post(domain="error", message="Email e password sono obbligatori.")
        #    return None

        try:
            profile = self.config['profile']
            result = await backend_login(self.supabase, **data)
            result = await language.normalize({'identifier':data['identifier'],'ip':data['ip'],'user':result['user'],'tokens':{profile:result['tokens']}},scheme_session)
            return result
        except Exception as e:
            print(f"Errore di autenticazione: {e}")
            #await messenger.post(domain="error", message=f"Errore di autenticazione: {e}")
            return None
