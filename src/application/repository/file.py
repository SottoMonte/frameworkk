modules = {'factory': 'framework.service.factory','flow': 'framework.service.flow'}

import base64

def decode(data):
    """
    Decodifica una stringa base64 in testo.

    Args:
        data (str): Stringa codificata in base64.

    Returns:
        str: Testo decodificato.
    """
    if not isinstance(data, str):
        raise TypeError("Il dato da decodificare deve essere una stringa.")

    return base64.b64decode(data).decode('utf-8')

def encode(data):
    """
    Codifica una stringa in base64.

    Args:
        data (str): Testo da codificare.

    Returns:
        str: Stringa codificata in base64.
    """
    if not isinstance(data, str):
        raise TypeError("Il dato da codificare deve essere una stringa.")
    return base64.b64encode(data.encode()).decode()

def rimuovi_ultimo_slash(stringa):
  """
  Rimuove l'ultimo slash di una stringa se presente.

  Args:
    stringa: La stringa da modificare.

  Returns:
    La stringa modificata, con l'ultimo slash rimosso, o la stringa originale se non c'è slash finale.
  """
  if stringa.endswith("/"):
    return stringa[:-1]
  else:
    return stringa


import xml.etree.ElementTree as ET

def build_xml_tree_dict(file_path):
    source = decode(file_path)
    tree = ET.parse(source)
    root_elem = tree.getroot()

    def parse_element(elem):
        node = {
            "tag": elem.tag,
            "attributes": elem.attrib,
            "text": (elem.text or "").strip(),
            "children": [parse_element(child) for child in elem]
        }
        return node

    root_dict = {
        "type": "file",
        "name": os.path.basename(file_path),
        "path": file_path,
        "children": [parse_element(root_elem)]
    }

    return root_dict

import re

def build_markdown_tree_dict(file_path):
    source = decode(file_path)
    lines = source.splitlines()
    root = {
        "type": "file",
        "name": 'Markdown File',
        "path": file_path,
        "children": []
    }

    stack = [{
        "level": 0,
        "node": root
    }]

    current_node = None
    buffer = []

    header_pattern = re.compile(r"^(#+)\s+(.*)")

    for line in lines:
        header_match = header_pattern.match(line)
        if header_match:
            # Save previous buffered content
            if current_node is not None and buffer:
                current_node["content"] = "".join(buffer).strip()
                buffer = []

            level = len(header_match.group(1))
            title = header_match.group(2)

            new_node = {
                "type": "heading",
                "level": level,
                "title": title,
                "children": []
            }

            # Find parent node in stack
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            parent = stack[-1]["node"]
            parent["children"].append(new_node)
            stack.append({"level": level, "node": new_node})
            current_node = new_node
        else:
            buffer.append(line)

    # Aggiungi contenuto residuo all'ultimo nodo
    if current_node and buffer:
        current_node["content"] = "".join(buffer).strip()

    return root

try:
    import tomllib  # Python 3.11+
except ImportError:
    import toml


def build_toml_tree_dict(file_path):
    source = decode(file_path)
    data = tomllib.load(source) if "tomllib" in globals() else toml.load(source)

    def parse_node(obj, path=""):
        children = []
        for key, value in obj.items():
            if isinstance(value, dict):
                children.append({
                    "type": "section",
                    "name": key,
                    "path": f"{path}.{key}" if path else key,
                    "children": parse_node(value, f"{path}.{key}" if path else key)
                })
            elif isinstance(value, list) and all(isinstance(i, dict) for i in value):
                # Array of tables
                array_nodes = []
                for idx, item in enumerate(value):
                    array_nodes.append({
                        "type": "table_item",
                        "name": f"{key}[{idx}]",
                        "path": f"{path}.{key}[{idx}]" if path else f"{key}[{idx}]",
                        "children": parse_node(item, f"{path}.{key}[{idx}]")
                    })
                children.append({
                    "type": "array_table",
                    "name": key,
                    "path": f"{path}.{key}" if path else key,
                    "children": array_nodes
                })
            else:
                children.append({
                    "type": "key",
                    "name": key,
                    "value": value,
                    "path": f"{path}.{key}" if path else key
                })
        return children

    return {
        "type": "file",
        "name": 'ok',
        "path": '',
        "children": parse_node(data)
    }

import ast

def build_python_tree_dict(file_path):
    source = decode(file_path)
    tree = ast.parse(source)
    filename = 'python'

    def get_node_name(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
        elif isinstance(node, ast.ClassDef):
            return node.name
        elif isinstance(node, ast.Import):
            return ", ".join([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            return f"from {node.module} import " + ", ".join([alias.name for alias in node.names])
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            return ", ".join(targets)
        return "unknown"

    root = {
        "type": "module",
        "name": filename,
        "path": file_path,
        "children": []
    }

    categories = {
        "imports": [],
        "classes": [],
        "functions": [],
        "async_functions": [],
        "constants": []
    }

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            categories["imports"].append({
                "type": "import",
                "name": get_node_name(node),
                "lineno": node.lineno,
                "col_offset": node.col_offset,
                "source": ast.get_source_segment(source, node)
            })
        elif isinstance(node, ast.ClassDef):
            class_node = {
                "type": "class",
                "name": node.name,
                "lineno": node.lineno,
                "col_offset": node.col_offset,
                "source": ast.get_source_segment(source, node),
                "children": []
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    class_node["children"].append({
                        "type": "method",
                        "name": item.name,
                        "lineno": item.lineno,
                        "col_offset": item.col_offset,
                        "source": ast.get_source_segment(source, item)
                    })
                elif isinstance(item, ast.AsyncFunctionDef):
                    class_node["children"].append({
                        "type": "async_method",
                        "name": item.name,
                        "lineno": item.lineno,
                        "col_offset": item.col_offset,
                        "source": ast.get_source_segment(source, item)
                    })
            categories["classes"].append(class_node)
        elif isinstance(node, ast.FunctionDef):
            categories["functions"].append({
                "type": "function",
                "name": node.name,
                "lineno": node.lineno,
                "col_offset": node.col_offset,
                "source": ast.get_source_segment(source, node)
            })
        elif isinstance(node, ast.AsyncFunctionDef):
            categories["async_functions"].append({
                "type": "async_function",
                "name": node.name,
                "lineno": node.lineno,
                "col_offset": node.col_offset,
                "source": ast.get_source_segment(source, node)
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    categories["constants"].append({
                        "type": "constant",
                        "name": target.id,
                        "lineno": node.lineno,
                        "col_offset": node.col_offset,
                        "source": ast.get_source_segment(source, node)
                    })

    for key, items in categories.items():
        if items:
            root["children"].append({
                "type": key,
                "name": key.replace("_", " ").capitalize(),
                "children": items
            })

    return root

def build_python_tree_dict2(file_path):
    source = decode(file_path)

    tree = ast.parse(source)
    filename = 'python'

    def get_node_name(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
        elif isinstance(node, ast.ClassDef):
            return node.name
        elif isinstance(node, ast.Import):
            return ", ".join([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            return f"from {node.module} import " + ", ".join([alias.name for alias in node.names])
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            return ", ".join(targets)
        return "unknown"

    root = {
        "type": "module",
        "name": filename,
        "path": file_path,
        "children": []
    }

    categories = {
        "imports": [],
        "classes": [],
        "functions": [],
        "async_functions": [],
        "constants": []
    }

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            categories["imports"].append({
                "type": "import",
                "name": get_node_name(node)
            })
        elif isinstance(node, ast.ClassDef):
            class_node = {
                "type": "class",
                "name": node.name,
                "children": []
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    class_node["children"].append({
                        "type": "method",
                        "name": item.name
                    })
                elif isinstance(item, ast.AsyncFunctionDef):
                    class_node["children"].append({
                        "type": "async_method",
                        "name": item.name
                    })
            categories["classes"].append(class_node)
        elif isinstance(node, ast.FunctionDef):
            categories["functions"].append({
                "type": "function",
                "name": node.name
            })
        elif isinstance(node, ast.AsyncFunctionDef):
            categories["async_functions"].append({
                "type": "async_function",
                "name": node.name
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    categories["constants"].append({
                        "type": "constant",
                        "name": target.id
                    })

    for key, items in categories.items():
        if items:
            root["children"].append({
                "type": key,
                "name": key.replace("_", " ").capitalize(),
                "children": items
            })

    return root



async def create_payload(**constants):
    payload = constants.get('payload',{})
    payload.pop('action')
    #payload.pop('location')
    payload |= {
        "message": "Creating new file",
        "content": encode(payload.get('content',''))  # Content should be base64-encoded
    }
    print(payload,'log')
    return payload

@flow.asynchronous(managers=('storekeeper',))
async def delete_payload(storekeeper,**constants):
    branch_data = await storekeeper.gather(**constants)
    sha = branch_data.get('result')[0].get('sha','')
    payload = {
        "message": "Deleting file",
        "sha": sha
    }
    return constants.get('payload')|payload

@flow.asynchronous(managers=('storekeeper',))
async def write_payload(storekeeper,**constants):
    branch_data = await storekeeper.gather(**constants)
    sha = branch_data.get('result')[0].get('sha','')
    payload = {
        "message": "Updating file",
        "content": base64.b64encode(constants.get('payload').get('content','').encode()).decode(),
        "sha": sha
    }
    return constants.get('payload')|payload

repository = factory.repository(
    location = {'GITHUB':[
       "repos/{payload.location}/contents/{payload.path}",
       "repos/{payload.location}/contents/{payload.path}/{payload.name}",
       "repos/{filter.eq.location}/contents/{filter.eq.path}",
       "repos/{filter.eq.location}/contents/{filter.eq.path}/{filter.eq.name}",
    ]},
    model = 'file',
    values = {
        'content':{'GITHUB':encode,'MODEL':decode},
        'path':{'GITHUB':rimuovi_ultimo_slash,'MODEL':rimuovi_ultimo_slash},
        #'tree':{'MODEL':build_python_tree_dict},
    },
    mapper = {
        'name':{'GITHUB':'name'},
        'type':{'GITHUB':'type'},
        'content':{'GITHUB':'content'},
        #'tree':{'GITHUB':'content'},
    },
    payloads = {
        'create':create_payload,
        'delete':delete_payload,
        'update':write_payload,
    }
)