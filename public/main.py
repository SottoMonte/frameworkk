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
        import framework.service.flow as flow
        import framework.manager.loader as loader
        
        loader_instance = loader.loader()
        load_filtered = await loader_instance.resource(path="framework/service/load.py")
        print(load_filtered)
        load_filtered = load_filtered.get('data')
        print(dir(load_filtered))
        '''ok = await loader_instance.resource(path="framework/service/run.py")
        print(dir(ok.get('data')))
        print(ok.get('data').__dict__)'''

        # Seed the DI cache with the imported module so dynamically loaded
        # modules that ask for `language` during their own import don't see None.
        return await flow.pipe(
            flow.step(load_filtered.resource, path="framework/service/language.py"),
            #flow.step(lambda lang: language.container.module_cache()['framework/service/language.py'] = lang),
            flow.step(flow.catch,
                flow.step('@.outputs.-1.resource', path="framework/service/run.py"),
                flow.step(load_filtered.resource, path="framework/service/run.py"),
            )
        )

if __name__ == "__main__":
    # Load the run module
    result = asyncio.run(main())
    run_module = result.get('data') if isinstance(result, dict) and 'data' in result else result
    
    run_module.application(args=sys.argv)