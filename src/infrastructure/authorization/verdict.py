imports = {
    #'persistence': 'framework/port/authorization.py',
}

import json
from typing import Dict, Any
import mistql # Motore di query sicuro
import asyncio
# La classe adapter gestisce il caricamento e la valutazione delle policy
class adapter():
    
    def __init__(self, **constants):
        self.config = constants
        self._policies: Dict[str, Dict] = {}
        self._data_store: Dict[str, Any] = {}

        # Caricamento iniziale dei dati e delle policy
        self._data_store = self.load_data_store()
        policy_data = self.load_policies()
        for name, policy in policy_data.items():
            self.load_policy(name, policy)


    # ------------------------------
    # POLICY COMPILATION & LOADING
    # ------------------------------

    def _compile(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Placeholder per la pre-elaborazione delle policy.
        """
        return policy_data

    def load_policy(self, name: str, policy_data: Dict[str, Any]):
        """Carica una policy pre-compilata nella memoria."""
        compiled_policy = self._compile(policy_data)
        self._policies[name] = compiled_policy

    # ------------------------------
    # POLICY EVALUATION (MistQL)
    # ------------------------------

    def _evaluate_rule(self, rule: Dict, context: Dict[str, Any]) -> bool:
        """
        Valuta una singola regola usando l'espressione MistQL contenuta in 'condition'.
        """
        effect = rule.get("effect", "deny")
        condition_mistql_string = rule.get("condition") 
        
        # 1. Gestione assenza condizione
        if condition_mistql_string is None:
            return effect == "allow"

        safe_context = context

        # ➤ DEBUG STEP: log condition before evaluation
        print("\n🧪 Evaluating Rule")
        print("Effect:", effect)
        print("Condition:", condition_mistql_string)
        print("Context:", json.dumps(safe_context, indent=2))

        # 2. Evaluation con MistQL
        try:
            # MistQL valuta l'espressione (stringa) sul dizionario di contesto (safe_context)
            result = mistql.query(condition_mistql_string, safe_context)
            
            print(f"➡️ Result: {result} (Type: {type(result).__name__})")
        except Exception as e:
            # Cattura errori di sintassi MistQL o errori di runtime
            print("\n❌ MISTQL EVALUATION ERROR")
            print("---------------------------------")
            print("Rule:", condition_mistql_string)
            print("Error:", str(e))
            print("---------------------------------\n")
            return False

        # 3. Restituisce il risultato della decisione
        return bool(result) and effect == "allow"

    def check(self, policy_name: str, input_data: Dict[str, Any]) -> bool:
        """
        Esegue la valutazione policy su un input. Ritorna True/False (first match allow).
        """
        if policy_name not in self._policies:
            return False

        # Crea il contesto completo unendo l'input e i dati di supporto
        context = {
            "input": input_data,
            "data": self._data_store,
        }

        for rule in self._policies[policy_name].get("rules", []):
            if self._evaluate_rule(rule, context):
                return True

        return False # Deny se nessuna regola 'allow' ha fatto match

    # ------------------------------
    # MOCK PERSISTENCE LAYER
    # ------------------------------

    def load_data_store(self) -> Dict[str, Any]:
        """Dati di supporto statici (es. limiti di abbonamento)."""
        return {
            "limits": {
                "free": {"max_download": 5},
                "premium": {"max_download": 999}
            }
        }

    async def load_policieee(self) -> Dict[str, Dict]:
        text = await language.fetch(path="application/policy/presentation/web.toml")
        ok = await language.convert(text,dict,'toml')
        print(ok)
        return ok
        

    def load_policies(self) -> Dict[str, Dict]:
        #language.fetch
        """Definizione delle policy (le condizioni sono stringhe MistQL)."""
        return {
            "document_access": {
                "rules": [
                    {
                        "effect": "allow",
                        # Regola 1: documento PUBBLICATO E utente PREMIUM
                        #"condition": 'input.resource.status == "PUBLISHED and true"'
                        "condition": '(input.resource.status == "PUBLISHED") && ((input.principal.roles | find @ == "premium") != null)'
                        #"condition": "(input.resource.status == \"PUBLISHED\") and (input.principal.roles | contains(\"premium\"))"
                    },
                    {
                        "effect": "deny",
                        # Regola 2 (Fallback Deny): sempre True, quindi blocca se la Regola 1 fallisce
                        "condition": "true" 
                    }
                ]
            }
        }