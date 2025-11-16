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

        # Seed the DI cache with the imported module so dynamically loaded
        # modules that ask for `language` during their own import don't see None.

        try:
            lang = await language.resource(path="framework/service/language.py")
            language.di['module_cache']['framework/service/language.py'] = lang
            # If loading succeeded, replace cache entry with the filtered module
        except Exception as e:
            print(e)
            #run = await language.resource(path="framework/service/run.py")
            pass
        try:
            run = await lang.fetch(path="framework/service/run.py")
        except Exception as e:
            print(e)
            raise('ssss')
            run = await language.resource(path="framework/service/run.py")
            pass
    
    return run
if __name__ == "__main__":
    run = asyncio.run(main())
    run.application(args=sys.argv)
    