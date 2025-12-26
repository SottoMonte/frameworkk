import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Import load.py normally (not via the dynamic loader)
from framework.service import load

# Funzione per scoprire tutti i contratti da riparare
def discover_files_to_repair(start_dir="src"):
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

async def repair():
    services = discover_files_to_repair()
    print(f"Repairing {len(services)} contracts (Auto-Discovery)...")
    
    for service_path in services:
        print(f"Repairing contract for {service_path}...")
        try:
            res = await load.generate_checksum(service_path)
            data = res.get('data', {}) if isinstance(res, dict) and 'data' in res else res
            print(f"  Result type: {type(res)}")
            import json
            # print(f"  Result content: {json.dumps(res, indent=2)}") 
            # ... rest of logic

            if service_path in data:
                import json
                hashes = data[service_path]
                if not hashes:
                    print(f"  ⚠️ Warning: No hashes generated for {service_path}")
                contract_path = service_path.replace(".py", ".contract.json")
                with open(contract_path, "w") as f:
                    json.dump(hashes, f, indent=4)
                print(f"  ✅ Updated {contract_path}")
            else:
                print(f"  ❌ Failed to find {service_path} in result keys: {list(data.keys() if isinstance(data, dict) else [])}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ Error repairing {service_path}: {e}")

if __name__ == "__main__":
    asyncio.run(repair())
