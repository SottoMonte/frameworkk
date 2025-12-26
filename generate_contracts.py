import sys
import os
import asyncio
import json

# Setup path per importare src
cwd = os.getcwd()
sys.path.insert(1, cwd + '/src')

# Importa i moduli del framework
# Nota: L'importazione attiverà i decoratori, quindi l'ambiente deve essere pronto.
import framework.service.load as load
import framework.service.flow as flow

# Funzione per scoprire tutti i contratti da generare
def discover_files_to_generate(start_dir="src"):
    files = []
    for root, _, filenames in os.walk(start_dir):
        for filename in filenames:
            if filename.endswith(".test.py"):
                # Percorso del file di test
                test_path = os.path.join(root, filename)
                # Percorso del file principale corrispondente
                main_path = test_path.replace(".test.py", ".py")
                if os.path.exists(main_path):
                    files.append(main_path)
    return files

async def generate(path):
    print(f"Generating contract for {path}...")
    
    # Il framework usa path relativi senza 'src/'
    rel_path = path
    if rel_path.startswith('src/'):
        rel_path = rel_path[4:]
        
    try:
        # load.generate_checksum calcola gli hash usando ast e dill
        result = await load.generate_checksum(rel_path)
        
        # Gestione risultato (se wrapped in transaction o raw)
        data = result.get('data') if isinstance(result, dict) and 'data' in result else result
        
        if not data or rel_path not in data:
            print(f"❌ Failed or Empty data for {path}. Result keys: {data.keys() if isinstance(data, dict) else type(data)}")
            return

        contract_content = data[rel_path]
        
        # Verifica che ci sia contenuto
        if not contract_content:
            print(f"⚠️ Warning: Generated contract is empty for {path}")
        
        contract_path = path.replace('.py', '.contract.json')
        
        with open(contract_path, 'w') as f:
            json.dump(contract_content, f, indent=4)
            
        print(f"✅ Contract written to {contract_path}")
        
    except Exception as e:
        print(f"❌ CRITICAL Error generating {path}: {e}")
        # import traceback
        # traceback.print_exc()

async def main():
    print("🚀 Starting Contract Generation (Auto-Discovery)...")
    files_to_generate = discover_files_to_generate()
    print(f"🔍 Found {len(files_to_generate)} modules with tests.")
    
    for f in files_to_generate:
        await generate(f)
        
    print("🏁 Done.")

if __name__ == "__main__":
    asyncio.run(main())
