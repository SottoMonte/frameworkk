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
        import framework.service.flow as flow
        import framework.manager.loader as loader
        
        loader_instance = loader.loader()

        ok = await loader_instance.resource(path="framework/service/language.py")
        print(dir(ok.get('data')))
        print(ok.get('data').__dict__)

        # Seed the DI cache with the imported module so dynamically loaded
        # modules that ask for `language` during their own import don't see None.
        return await flow.pipe(
            flow.step(loader_instance.resource, path="framework/service/language.py"),
            #flow.step(lambda lang: language.container.module_cache()['framework/service/language.py'] = lang),
            flow.step(flow.catch,
                flow.step('@.outputs.-1', path="framework/service/run.py"),
                flow.step(loader_instance.resource, path="framework/service/run.py"),
            )
        )

if __name__ == "__main__":
    run = asyncio.run(main())
    print(run)
    #run.application(args=sys.argv)
    