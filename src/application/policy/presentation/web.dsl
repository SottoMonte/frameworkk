{
    # ======================================================================
    # === 1. DATI DI CONTESTO (INPUT E STORE) ===
    # ======================================================================

    input: {
        context: { i: ("sub", "obj", "act", "type"); };
        principal: { 
            id: "user-101"; 
            roles: ("author", "premium"); 
            department: "marketing"; 
        };
        resource: { 
            kind: "document";
            id: "doc-456";
            owner_id: "user-101";
            status: "PUBLISHED";
        };
        # Assumiamo che input.path venga iniettato prima dell'esecuzione della policy
        path: "/profile"; 
    };
    
    # ----------------------------------------------------------------------
    
    store: {
        data: {
            # Limiti (come dizionari)
            limits: {
                free_tier: { max_downloads: 5; max_storage_mb: 100; };
                premium_tier: { max_downloads: 999; max_storage_mb: 10240; };
            };
            
            # Rotte (come una lista/tupla di dizionari)
            routes: (
                { path: "/", type: "view"; view: "auth/login.xml"; method: "GET"; },
                { path: "/ops"; type: "view"; view: "ops/overview.xml"; method: "GET"; },
                { path: "/profile"; type: "view"; view: "auth/profile.xml"; method: "GET"; },
                # ... (aggiungere qui tutte le altre rotte come dizionari)
                { path: "/login"; type: "login"; method: "POST"; },
                { path: "/create"; type: "action"; method: "POST"; }
            );
        };
    };

    # ======================================================================
    # === 2. POLICY RULES (REGOLE CONDIZIONALI) ===
    # ======================================================================
    
    # Le policies sono rappresentate come una lista/tupla di dizionari.
    policies: (
        
        # Regola 1: Chiunque può leggere documenti PUBLISHED (se ha il ruolo corretto)
        {
            id: "rule-1-read-published";
            effect: "allow";
            match: { act: "read"; };
            description: "Consente la lettura di documenti pubblici/pubblicati.";
            # Uso di MistQL per la condizione booleana
            condition: '(input.resource.status == "PUBLISHED") && ("premium" in input.principal.roles)';
        },
        
        # Regola 2: L'owner può editare
        {
            id: "rule-2-owner-edit";
            effect: "allow";
            match: { act: "edit"; };
            # Uso di MistQL per la condizione booleana
            condition: 'input.principal.id == input.resource.owner_id';
        },

        # Regola 3: Limite di Download per utenti Free
        {
            id: "rule-3-download-limit";
            effect: "deny";
            match: { act: "download"; };
            description: "Nega il download se la quota per il tier FREE è stata superata.";
            # MistQL non supporta l'operatore 'in' sulle stringhe, ma supponiamo 
            # che supporti 'in' sulle tuple/liste e l'accesso ai campi
            condition: '"free" in input.principal.roles && input.principal.download_count > store.data.limits.free_tier.max_downloads';
        },
        
        # Regola 4: Autorizzazione al Profilo/Dashboard (Ricerca Condizionale)
        {
            id: "rule-4-profile-dashboard";
            effect: "allow";
            match: { type: "view"; };
            description: "Permette l'accesso a /profile e /dashboard solo se autenticati.";
            # Nota: Questa condizione richiede una funzione di ricerca complessa (come 'some' in TOML) 
            # che deve essere gestita da una FUNZIONE PYTHON mappata e chiamata nella pipeline 
            # o direttamente nel corpo MistQL, se supportato. 
            # Qui si usa la sintassi di MistQL per 'some' (simile a JmesPath)
            condition: 'input.principal.id != "" && store.data.routes | some(@: @.path == input.path && (@.path == "/profile" || @.path == "/dashboard"))';
        }
    );

    # ======================================================================
    # === 3. MOTORE DI DECISIONE E VALUTAZIONE ===
    # ======================================================================
    
    output: {
        default: "deny";
        logic: "some(policies | filter(rule: rule.effect == 'allow' && rule.is_matched == true))"; 
    };

    # ----------------------------------------------------------------------
    # === AZIONE DI DOMINIO (Esecuzione) ===
    # ----------------------------------------------------------------------
    
    # Esempio di come potresti orchestrare l'azione di valutazione della policy:
    # 1. Valuta le policies rispetto all'input.
    # 2. Applica la logica di output.
    
    valuta_politiche: policies 
        | valuta_match # Funzione Python: filtra le regole in base a 'match'
        | valuta_condizione # Funzione Python: esegue la stringa 'condition' tramite MistQL
        | determina_verdetto; # Funzione Python: applica la logica finale 'output.logic'
        
    risultato_policy: valuta_politiche;
}