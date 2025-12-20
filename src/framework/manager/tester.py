import unittest
import os
import types
import sys
import io
import asyncio
import inspect
from framework.service.inspector import framework_log

class tester():

    def __init__(self,**constants):
        self.sessions = dict()
        self.providers = constants['providers']

    def discover_tests(self):
        # Pattern personalizzato per i test
        test_dir = './src'
        test_suite = unittest.TestSuite()
        
        # Scorri tutte le sottocartelle e i file
        for root, dirs, files in os.walk(test_dir):
            for file in files:
                if file.endswith('.test.py'):
                    # Crea il nome del modulo di test per ciascun file trovato
                    module_name = os.path.splitext(file)[0]
                    module_path = os.path.join(root, file)
                    
                    # Importa il modulo di test dinamicamente
                    try:
                        module = language.get_module_os(module_path,language)
                        # Aggiungi i test dal modulo
                        test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(module))
                    except ImportError as e:
                        framework_log("ERROR", f"Errore nell'importazione del modulo: {module_path}, {e}", emoji="❌")
        return test_suite
    
    async def unittest2(self, code: str, **constants):
        def get_test_methods( suite):
            test_methods = []
            for test in suite:
                if hasattr(test, 'test_'):  # Verifica se è un caso di test
                    method_name = test._testMethodName
                    method = getattr(test, method_name, None)
                    if asyncio.iscoroutinefunction(method):  # Controlla se è una coroutine
                        test_methods.append((method_name, "async"))
                    else:
                        test_methods.append((method_name, "sync"))
            return test_methods
        #code = code.replace('unittest.IsolatedAsyncioTestCase','unittest.TestCase')
        # Crea un modulo Python temporaneo
        module_name = "__dynamic_test_module__"
        test_module = types.ModuleType(module_name)

        # Inietta le costanti nel contesto del modulo
        for key, value in constants.items():
            setattr(test_module, key, value)

        # Esegue il codice della stringa nel contesto del modulo
        exec(code, test_module.__dict__)

        # Registra il modulo temporaneamente in sys.modules
        sys.modules[module_name] = test_module

        # Trova le classi di test definite nel modulo
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_module)

        # Esegue i test e cattura l'output
        stream = io.StringIO()
        #runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        #result = runner.run(suite)
        results = unittest.TestResult()
        for test in suite:
            #test.run(results)
            #print(get_test_methods(suite))
            lol = getattr(test, '_tests', [])
            for case in lol:
                print(case())
            #print(await test())

        # Risultati
        framework_log("INFO", "Risultati Test Unittest2", emoji="🧪", 
                      total=results.testsRun, 
                      errors=len(results.errors), 
                      failures=len(results.failures))

        # Rimuove il modulo temporaneo
        del sys.modules[module_name]

        # Stampa o restituisce i risultati
        print(stream.getvalue())
        #return result
        if results.failures or results.errors:
            return (False,results.testsRun,results.errors,results.failures)
        else:
            return (True,results.testsRun,results.errors,results.failures)


    async def unittest(self, code: str, **constants):
        '''module = types.ModuleType("dynamic_module")
        module.__dict__.update(constants)
        module.__dict__.update({
            'unittest': unittest,
            'asyncio': asyncio,
        })

        exec(code, module.__dict__)'''

        module = await language.load_module(language,code=code)

        test_classes = [
            cls for cls in module.__dict__.values()
            if inspect.isclass(cls) and issubclass(cls, unittest.TestCase)
        ]

        results = {
            "testsRun": 0,
            "errors": [],
            "failures": [],
            "successes": [],
            "setup":None,
            "teardown":None,
        }

        for TestClass in test_classes:
            test_methods = [
                name for name, func in inspect.getmembers(TestClass, predicate=inspect.isfunction)
                if name.startswith("test_")
            ]

            for method_name in test_methods:
                test_instance = TestClass(method_name)
                results["testsRun"] += 1
                test_id = f"{TestClass.__name__}.{method_name}"

                async def run_test():
                    if hasattr(test_instance, "setUp"):
                        results["setup"] = test_instance.setUp()
                    if hasattr(test_instance, "asyncSetUp"):
                        ok = await test_instance.asyncSetUp()
                        results["teardown"] = ok
                        

                    method = getattr(test_instance, method_name)
                    if inspect.iscoroutinefunction(method):
                        await method()
                    else:
                        method()

                    if hasattr(test_instance, "tearDown"):
                        test_instance.tearDown()
                    if hasattr(test_instance, "asyncTearDown"):
                        await test_instance.asyncTearDown()

                try:
                    await run_test()
                    results["successes"].append(test_id)
                except AssertionError as e:
                    results["failures"].append((test_id, str(e)))
                except Exception as e:
                    results["errors"].append((test_id, str(e)))

        # Determina lo stato complessivo
        if results["failures"] or results["errors"]:
            results["state"] = False
        else:
            results["state"] = True

        return results



    def run(self,**constants):
        framework_log("INFO", "Avvio esecuzione suite di test...", emoji="🧪")
        suite = self.discover_tests()
        runner = unittest.TextTestRunner()
        runner.run(suite)