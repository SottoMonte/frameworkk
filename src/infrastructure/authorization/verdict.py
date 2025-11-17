imports = {
    'persistence': 'framework/port/authorization.py',
}

class adapter(persistence.port):
    conn = None
    engine = None
    def __init__(self,**constants):
        self.config = constants['config'] 
        self._policies = {}
        self.load_policy()

    def _compile(self, policy_data: dict):
        """Converte la struttura Policy (YAML/JSON) in un formato più veloce da valutare."""
        # Logica di parsing e ottimizzazione
        return policy_data # placeholder
    
    def _evaluate_rule(self, rule: dict, context: dict) -> bool:
        """Valuta le condizioni di una singola regola rispetto al contesto."""
        # Logica che utilizza una libreria di valutazione espressioni (es. json-logic)
        # per risolvere espressioni come "input.user.role == 'admin'"
        return True # placeholder

    def load_policy(self, name: str, policy_data: dict):
        """Compila e carica una policy nel motore."""
        # policy_data è la struttura YAML/JSON letta
        compiled_policy = self._compile(policy_data)
        self._policies[name] = compiled_policy

    def check(self, policy_name: str, input_data: dict) -> bool:
        """
        Controlla l'accesso in base a una policy specifica e ai dati di input.
        Ritorna True (ALLOW) o False (DENY).
        """
        if policy_name not in self._policies:
            # Deny by default
            return False 

        policy = self._policies[policy_name]
        
        # Unisce l'input e i dati esterni per creare il contesto
        context = {"input": input_data, "data": self._data_store}
        
        # Itera sulle regole della policy e cerca un ALLOW
        for rule in policy['rules']:
            if self._evaluate_rule(rule, context):
                # Assumendo una logica 'First-match/Allow'
                return True 
                
        # Deny by default se nessuna regola ha fatto match
        return False
        