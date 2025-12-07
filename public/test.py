from lark import Lark, Transformer, v_args
import json

# ----------------------------------------------------------------------
# --- 1. Definizione della Grammatica (DSL Rules) - CORRETTA V17 ---
# ----------------------------------------------------------------------

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

    value: SIGNED_NUMBER -> number
        | ESCAPED_STRING -> string
        | "Vero" -> true
        | "Falso" -> false
        | CNAME -> simple_key
        | QUALIFIED_CNAME-> simple_key
    
    
    case.8 : value -> valor
           | dictionary -> valor
           | pair -> valor
           | tuple -> valor
           | expression -> valor
    
    // Dizionario
    dictionary.10: "{" (pair ";")* ";"?  "}" | (pair ";")*

    // Pair
    pair_statement.10: case ":" case | tuple_inline ":" case | case ":" tuple_inline
    pair: "(" pair_statement ")" | pair_statement
    
    // Tuple
    tuple: "(" [ case ("," case)*] ")" -> tuple_
    tuple_inline: [case "," case ("," case)*] -> tuple_

    // Unità di base (CNAME, Stringa, Numero, Booleano, o Case precedente)
    atom: ESCAPED_STRING | SIGNED_NUMBER | "Vero" | "Falso" | CNAME | dictionary | pair | tuple

    // Espressione che include atomi e operatori logici/matematici
    // Aggiungi gli operatori logici, esempio: ==, !=, >, <, ecc.
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
        
    def config_block(self, *statements):
        return dict(statements)
        
    # --- Funzioni del Transformer ---

    def imports_statement(self, key, imports_dict):
        return str(key), imports_dict

    def exports_statement_(self, key, *items):
        return str(key), list(items)

    def list_statement_(self, key, item1, item2, *rest_items):
        return str(key), [item1, item2] + list(rest_items)

    def single_value_statement_(self, key, value_list):
        return str(key), value_list
        
    def pair_statement(self, key, value):
        print(f"{key}: {value} |DICT")
        return str(key), value

    def dictionary(self, *statements):
        return dict(statements)

    def expression2(self, *statements):
        print(f"{statements} |EXPRESSION")
        return str(statements)

    def expression(self, *items):
        print(f"{items} |EXPRESSION")
        
        # Inizializza la pipeline con il primo elemento
        pipeline = []
        
        # Ipotizzando che gli elementi in *items siano già trasformati 
        # (es. ('<', 'a', 5.0), 'print', ('save', 'log'))
        
        # Loop sugli elementi, saltando gli operatori di pipeline se sono inclusi esplicitamente
        for item in items:
            # Controllo per token come il tuo 'PIPE: "|"'
            pipeline.append(str(item))
                
        # Restituisce una lista che rappresenta la sequenza delle operazioni
        return ('EXPRESSION:',''.join(pipeline))

    def tuple_(self, *items):
        print(f"{items} |TUPLE",len(items))
        lista_filtrata = [elemento for elemento in items if elemento is not None]
        return tuple(lista_filtrata)
    '''def tuple_(self, *items):
        print(f"{items} |TUPLE", len(items))
        
        # 1. Filtra eventuali elementi None
        lista_filtrata = [elemento for elemento in items if elemento is not None]

        # 2. LOGICA AGGIORNATA: Se c'è ESATTAMENTE UN elemento, 
        # restituiscilo direttamente (scapsulamento).
        if len(lista_filtrata) == 1:
            return lista_filtrata[0] 
        
        # 3. Altrimenti, restituisci la tupla normale (zero o più di un elemento)
        return tuple(lista_filtrata)'''

    def inline_dict(self, key, value):
        print(f"{key}: {value} |INLINE DICT")
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

    def list_group(self, *items):
        return list(items)

    def pair(self, *items):
        print(items,'<----------------','pair')
        return items[0] if items else None
        
    # --- Strutture Complesse ---
    
    def pipeline(self, s):
        return str(s).strip()

    def imports_list(self, *pairs):
        import_dict = {}
        for k, v in pairs:
             import_dict[str(k)] = v
        return import_dict
    
    def imports_pair(self, key, value):
        return str(key), value
        

# ----------------------------------------------------------------------
# --- 3. Funzione Principale di Parsing ---
# ----------------------------------------------------------------------

def parse_dsl_file(content):
    parser = Lark(grammar, parser='earley')
    tree = parser.parse(content)
    return ConfigTransformer().transform(tree)


# ----------------------------------------------------------------------
# --- 4. Esempio di Utilizzo ---
# ----------------------------------------------------------------------

file_input_finale = """
{
    imports:save:"application/action/save.dsl",delete:"application/action/delete.dsl";
    exports:somma,delete.somma;
    
    # Firma della funzione: (Input), (Corpo), (Output)
    #somma: (integer:a,float:b), { output:"a + b" }, (float:output);
    
    PI: 3.14159;
    TENTATIVI_MAX: 5;
    MODO_DEBUG: Vero;
    
    numeri: 100, 250, 50;
    
    resto: numeri[:1] | somma | (numeri[2]) somma;
    
    utente_completo: {
        nome: "Giulia"; 
        eta: 25; 
        attivo: Vero; 
        residenza: {
            citta: "Roma";
            cap: 100;
        };
    };
}
"""

file_input = """
{
    numeri: 100;
    stringa: "ciao";
    booleano: Vero;
    lista: 100, 200, 300,(1,(100:100;200:200;),3);
    tuple: 1,2,3;
    ttt: nome:"Giulia";eta:25;
    espressione: (100,200) | print;
    dizionario: {nome:"Giulia"; eta:25; attivo:Vero;ttt: nome:"1";lista: 100, 200, 300;};
    coppia: a:100;
    somma: (integer:a), { output:"a + b"; }, (integer:b);
}
"""

output_atteso = {
    "imports": {
        "save": "application/action/save.dsl",
        "delete": "application/action/delete.dsl"
    },
    "exports": [
        "somma",
        "delete.somma"
    ],
    "somma": [
        [
            "integer:a",
            "float:b"
        ],
        {
            "output": "a + b"
        },
        [
            "float:output"
        ]
    ],
    "PI": 3.14159,
    "TENTATIVI_MAX": 5,
    "MODO_DEBUG": True,
    "numeri": [
        100,
        250,
        50
    ],
    "resto": "numeri[:1] | somma | (numeri[2]) somma",
    "utente_completo": {
        "nome": "Giulia",
        "eta": 25,
        "attivo": True,
        "residenza": {
            "citta": "Roma",
            "cap": 100
        }
    }
}

print("--- Risultato del Parsing con Lark (Corretto V17) ---")
print(file_input)
parsed_data = parse_dsl_file(file_input)
print("--- Risultato del Parsing con Lark (Corretto V17) ---")
print(parsed_data)
#print(json.dumps(parsed_data, indent=4))