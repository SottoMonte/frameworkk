{
    numeri: 100;
    stringa: "ciao";
    
    # --- Definizione Funzione DSL ---
    # somma: (Inputs), { Body }, (Returns)
    # Inputs: (type:name, ...)
    # Body: { output_var: "expression"; }  <-- Semicolon required
    somma_dsl: (integer:a, integer:c), { res: "a + c"; }, (integer:res);
    moltiplica_dsl: (integer:a, integer:c), { res: "(a + c) * 2"; }, (integer:res);
    
    # --- Utilizzo in Pipeline ---
    # (100, 200) -> somma_dsl (esegue a+b=300) -> raddoppia (600) -> print
    test_dsl_func: (100, 200) | somma_dsl | raddoppia | print; 
    test_dsl_func2: (100, 200) | moltiplica_dsl | print;
}