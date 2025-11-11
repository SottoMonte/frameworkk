import asyncio
from typing import List, Dict, Any, Callable
import re
import traceback

imports = {}

class executor:
    def __init__(self, **constants):
        # actuator
        self.sessions: Dict[str, Any] = {}
        self.providers = constants.get('providers', [])
        #print('EXE-',self.providers)
        #asyncio.create_task(self.action(case="github.invite-collaborator"))
    
    @language.asynchronous(managers=('messenger',))
    async def action2(self, messenger, **constants):
        await asyncio.sleep(5)
        #print('EXE2-',self.providers)
        tasks = [x.load() for x in self.providers]
        
        #print(tasks)
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        #await self.all_completed(tasks=tasks)
    
    @language.asynchronous(managers=('messenger',))
    async def action(self, messenger, **constants):
        #await asyncio.sleep(5)

        await self.providers[-1].actuate(**constants)
        '''await self.providers[-1].actuate(case_name,owner="SottoMonte",
        repo="framework",
        username= "SottoMonte",)'''

        

    '''@language.asynchronous(managers=('messenger',))
    async def act(self, messenger, **constants) -> Dict[str, Any]:
        """Esegue un'azione specifica caricando dinamicamente il modulo corrispondente."""
        action = constants.get('action', '')
        await messenger.post(domain='debug',message=f"🔄 Caricamento dell'azione: {action}")
        
        module = await language.load_module(
                language,
                path=f'application.action.{action}',
                area='application',
                service='action',
                adapter=action
        )
        act = getattr(module, action)
        result = await act(**constants)

        await messenger.post(domain='debug',message=f"✅ Azione '{action}' eseguita con successo.")
        return {"state": True, "result": result, "error": None}'''
    @language.asynchronous(managers=('messenger',))
    async def act2(self, messenger, **constants) -> Dict[str, Any]:
        """Esegue un'azione specifica caricando dinamicamente il modulo corrispondente."""
        action = constants.get('action', '')
        await messenger.post(domain='debug', message=f"🔄 Caricamento dell'azione: {action}")

        # Gestione action tipo 'create' o 'create.note'
        parts = action.split('.')
        module_path = f"application.action.{parts[0]}"
        adapter = parts[0]
        func_name = parts[1] if len(parts) > 1 else parts[0]

        module = await language.load_module(
            language,
            path=module_path,
            area='application',
            service='action',
            adapter=adapter
        )
        act_func = getattr(module, func_name)
        result = await act_func(**constants)

        await messenger.post(domain='debug', message=f"✅ Azione '{action}' eseguita con successo.")
        return {"state": True, "result": result, "error": None}

    @language.asynchronous(managers=('messenger',))
    async def act(self, messenger, **constants) -> Dict[str, Any]:
        """
        Esegue una o più azioni (separate da '|') caricando dinamicamente i moduli corrispondenti.
        Supporta sia chiamate con parametri (es: create.note(param=1)) sia solo nome funzione (es: create.note).
        """
        value = constants.get('action', '') or constants.get('action', '')
        functions = value.split('|')
        lista = []

        for func in functions:
            func = func.strip()
            result = {}
            match = re.match(r"(\w+(?:\.\w+)*)(?:\((.*)\))?", func)
            if not match:
                continue
            key = match.group(1)
            params_str = match.group(2)
            if params_str:
                params = language.extract_params(f"{key}({params_str})")
            else:
                params = constants
            result[key] = params
            lista.append(result)

        results = []
        for n in lista:
            for name in n:
                await messenger.post(domain='debug', message=f"🔄 Caricamento dell'azione: {name}")
                parts = name.split('.')
                module_path = f"application.action.{parts[0]}"
                adapter = parts[0]
                func_name = parts[1] if len(parts) > 1 else parts[0]
                module = await language.load_module(
                    language,
                    path=module_path,
                    area='application',
                    service='action',
                    adapter=adapter
                )
                act_func = getattr(module, func_name)
                res = await act_func(**n[name])
                results.append({name: res})
                await messenger.post(domain='debug', message=f"✅ Azione '{name}' eseguita con successo.")

        return {"state": True, "result": results, "error": None}

    @language.asynchronous(managers=('messenger',))
    async def first_completed(self, messenger, **constants):
        """Attende il primo task completato e restituisce il suo risultato."""
        operations = constants.get('operations', [])
        await messenger.post(domain='debug',message="⏳ Attesa della prima operazione completata...")

        try:
            while operations:
                finished, unfinished = await asyncio.wait(operations, return_when=asyncio.FIRST_COMPLETED)

                for operation in finished:
                    try:
                        transaction = operation.result()
                        print(transaction,'<------------------')
                        if transaction:
                            print(f"Transazione completata: {type(transaction)}")
                            if 'success' in constants:
                                transaction = await constants['success'](transaction=transaction,profile=operation.get_name())
                            await messenger.post(domain='debug',message=f"✅ Transazione completata: {str(transaction)}")
                            for task in unfinished:
                                task.cancel()
                            transaction['parameters'] = operation.parameters
                            return transaction
                    except Exception as e:
                        await messenger.post(domain='debug',message=f"❌ Errore nell'operazione: {e}")

                operations = unfinished

            error_msg = "⚠️ Nessuna transazione valida completata"
            await messenger.post(domain='debug',message=error_msg)
            return {"state": False, "result": None, "error": error_msg}

        except Exception as e:
            error_msg = f"❌ Errore in first_completed: {str(e)}"
            await messenger.post(domain='debug',message=error_msg)
            return {"state": False, "result": None, "error": error_msg}

    @language.asynchronous(managers=('messenger',))
    async def all_completed(self, messenger, **constants) -> Dict[str, Any]:
        """Esegue tutti i task in parallelo e attende il completamento di tutti."""
        '''tasks = constants.get('tasks', [])
        
        try:
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            #await messenger.post(domain='debug',message="🚀 Avvio esecuzione parallela di tutte le operazioni...")
            #await messenger.post(domain='debug',message="✅ Tutte le operazioni completate.")
            return {"state": True, "result": results, "error": None}

        except Exception as e:
            error_msg = f"❌ Errore in all_completed: {str(e)}"
            #await messenger.post(domain='debug',message=error_msg)
            return {"state": False, "result": None, "error": error_msg}'''
        tasks: List[asyncio.Future] = constants.get('tasks', [])
    
        # Lista per raccogliere i dettagli degli errori da ogni task
        detailed_errors = []
        
        try:
            # return_exceptions=True: le eccezioni sono restituite come risultati
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 1. Analisi dei Risultati Dettagliata
            for result in results:
                if isinstance(result, Exception):
                    # 🔥 STAMPA IMMEDIATA DEL TRACEBACK COMPLETO
                    print(f"--- ❌ ERRORE DETTAGLIATO TASK ---")
                    
                    # Questa funzione stampa il traceback completo sul tuo log/console
                    traceback.print_exception(type(result), result, result.__traceback__)
                    
                    print("---------------------------------------")
                    # Un task è fallito. Registra il traceback completo.
                    
                    # Ottieni il traceback completo (come stringa)
                    error_trace = traceback.format_exception(type(result), result, result.__traceback__)
                    full_error_log = "".join(error_trace)
                    
                    # Aggiungi il dettaglio all'elenco degli errori
                    detailed_errors.append(full_error_log)

                    # Opzionale: invia il log completo del singolo errore al messenger (disattivato per default)
                    # await messenger.post(domain='error', message=f"Task fallito: {full_error_log}")
                else:
                    # Il task è stato completato con successo
                    detailed_errors.append(None) # Usa None se il task ha avuto successo
            
            # Se ci sono errori dettagliati, il risultato complessivo è un fallimento logico
            if any(err is not None for err in detailed_errors):
                error_summary = f"❌ Completamento parallelo con {sum(1 for err in detailed_errors if err is not None)} errori rilevati. Dettagli in 'result'."
                # Opzionale: logga un riepilogo
                # await messenger.post(domain='error', message=error_summary)
                
                return {"state": False, "result": results, "error": error_summary}
            
            # Se non ci sono eccezioni in 'results'
            # await messenger.post(domain='debug', message="✅ Tutte le operazioni completate con successo.")
            return {"state": True, "result": results, "error": None}

        except Exception as e:
            # Questo blocco cattura solo gli errori che si verificano DURANTE asyncio.gather stesso
            error_msg = f"❌ Errore critico di sistema in all_completed (non un errore di task): {str(e)}"
            # Opzionale: logga l'errore critico
            # await messenger.post(domain='critical', message=error_msg)
            
            # Restituisce il traceback per l'errore critico di sistema
            full_traceback = "".join(traceback.format_exc())
            return {"state": False, "result": full_traceback, "error": error_msg}

    @language.asynchronous(managers=('messenger',))
    async def chain_completed(self, messenger, **constants) -> Dict[str, Any]:
        """Esegue i task in sequenza, aspettando il completamento di ciascuno prima di passare al successivo."""
        tasks = constants.get('tasks', [])
        results = []

        await messenger.post(domain='debug',message="🔄 Avvio esecuzione sequenziale delle operazioni...")

        try:
            for task in tasks:
                try:
                    result = await task(**constants)
                    results.append(result)
                    await messenger.post(domain='debug', message=f"✅ Task completato: {result}")
                except Exception as e:
                    await messenger.post(domain='debug', message=f"❌ Errore nel task {task}: {e}")

            return {"state": True, "result": results, "error": None}

        except Exception as e:
            error_msg = f"❌ Errore in chain_completed: {str(e)}"
            await messenger.post(domain='debug', message=error_msg)
            return {"state": False, "result": None, "error": error_msg}

    @language.asynchronous(managers=('messenger',))
    async def together_completed(self, messenger, **constants) -> Dict[str, Any]:
        """Esegue tutti i task contemporaneamente senza attendere il completamento di tutti."""
        tasks = constants.get('tasks', [])

        await messenger.post(domain='debug', message="🚀 Avvio esecuzione simultanea delle operazioni...")

        try:
            for task in tasks:
                asyncio.create_task(task)

            await messenger.post(domain='debug', message="✅ Tutti i task sono stati avviati in background.")
            return {"state": True, "result": "Tasks avviati in background", "error": None}

        except Exception as e:
            error_msg = f"❌ Errore in together_completed: {str(e)}"
            await messenger.post(domain='debug', message=error_msg)
            return {"state": False, "result": None, "error": error_msg}