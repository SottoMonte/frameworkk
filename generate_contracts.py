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

# Lista dei file per cui generare i contratti
FILES_TO_GENERATE = [
    "src/framework/service/run.py",
    "src/framework/service/flow.py",
    "src/framework/service/load.py",
    "src/framework/service/language.py",
    "src/framework/service/factory.py",
    "src/framework/manager/executor.py",
    "src/framework/manager/tester.py",
    "src/infrastructure/message/otel.py"
]

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
            # A volte generate_checksum potrebbe ritornare direttamente il contenuto o usare chiavi diverse
            # Controlliamo cosa torna
            # Se generate_checksum fallisce internamente, potrebbe tornare un dict vuoto o errore
            print(f"❌ Failed or Empty data for {path}. Result keys: {data.keys() if isinstance(data, dict) else type(data)}")
            # Fallback: a volte il path chiave nel dict risultato potrebbe variare leggermente
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
        import traceback
        traceback.print_exc()

async def main():
    print("🚀 Starting Contract Generation...")
    for f in FILES_TO_GENERATE:
        # Verifica se il file esiste prima
        if os.path.exists(f):
            await generate(f)
        else:
            print(f"⚠️ File not found, skipping: {f}")
    print("🏁 Done.")

if __name__ == "__main__":
    asyncio.run(main())
