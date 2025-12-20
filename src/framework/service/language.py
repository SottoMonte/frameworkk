from framework.service.context import container
from dependency_injector import providers
import tomli
import sys
import os
from jinja2 import Environment
import asyncio
import ast
import re
import fnmatch
from datetime import datetime, timezone
import uuid
import json
import copy
from urllib.parse import parse_qs,urlencode,urlparse
import types 
import inspect
import contextvars
from cerberus import Validator, TypeDefinition, errors
import functools
from typing import Dict, Any, Optional, List, Callable
from lark import Lark, Transformer, v_args, Token
import mistql

# Importa le funzioni di flusso e utilità che erano implicitamente usate o attese
from framework.service.flow import (
    asynchronous, 
    synchronous, 
    get_transaction_id, 
    set_transaction_id,
    _transaction_id,
    convert,
    get,      # Re-exported
    put,      # Re-exported
    format,   # Re-exported
    transform as translation, # Aliased for backward compatibility/tests
    route,
    normalize,
    framework_log
)
import framework.service.flow as flow

# =====================================================================
# --- 1. Definizione della Grammatica (DSL Rules) - CORRETTA V18 ---
# =====================================================================

grammar = r"""
    start:  [dictionary] 

    // --- TOKEN ---
    COMPARISON_OP: "==" | "!=" | ">=" | "<=" | ">" | "<"
    PIPE: "|"
    #LPAR: "("
    #RPAR: ")"
    #LBRACE: "{"
    #RBRACE: "}"
    #COMMA: ","
    #COLON: ":"
    #SEMICOLON: ";"
    QUALIFIED_CNAME: CNAME ("." CNAME)+
    COMMENT: /#[^\n]*/
    #NATURAL: natural
    #INTEGER: integer
    #RATIONAL: rational
    #IRRATIONAL: irrational
    #REAL: real
    #COMPLEX: complex
    #BOOLEAN: boolean
    #STRING: string

    property_access: (CNAME | ESCAPED_STRING) ("." (CNAME | ESCAPED_STRING))*

    value: SIGNED_NUMBER -> number
        | ESCAPED_STRING -> string
        | "Vero" -> true
        | "Falso" -> false
        | CNAME -> simple_key
        | QUALIFIED_CNAME-> simple_key
    
    // Rimosso 'expression' da 'case' per evitare ricorsione ambigua
    case.8 : value -> valor
           | dictionary -> valor
           | pair -> valor
           | tuple -> valor
           
    
    // Dizionario
    dictionary.10: "{" (pair ";")* ";"?  "}" | (pair ";")*

    // Pair - Ora accetta espressioni esplicitamente
    pair_statement.10: expression ":" expression | tuple_inline ":" expression | expression ":" tuple_inline
    pair: "(" pair_statement ")" | pair_statement
    
    // Tuple - Ora accetta espressioni
    tuple: "(" [ expression ("," expression)*] ")" -> tuple_
    tuple_inline: [expression "," expression ("," expression)*] -> tuple_

    // Unità di base (CNAME, Stringa, Numero, Booleano, o Case precedente)
    atom: ESCAPED_STRING | SIGNED_NUMBER | "Vero" | "Falso" | CNAME | dictionary | pair | tuple

    // Espressione che include atomi e operatori logici/matematici
    ?logical_expression: case
        | logical_expression COMPARISON_OP case

    expression: logical_expression (PIPE logical_expression)* -> expression

    // Importazione dei Token standard di Lark
    %import common.SIGNED_NUMBER
    %import common.ESCAPED_STRING
    %import common.CNAME
    %import common.LETTER
    %import common.WS

    // Ignora spazi bianchi e commenti
    %ignore WS
    %ignore COMMENT
"""

@v_args(inline=True)
class ConfigTransformer(Transformer):
    
    def start(self, *items):
        if not items:
            return {}
        return items[0]
        
    # --- Funzioni del Transformer ---

    def pair_statement(self, key, value):
        # key è già stato elaborato da expression ma potrebbe non essere stringa
        return str(key), value

    def dictionary(self, *statements):
        return dict(statements)

    def expression(self, *items):
        #print(f"{items} |EXPRESSION")
        
        # Filtra i token PIPE e mantiene solo gli operandi
        pipeline = []
        for item in items:
            if isinstance(item, Token) and item.type == 'PIPE':
                continue
            pipeline.append(item)
        
        # Se c'è un solo elemento, restituiscilo direttamente (appiattimento)
        if len(pipeline) == 1:
            return pipeline[0]
            
        # Restituisce una tupla identificativa e la lista di operazioni
        return ('EXPRESSION', pipeline)

    def tuple_(self, *items):
        #print(f"{items} |TUPLE", len(items))
        
        # 1. Filtra eventuali elementi None (da optional?)
        lista_filtrata = [elemento for elemento in items if elemento is not None]

        # 2. Scapsulamento se singolo elemento (permette raggruppamento (expr))
        if len(lista_filtrata) == 1:
            return lista_filtrata[0] 
        
        # 3. Altrimenti tupla
        return tuple(lista_filtrata)

    def inline_dict(self, key, value):
        #print(f"{key}: {value} |INLINE DICT")
        return str(key), value

    # --- Tipi Primitivi ---

    def number(self, n):
        n_str = str(n)
        return float(n_str) if '.' in n_str and 'E' not in n_str.upper() else int(n_str)

    def string(self, s):
        return str(s).strip('"')

    def true(self): return True
    def false(self): return False
    
    def simple_key(self, s):
        return str(s)

    def valor(self, s):
        return s
    
    # --- Liste/Tuple ---

    def pair(self, *items):
        # Gestisce eventuali parentesi attorno a pair
        return items[0] if items else None
        
    # --- Strutture Complesse ---
    
    def pipeline(self, s):
        return str(s).strip()

class DSLVisitor:
    """
    Visitatore che attraversa il dizionario risultante dal parsing
    ed esegue le espressioni marcate come 'EXPRESSION'.
    Supporta funzioni definite in Python (functions_map) e nel DSL stesso.
    """
    def __init__(self, functions_map=None):
        self.functions_map = functions_map or {}
        self.root_data = {} # Contesto globale del DSL per lookup funzioni

    def run(self, data):
        """Metodo di ingresso che imposta il contesto globale."""
        self.root_data = data
        return self.visit(data)

    def visit(self, node):
        if isinstance(node, dict):
            # Visita ricorsiva per ogni valore del dizionario
            return {k: self.visit(v) for k, v in node.items()}
        elif isinstance(node, list):
            # Visita ricorsiva per le liste
            return [self.visit(x) for x in node]
        elif isinstance(node, tuple):
            # Controlla se è un'espressione da eseguire
            if len(node) > 0 and node[0] == 'EXPRESSION':
                return self.evaluate_expression(node[1])
            else:
                # Altrimenti visita gli elementi della tupla
                return tuple(self.visit(x) for x in node)
        else:
            return node

    def evaluate_expression(self, pipeline_ops):
        """
        Esegue la pipeline di operazioni.
        Esempio: [valore, func1, func2] -> func2(func1(valore))
        """
        result = None
        
        for i, op in enumerate(pipeline_ops):
            if i == 0:
                # Il primo elemento è il valore iniziale
                result = self.visit(op) 
            else:
                # Funzioni/Operazioni
                func_name = str(op)
                
                # 1. Cerca nelle funzioni Python mappate
                if func_name in self.functions_map:
                    try:
                        result = self.functions_map[func_name](result)
                    except Exception as e:
                        framework_log("ERROR", f"[{func_name}] Errore esecuzione Python: {e}", emoji="🐍")
                
                # 2. Cerca nelle funzioni definite nel DSL (root_data)
                elif func_name in self.root_data:
                    dsl_def = self.root_data[func_name]
                    # Euristica: una funzione DSL è definita come una tupla di 3 elementi:
                    # (Args), {Body}, (Ret)
                    # Oppure (Args, Body, Ret) se wrappata in tupla
                    if isinstance(dsl_def, tuple) and len(dsl_def) == 3:
                        try:
                            #print(f"[{func_name}] Esecuzione funzione DSL...")
                            result = self.execute_dsl_function(dsl_def, result)
                        except Exception as e:
                            framework_log("ERROR", f"[{func_name}] Errore esecuzione DSL: {e}", emoji="📜")
                    else:
                         framework_log("WARNING", f"[{func_name}] Trovato nel DSL ma formato non valido per funzione: {type(dsl_def)}", emoji="⚠️")
                
                else:
                    framework_log("WARNING", f"[{func_name}] Funzione NON trovata (Python o DSL).", emoji="🤷")
                    
        return result

    def execute_dsl_function(self, func_def, input_args):
        """
        Esegue una funzione definita nel DSL.
        Firma attesa: ( (Inputs...), { Body... }, (Outputs...) )
        """
        inputs_def, body_def, outputs_def = func_def
        
        # --- 1. Mappatura Input ---
        # inputs_def può essere una tupla di coppie (es: (integer:a, float:b)) o una singola coppia
        # input_args può essere un valore singolo o una tupla
        
        local_context = {}
        
        # Normalizzazione inputs_def in lista di (type, name) o (name)
        input_params = []
        
        # Helper per estrarre il nome parametro da una definizione (che può essere coppia 'tipo:nome' o solo 'nome')
        def extract_param_name(p):
            # Se è una coppia (es: ('integer', 'a')), il nome è 'a'
            if isinstance(p, tuple) and len(p) == 2:
                return str(p[1]) # Secondo elem è il nome
            return str(p)

        # Se inputs_def è una tupla che contiene stringhe E non è una coppia ('tipo', 'val')
        # Ma (tipo, val) è una tupla.
        # Caso singolo parametro: inputs_def = ('integer', 'a')
        # Caso multi parametro: inputs_def = ( ('integer', 'a'), ('float', 'b') )
        
        if isinstance(inputs_def, tuple) and len(inputs_def) == 2 and isinstance(inputs_def[0], str):
             # È una singola coppia ('tipo', 'nome') -> un solo parametro
             input_params.append(extract_param_name(inputs_def))
        elif isinstance(inputs_def, tuple):
             # È una tupla di parametri
             for p in inputs_def:
                 input_params.append(extract_param_name(p))
        else:
             # Fallback, magari è solo il nome 'a'
             input_params.append(str(inputs_def))
             
        # Mapping valori
        if len(input_params) == 1:
            # Un solo parametro riceve tutto l'input
            local_context[input_params[0]] = input_args
        else:
            # Più parametri: input_args deve essere iterabile (tupla/lista)
            if not isinstance(input_args, (list, tuple)):
                 framework_log("ERROR", f"Mismatch argomenti: Attesi {len(input_params)}, ricevuto singolo scalare: {input_args}", emoji="❌")
                 return None
            if len(input_args) != len(input_params):
                 framework_log("ERROR", f"Mismatch argomenti. Attesi {len(input_params)}, ricevuti {len(input_args)}", emoji="❌")
                 return None
            
            for name, val in zip(input_params, input_args):
                local_context[name] = val
                
        # --- 2. Esecuzione Body ---
        # body_def è un dizionario (es: {'output': "a + b"})
        
        for key, expr_str in body_def.items():
            try:
                # Valuta la stringa come espressione Python
                # Permette operazioni base (a + b, ecc)
                #val = eval(str(expr_str), {}, local_context)
                val = mistql.query(str(expr_str), data=local_context)
                local_context[str(key)] = val
            except Exception as e:
                print(f"Errore valutazione espressione '{expr_str}': {e}")
                
        # --- 3. Return Output ---
        # outputs_def definisce cosa ritornare (es: (float:output))
        # Estraiamo il nome della variabile da ritornare
        ret_val = None
        
        output_vars = []
        if isinstance(outputs_def, tuple) and len(outputs_def) == 2 and isinstance(outputs_def[0], str):
             output_vars.append(extract_param_name(outputs_def))
        elif isinstance(outputs_def, tuple):
             for p in outputs_def:
                 output_vars.append(extract_param_name(p))
        else:
             output_vars.append(str(outputs_def))
             
        if len(output_vars) == 1:
            var_name = output_vars[0]
            ret_val = local_context.get(var_name, None)
        else:
            ret_val = tuple(local_context.get(v, None) for v in output_vars)
            
        return ret_val

# ----------------------------------------------------------------------
# --- 3. Funzione Principale di Parsing ---
# ----------------------------------------------------------------------

def parse_dsl_file(content):
    parser = Lark(grammar, parser='earley')
    tree = parser.parse(content)
    return ConfigTransformer().transform(tree)

def execute_dsl_file(content):
    config = parse_dsl_file(content)
    visitor = DSLVisitor(functions_map=dsl_functions)
    
    # Nota: Usiamo visitor.run() invece di visit() per inizializzare il contesto
    final_result = visitor.run(config)
    return final_result

def run_dsl_tests(visitor: DSLVisitor, parsed_data: dict, functions_map: dict):
    """
    Esegue tutti i casi definiti nella sezione 'test_suite' del DSL.
    """
    test_suite = parsed_data.get('test_suite')
    
    if not test_suite or not isinstance(test_suite, tuple):
        print("🔴 Errore: Sezione 'test_suite' non trovata o non valida nel file DSL.")
        return False

    all_passed = True
    print("\n====================================")
    print(f"Esecuzione {len(test_suite)} Casi di Test DSL")
    print("====================================")

    for test_case in test_suite:
        if not isinstance(test_case, dict):
            print(f"🔴 Errore nel formato del caso test: {test_case}")
            continue

        test_id = test_case.get('id', 'N/A')
        target_name = test_case.get('target')
        input_args = test_case.get('input_args')
        expected = test_case.get('expected_output')

        print(f"\n[Test ID: {test_id}] Testing '{target_name}'...")

        try:
            # 1. Trova la funzione/pipeline target nel contesto globale (root_data)
            target_def = parsed_data.get(target_name)

            if target_def is None:
                print(f"🔴 FALLITO: Target '{target_name}' non trovato nel DSL.")
                all_passed = False
                continue

            # 2. Esecuzione: Le funzioni DSL sono tuple di 3 elementi (Args, Body, Ret)
            if isinstance(target_def, tuple) and len(target_def) == 3:
                # Esegui la funzione DSL
                actual_output = visitor.execute_dsl_function(target_def, input_args)
            
            # 3. Esecuzione: Se è una Pipeline (già pre-valutata come 'EXPRESSION' dal Transformer, ma che deve essere eseguita qui)
            elif isinstance(target_def, tuple) and len(target_def) > 0 and target_def[0] == 'EXPRESSION':
                 # Per testare una pipeline che non è una funzione, dobbiamo iniettare
                 # l'input_args nel primo elemento della pipeline e rieseguire.
                 # Questo è complesso, quindi è meglio definire le pipeline come funzioni DSL
                 # che accettano l'input, come fatto nell'esempio di prima.
                 # Per semplicità, qui assumiamo che solo le funzioni DSL siano testate direttamente.
                 print(f"⚠️ Tipo target non supportato per test diretto: {target_name}. Usare una funzione DSL.")
                 all_passed = False
                 continue
                 
            else:
                 # Se il target non è una funzione DSL, eseguiamo la sua valutazione.
                 # Ad esempio, se target è 'numeri: 100;' e lo vogliamo testare
                 actual_output = visitor.visit(target_def)


            # 4. Confronto
            if actual_output == expected:
                print("🟢 PASSATO!")
            else:
                print("🔴 FALLITO!")
                print(f"   Atteso: {expected}")
                print(f"   Ottenuto: {actual_output}")
                all_passed = False

        except Exception as e:
            print(f"🔴 FALLITO con ECCEZIONE: {e}")
            all_passed = False
            
    print("\n====================================")
    print(f"RISULTATO FINALE: {'🟢 TUTTI I TEST PASSATI' if all_passed else '🔴 TEST FALLITI'}")
    print("====================================")
    return all_passed

# ----------------------------------------------------------------------
# --- 4. Esempio di Utilizzo ---
# ----------------------------------------------------------------------

# --- Funzioni definite nel codice Python ---
def custom_print(data):
    print(f"*** CUSTOM PRINT ***: {data}")
    return data 

def custom_double(data):
    if isinstance(data, (int, float)):
        return data * 2
    return data

# Mappa delle funzioni disponibili per il DSL
dsl_functions = {
    'print': custom_print,
    'raddoppia': custom_double
}