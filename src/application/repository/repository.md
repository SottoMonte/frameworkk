# Repository Layer - `src/application/repository`

Questa cartella contiene la logica dedicata all'accesso e gestione delle sorgenti dati esterne.

## Obiettivo

Il repository `repository` definisce un'interfaccia modulare e astratta per la gestione di entità remote, utilizzando una combinazione di:
- **Mapper**: per tradurre tra i dati delle API e il modello interno.
- **Payloads**: per strutturare e trasformare i dati in ingresso/uscita.
- **Location**: per identificare gli endpoint REST da interrogare.

## Componenti principali

### ⚙️ `repository = factory.repository(...)`
Costruisce dinamicamente un oggetto repository usando la `factory`, configurato per accedere alle API di GitHub e ottenere informazioni su:
- Rami (`branches`)
- Struttura ad albero (`git/trees`)
- Informazioni generiche (`repos/...`)
  
Definisce:
- `location`: mapping degli endpoint REST GitHub.
- `model`: nome dell'entità (`repository`).
- `values`: trasformatori di campo, es. `tree` viene gestito con `build_tree_dict`.
- `mapper`: conversione campo-per-campo tra modello interno e risposta API.
- `payloads` e `functions`: gestori logici per azioni asincrone (es. `view`, `update`).

```python
import base64
import re

modules = {'factory': 'framework.service.factory','flow': 'framework.service.flow'}

def build_tree_dict2(tree):
    """
    Costruisce una rappresentazione ad albero nidificata da una lista di percorsi,
    includendo il campo 'path' per ciascun nodo.

    Args:
        tree (list): Lista di dizionari con chiavi "path", "type" e "sha".

    Returns:
        dict: Struttura ad albero nidificata con percorsi completi.
    """
    def add_to_tree(tree, path_parts, sha, type_, parent_path="/"):
        """Funzione ricorsiva per aggiungere un percorso all'albero."""
        node_name = path_parts[0]
        current_path = f"{parent_path}{node_name}/"
        
        # Cerca il nodo nella lista dei figli
        for child in tree["children"]:
            if child["name"] == node_name:
                # Nodo trovato, continua la ricorsione
                if len(path_parts) > 1:
                    add_to_tree(child, path_parts[1:], sha, type_, current_path)
                return
        
        # Nodo non trovato, creane uno nuovo
        new_node = {
            "id": f"{parent_path.strip('/')}/{node_name}",
            "name": node_name,
            "path": current_path,
            "children": []
        }
        if len(path_parts) == 1:
            # Se è un nodo foglia, aggiungi informazioni sul tipo e lo sha
            new_node["type"] = type_
            new_node["sha"] = sha
        else:
            # Continua la ricorsione per i figli
            add_to_tree(new_node, path_parts[1:], sha, type_, current_path)
        
        # Aggiungi il nuovo nodo ai figli del nodo corrente
        tree["children"].append(new_node)
    # Nodo radice
    tree_dict = {
        'repository':re.search(r"https://api\.github\.com/repos/([^/]+/[^/]+)/", tree[0].get('url')).group(1),
        "id": "root",
        "name": "Root Node",
        "path": "/",
        "children": []
    }
    
    for item in tree:
        path_parts = item["path"].split("/")
        add_to_tree(tree_dict, path_parts, item["sha"], item["type"])
    
    return tree_dict

def build_tree_dict(tree):
    """Costruisce una struttura ad albero da una lista di percorsi GitHub, con 'path' che esclude il nome file nei file."""

    def add_to_tree(node, parts, sha, type_, parent_path="/"):
        name = parts[0]
        is_leaf = len(parts) == 1
        current_path = parent_path if is_leaf and type_ == "blob" else f"{parent_path}{name}/"

        child = next((c for c in node["children"] if c["name"] == name), None)
        if not child:
            child = {
                "id": f"{parent_path.strip('/')}/{name}",
                "name": name,
                "path": current_path,
                "children": []
            }
            node["children"].append(child)

        if is_leaf:
            child.update({"type": type_, "sha": sha})
            # I file non hanno 'children'
            if type_ == "blob":
                child.pop("children", None)
        else:
            add_to_tree(child, parts[1:], sha, type_, current_path)

    repo_url = tree[0].get("url")
    repository = re.search(r"https://api\.github\.com/repos/([^/]+/[^/]+)/", repo_url).group(1)

    root = {
        "repository": repository,
        "id": "root",
        "name": "Root Node",
        "path": "/",
        "children": []
    }

    for item in tree:
        add_to_tree(root, item["path"].split("/"), item["sha"], item["type"])

    return root

@flow.asynchronous(managers=('storekeeper',))
async def view(storekeeper,**constants):
    repo = constants.get('repo','framework')
    branch = 'main'
    payload = constants.get('payload',{})
    #payload |= {'name':repo,'branch':branch,'owner':'SottoMonte'}
    payload |= {'branch':branch,}

    
    branch_data = await storekeeper.gather(**constants|{'payload':payload})
    payload |= {'sha':branch_data.get('result')[0].get('sha')}
    payload.pop('branch')
    
    return payload

@flow.asynchronous(managers=('storekeeper',))
async def update_payload(storekeeper,**constants):
    #constants.pop('owner')
    
    return {'method':'PATCH'}

repository = factory.repository(
    location = {'GITHUB':[
        "repos/{owner}/{name}/git/trees/{sha}?recursive=1",
        "repos/{owner}/{name}/branches/{branch}",
        "repos/{owner}/{name}",
        "repos/{filter.eq.owner}/{filter.eq.name}",
        "orgs/{filter.eq.owner}/repos",
        "orgs/{owner}/repos",
        "users/{filter.eq.owner}/repos",
        "users/{owner}/repos",
        #"user/repos?per_page={perPage}&page={currentPage}",
        "user/repos",
    ]},
    model = 'repository',
    values = {
        'tree':{'MODEL':build_tree_dict},
        #'content':{'REPOSITORY':encode,'MODEL':decode},
    },
    mapper = {
        'sha':{'GITHUB':'commit.commit.tree.sha'},
        'name':{'GITHUB':'name'},
        'branch':{'GITHUB':'default_branch'},
        'owner':{'GITHUB':'owner.login'},
        'type':{'REPOSITORY':'type'},
        #'content':{'REPOSITORY':'content'},
        'created':{'GITHUB':'created_at'},
        'updated':{'GITHUB':'updated_at'},
        'language':{'REPOSITORY':'language'},
        #'description':{'REPOSITORY':'description'},
        'visibility':{'GITHUB':'private'},
        'tree':{'GITHUB':'tree'},
        'stars':{'GITHUB':'stargazers_count'},
        'forks':{'GITHUB':'forks_count'},
    },
    payloads = {
    #'create':create_payload,
    #'delete':delete_payload,
        #'update':update_payload,
        'view':view,
    },
    functions = {
        'update':update_payload,
    },
)
```
