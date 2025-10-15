# Import
import sys
import os

if sys.platform == 'emscripten':
    # WebAssembly/browser environment - not supported in this setup
    raise NotImplementedError("WebAssembly environment not supported in this configuration")
else:
    cwd = os.getcwd()
    sys.path.insert(1, cwd+'/src')
    import framework.service.language as language
    
    # Use resource method instead of load_main
    import asyncio
    async def get_run_module():
        await language.resource(language, path="framework/service/language.py", adapter="language")
        return await language.resource(language, path="framework/service/run.py", adapter="run")
    
    run = asyncio.run(get_run_module())

#modulo = ['run','language']

if __name__ == "__main__":
    run.application(args=sys.argv)
    