# Import
import sys
import os
import asyncio

async def main():
    if sys.platform == 'emscripten':
        run = await language.resource(language, path="framework/service/run.py", )
        #loader = await language.load_module(language, path="framework.service.loader", )
    else:
        cwd = os.getcwd()
        sys.path.insert(1, cwd+'/src')
        import framework.service.language as language
        
        try:
            lang = await language.resource(path="framework/service/language.py")
        except Exception as e:
            print("Errore durante il caricamento del modulo language:", e)
            
        #language.di['module_cache']['language'] = language
        language.di['module_cache']['language'] = lang
        #print(dir(lang))
        #loader = await language.load_module(language, path="framework.service.loader", area="framework", service='service', adapter='loader')
        #await loader.bootstrap()
        try:
            run = await lang.resource(path="framework/service/run.py")
        except Exception as e:
            language.di['module_cache']['language'] = language
            run = await language.resource(path="framework/service/run.py")
            
        
    
    return run
if __name__ == "__main__":
    run = asyncio.run(main())
    run.application(args=sys.argv)
    