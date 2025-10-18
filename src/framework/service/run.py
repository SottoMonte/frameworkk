import asyncio
import sys

#loader = language.load_main(language,area="framework",service='service',adapter='loader')

imports = {
    'flow': 'framework/service/flow.py',
    'loader': 'framework/service/loader.py'
}

import os
import requests
import hashlib

def get_remote_file_sha(url):
    response = requests.get(url)
    if response.status_code == 200:
        return hashlib.sha256(response.content).hexdigest(), response.content
    return None, None

def get_local_file_sha(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def sync_directory_recursive(api_url, local_dir):
    response = requests.get(api_url)
    if response.status_code != 200:
        raise Exception("GitHub API error:", response.json())
    
    files = response.json()

    for item in files:
        if item['type'] == 'dir':
            # Ricorsione per le sottocartelle
            sub_local_dir = os.path.join(local_dir, item['name'])
            sync_directory_recursive(item['url'], sub_local_dir)
        elif item['type'] == 'file':
            file_path = os.path.join(local_dir, item['name'])
            remote_sha, remote_content = get_remote_file_sha(item['download_url'])
            local_sha = get_local_file_sha(file_path)

            if local_sha != remote_sha:
                print(f"[Updating] {file_path}")
                os.makedirs(local_dir, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(remote_content)
            else:
                print(f"[OK] {file_path} is up to date.")
        else:
            print(f"[Skipping] {item['type']}: {item['path']}")

def sync_github_repo(local_base_dir, github_user, repo, branch='main'):
    api_url = f"https://api.github.com/repos/{github_user}/{repo}/contents/src?ref={branch}"
    sync_directory_recursive(api_url, local_base_dir)


'''def test():
    import unittest
    async def discover_tests():
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
                    print(f"Importing test module: {module_path}")
                    # Importa il modulo di test dinamicamente
                    try:
                        module_path = module_path.replace('./src/','')
                        print(f"Module path: {module_path}")
                        #module = language.get_module_os(module_path,language)
                        module = await language.resource(language, path=module_path,adapter=module_name.replace('.test.py',''))
                        # Aggiungi i test dal modulo
                        test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(module))
                    except Exception as e:
                        print(f"Errore nell'importazione del modulo: {module_path}, {e}")
        return test_suite
    asyncio.run(loader.bootstrap())
    suite = asyncio.run(discover_tests())
    runner = unittest.TextTestRunner()
    runner.run(suite)'''

# =========================================================================
# 4. FUNZIONE 'TEST' MODIFICATA
# =========================================================================

def map_failed_tests(result) -> set[tuple[str, str]]:
    """
    Estrae il percorso del file e il nome completo del metodo di test fallito 
    (FAIL o ERROR).
    Ritorna un set di tuple: {(path_del_file, nome_metodo_completo), ...}
    """
    failed_set: set[tuple[str, str]] = set()

    # Combina Failures (F) e Errors (E)
    all_issues = result.failures + result.errors

    for test, _ in all_issues:
        # Il nome del test viene formattato come: test_method (file.py.TestClass)
        # Esempio: test_post (src/infrastructure/message/console.test.py.Testadapter)
        
        test_id: str = test.id()
        
        # Scomponiamo l'ID
        parts = test_id.split('.')
        # L'ultimo elemento è il nome del metodo (es. test_post)
        method_name = parts[-1]
        # L'elemento prima dell'ultimo contiene il file e la classe (es. src/.../console.test.py.Testadapter)
        
        # Rimuoviamo il nome della classe per isolare il percorso del file
        # Otteniamo il percorso del file (es. src/infrastructure/message/console.test.py)
        # La logica è complessa a causa della formattazione standard di unittest,
        # ma possiamo usare il nome del file fornito nel Traceback per la sicurezza.
        
        # Basandoci sul traceback, il formato è: test_metodo (percorso/file.test.py.TestClasse)
        # Usiamo il nome del file di test come chiave principale.
        
        # Estrarre il percorso del file (più semplice se conosciamo il formato)
        # Esempio: 'src/infrastructure/message/console.test.py'
        # Cerchiamo il primo elemento che inizia con 'src/'
        file_path_parts = [p for p in parts if 'src/' in p]
        if file_path_parts:
            # Rimuoviamo il nome della classe se presente
            file_path = file_path_parts[0].split('Test')[0].split('test.')[0] + '.test.py'
        else:
            # Fallback se la formattazione è inattesa
            continue
            
        failed_set.add((file_path, method_name))
        
    return failed_set

async def discover_and_run_tests():
    import unittest
    import json
    # Pattern personalizzato per i test
    test_dir = './src'
    test_suite = unittest.TestSuite()
    all_contract_hashes: dict[str, any] = {}
    
    # 1. FASE DI SCOPERTA E GENERAZIONE HASH
    for root, dirs, files in os.walk(test_dir):
        for file in files:
            if file.endswith('.test.py'):
                module_path_rel = os.path.join(root, file).replace('./','')
                main_path_rel = module_path_rel.replace('.test.py','.py')
                json_path = main_path_rel.replace('.py', '.contract.json')
                
                print(f"\n🔍 Generazione contratto per: {module_path_rel}")
                
                # --- Caricamento per l'Hashing ---
                try:
                    
                    hashes = await language.generate_and_validate_contract_json(main_path_rel)


                    all_contract_hashes |= hashes
                    
                    # --- SALVATAGGIO JSON (Simulato) ---
                    json_content = json.dumps(hashes, indent=4)
                    # Simula il salvataggio del file .contract.json
                    # await language.backend(path=json_path, content=json_content, mode='w')
                    print(f"✅ Contratto JSON salvato (Simulato) in: {json_path}")
                    
                except Exception as e:
                    print(f"❌ Errore critico nella generazione del contratto: {e}")
                    continue
                    
                # 2. FASE DI CARICAMENTO TEST (per l'esecuzione)
                try:
                    # Carica il modulo di test usando il framework per DI/Filtro
                    module_name = os.path.splitext(file)[0]
                    # language.resource caricherà e *filtrerà* il modulo usando il .contract.json appena creato
                    module = await language.resource(path=module_path_rel)
                    print(dir(module_path_rel))
                    # Aggiungi i test dal modulo filtrato
                    test_suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(module))
                except Exception as e:
                    print(f"Errore nell'importazione/filtro del modulo: {main_path_rel}, {e}")
    print("\n📋 Tutti i contratti generati:",all_contract_hashes)
    return all_contract_hashes,test_suite

def rimuovi_falliti_e_specchi(contratti_completi: dict, test_falliti_set: set) -> dict:
    """
    Filtra un dizionario di contratti (hash) rimuovendo:
    1. Gli hash delle funzioni di test fallite (es. 'test_post').
    2. Gli hash delle funzioni 'specchio' corrispondenti (es. 'post').

    Args:
        contratti_completi: Il dizionario dei contratti (es. all_contract_hashes).
        test_falliti_set: Un set contenente tuple (percorso_file, nome_test) dei test falliti.

    Returns:
        Un nuovo dizionario con gli hash rimossi.
    """
    risultato_filtrato = {}
    
    # 1. Identifica i nomi delle funzioni da rimuovere (test + specchio)
    nomi_da_rimuovere = set()
    for _, nome_test in test_falliti_set:
        nomi_da_rimuovere.add(nome_test)
        
        # Estrae la funzione 'specchio' rimuovendo il prefisso 'test_'
        if nome_test.startswith('test_'):
            nome_funzione_specchio = nome_test[len('test_'):]
            nomi_da_rimuovere.add(nome_funzione_specchio)
            
    # Esempio: nomi_da_rimuovere sarà {'test_post', 'post', 'test_asynchronous', 'asynchronous', ...}
    
    # 2. Itera sulla struttura dei contratti e applica il filtro
    for modulo_path, contenuto_modulo in contratti_completi.items():
        nuovo_contenuto_modulo = {}
        
        for container_name, funzioni_hash in contenuto_modulo.items():
            nuove_funzioni_hash = {}
            
            for nome_funzione, hash_valore in funzioni_hash.items():
                
                # Rimuoviamo la chiave se il suo nome è nel set nomi_da_rimuovere
                if nome_funzione in nomi_da_rimuovere:
                    continue
                
                # Altrimenti, conserva la funzione
                nuove_funzioni_hash[nome_funzione] = hash_valore
            
            # Aggiunge il container filtrato solo se non è vuoto
            if nuove_funzioni_hash:
                nuovo_contenuto_modulo[container_name] = nuove_funzioni_hash
        
        # Aggiunge il modulo filtrato solo se non è vuoto
        if nuovo_contenuto_modulo:
            risultato_filtrato[modulo_path] = nuovo_contenuto_modulo
            
    return risultato_filtrato

def estrai_test_da_suite(suite) -> set[tuple[str, str]]:
    from unittest.case import TestCase
    from unittest.suite import TestSuite
    """
    Attraversa ricorsivamente un oggetto unittest.suite.TestSuite annidato
    e restituisce un set di tuple (percorso_file_o_modulo, nome_metodo).
    
    Usa la logica standard di unittest per estrarre il nome del metodo e il modulo.
    """
    test_estratti = set()
    
    # La suite è iterabile, che sia una TestSuite o una lista di test
    for test in suite:
        if isinstance(test, TestSuite):
            # Caso 1: È una sottosuite. Chiamiamo ricorsivamente.
            test_estratti.update(estrai_test_da_suite(test))
            
        elif isinstance(test, TestCase):
            # Caso 2: È un TestCase effettivo (il nodo finale)
            
            # 1. Estrai il nome del metodo (es. 'test_synchronous')
            nome_metodo = getattr(test, '_testMethodName', 'unknown_method')
            
            # 2. Estrai il percorso del file / modulo
            nome_modulo = test.__class__.__module__
            percorso_test_pulito = nome_modulo
            
            # Tenta di trovare il percorso fisico del file sorgente
            try:
                modulo_obj = __import__(nome_modulo, fromlist=[''])
                if hasattr(modulo_obj, '__file__'):
                    # Ottiene il percorso assoluto e pulisce eventuali estensioni di byte-code
                    percorso_file_assoluto = modulo_obj.__file__
                    if percorso_file_assoluto.endswith(('.pyc', '.pyo')):
                        percorso_file_assoluto = percorso_file_assoluto[:-1]
                        
                    # Usa il percorso assoluto come identificatore del file
                    percorso_test_pulito = percorso_file_assoluto
                    
            except Exception:
                # In caso di errore (es. modulo non importabile o caricato dinamicamente)
                # manteniamo il nome del modulo come fallback.
                pass
                
            test_estratti.add((percorso_test_pulito, nome_metodo))

    return test_estratti

def test():
    """Funzione di avvio principale per la generazione del contratto e l'esecuzione dei test."""
    import unittest
    import asyncio
    
    # Assumiamo che 'loader' e 'language' siano disponibili globalmente o passati
    # Aggiungi le tue importazioni qui (os, asyncio, unittest, language, loader)
    
    # Esegui il bootstrap del framework (se necessario)
    asyncio.run(loader.bootstrap())

    # Scopri e genera i contratti, poi esegui i test
    all_contract_hashes, suite_test = asyncio.run(discover_and_run_tests())
    
    # Esegui la fase di scoperta, generazione del contratto ed esecuzione
    suite = suite_test
    runner = unittest.TextTestRunner()
    print("\n=====================================")
    print("        INIZIO ESECUZIONE TEST       ")
    print("=====================================")
    print(suite)
    result = runner.run(suite)
    #print(map_failed_tests(result))
    print(estrai_test_da_suite(suite))
    print(map_failed_tests(result))
    print(rimuovi_falliti_e_specchi(all_contract_hashes, map_failed_tests(result)))
    print("\n=====================================")
    print("        FINE ESECUZIONE TEST         ")
    print("=====================================")
        
APP_CONTEXT = {
    "APP_VERSION": "1.2.5",
    "USER_ID": "user_1234",
    "REQUEST_ID": "req_xyz987"
}

#@flow.asynchronous(managers=('tester',))
@language.synchronous(
    #custom_filename=__file__,
    app_context=APP_CONTEXT)
def application(tester=None,**constants):
    if '--update' in constants.get('args',[]):
        sync_github_repo("src", "colosso-cloud", "framework", "main")
    if '--test' in constants.get('args',[]):
        test()
    else:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        event_loop.create_task(loader.bootstrap())
        event_loop.run_forever()