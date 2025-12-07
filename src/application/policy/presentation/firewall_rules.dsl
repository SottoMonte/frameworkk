{
    # ----------------------------------------------------------------------
    # --- 1. Dati Iniziali (Tentativo di Connessione) ---
    # ----------------------------------------------------------------------
    
    # Input: (IP Sorgente, Porta Destinazione, Protocollo)
    richiesta_connessione: ("192.168.1.10", 80, "TCP"); 
    
    # Regole costanti
    PORTA_HTTP: 80;
    PROTOCOLLO_CONSENTITO: "TCP";
    
    # ----------------------------------------------------------------------
    # --- 2. Logica di Business Definite nel DSL (Regole Booleane) ---
    # ----------------------------------------------------------------------
    
    # Funzione DSL: Applica la regola di base
    applica_regola_base:
        (string:ip, integer:porta, string:protocollo), 
        { 
            # MistQL: Verifica se la porta e il protocollo sono quelli consentiti
            # Il corpo valuta un'espressione booleana complessa.
            regola_passata: "porta == PORTA_HTTP && protocollo == PROTOCOLLO_CONSENTITO";
        }, 
        (string:ip, boolean:regola_passata); # Output: (IP, Risultato Booleano)
        
    # Funzione DSL: Determina l'azione finale (Consentita o Bloccata)
    determina_azione:
        (string:ip, boolean:regola_base),
        {
            # MistQL non supporta IF/ELSE in modo robusto, quindi usiamo un trucco logico
            # per produrre una stringa (richiede che MistQL possa fare un casting)
            # Qui si ipotizza che 'check_blacklist' sia stato eseguito prima se necessario
            
            # Se regola_base è vera: 'Permessa'
            azione_finale: "regola_base ? 'Permessa' : 'Bloccata'"; 
        },
        (string:ip, string:azione_finale); # Output: (IP, Azione)

    # ----------------------------------------------------------------------
    # --- 3. Azione di Dominio (Pipeline) ---
    # ----------------------------------------------------------------------
    
    valuta_richiesta: richiesta_connessione
        | check_blacklist # Funzione Python (verifica se l'IP è in lista nera)
        | applica_regola_base
        | determina_azione
        | log_azione # Funzione Python (registra l'azione finale)
        | print;
}