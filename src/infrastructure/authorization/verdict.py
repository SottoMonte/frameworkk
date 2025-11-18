imports = {
    #'persistence': 'framework/port/authorization.py',
}

from json_logic import jsonLogic
from typing import Dict, Any
import json


#authorization.port
class adapter():
    def __init__(self, **constants):
        self.config = constants
        self._policies: Dict[str, Dict] = {}
        self._data_store: Dict[str, Any] = {}

        # Caricamento iniziale
        self._data_store = self.load_data_store()
        policy_data = self.load_policies()
        for name, policy in policy_data.items():
            self.load_policy(name, policy)

    # ------------------------------
    # POLICY COMPILATION & LOADING
    # ------------------------------

    def _compile(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess policies for faster evaluation.
        Esempio: normalizzazione campi, precompilazione espressioni, validazione sintattica.
        """
        # Placeholder per trasformazioni: regex pre-compile, caching attr maps, ecc.
        return policy_data

    def load_policy(self, name: str, policy_data: Dict[str, Any]):
        compiled_policy = self._compile(policy_data)
        self._policies[name] = compiled_policy

    # ------------------------------
    # POLICY EVALUATION
    # ------------------------------

    def _evaluate_rule2(self, rule: Dict, context: Dict[str, Any]) -> bool:
        """
        Valuta una singola regola usando jsonlogic.
        La regola deve avere forma:

        {
          "effect": "allow",
          "condition": { "==": [ {"var": "input.user.role"}, "admin" ] }
        }
        """
        def normalize(value):
            if isinstance(value, dict):
                return {str(k): normalize(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [normalize(v) for v in value]
            if hasattr(value, "keys") and not isinstance(value, dict):  # dict_keys, dict_values
                return [normalize(v) for v in list(value)]
            return value
        effect = rule.get("effect", "deny")
        condition = rule.get("condition")

        # Se non c'è condizione, si interpreta come "match sempre"
        if condition is None:
            return effect == "allow"

        # Valuta la condizione dinamicamente sul contesto
        try:
            result = jsonLogic(condition, normalize(context))
        except Exception as e:
            print(f"[POLICY ERROR] Condition evaluation failed: {e}")
            return False
        
        # Restituisce match valido
        return result and effect == "allow"

    def _evaluate_rule(self, rule: Dict, context: Dict[str, Any]) -> bool:
        """
        Valuta una singola regola usando jsonlogic, con debug avanzato per errori.
        """

        # Normalizzazione JSON-safe
        def normalize(value):
            try:
                # clone via JSON serialize/deserialize → garantisce struttura valida
                return json.loads(json.dumps(value))
            except Exception:
                # fallback manuale in caso di oggetti non serializzabili in prima passata
                if isinstance(value, dict):
                    return {str(k): normalize(v) for k, v in value.items()}
                if isinstance(value, (list, tuple, set)):
                    return [normalize(v) for v in value]
                if hasattr(value, "keys"):
                    return normalize(list(value))  # dict_keys, dict_values
                return value

        effect = rule.get("effect", "deny")
        condition = rule.get("condition")

        # No condition -> auto-match
        if condition is None:
            return effect == "allow"

        # Context normalized
        safe_context = normalize(context)

        # ➤ DEBUG STEP: validate JSON serializability
        try:
            json.dumps(safe_context)
        except Exception as e:
            print("\n❌ CONTEXT JSON SERIALIZATION ERROR")
            print("---------------------------------")
            print("Rule ID:", rule.get("id", "<no-id>"))
            print("Context object:", safe_context)
            print("Reason:", str(e))
            print("---------------------------------\n")
            return False

        # ➤ DEBUG STEP: log condition before evaluation
        print("\n🧪 Evaluating Rule")
        print("Effect:", effect)
        print("Condition:", json.dumps(condition, indent=2))
        print("Context:", json.dumps(safe_context, indent=2))

        # 🔥 Evaluation with traced exception
        try:
            result = jsonLogic(condition, safe_context)
            print("➡️ Result:", result)
        except Exception as e:
            print("\n❌ JSONLOGIC EVALUATION ERROR")
            print("---------------------------------")
            print("Rule:", json.dumps(rule, indent=2))
            print("Context:", json.dumps(safe_context, indent=2))
            print("Error:", str(e))
            print("---------------------------------\n")
            return False

        return result and effect == "allow"

    def check(self, policy_name: str, input_data: Dict[str, Any]) -> bool:
        """
        Esegue la valutazione policy su un input. Ritorna True/False.
        Supporta il modello "first match allow".
        """
        if policy_name not in self._policies:
            return False  # default deny

        context = {
            "input": input_data,
            "data": self._data_store,
        }

        for rule in self._policies[policy_name].get("rules", []):
            if self._evaluate_rule(rule, context):
                return True

        return False  # deny if no rule matched

    # ------------------------------
    # MOCK PERSISTENCE LAYER
    # ------------------------------

    def load_data_store(self) -> Dict[str, Any]:
        """Mock opzionale per consentire test immediati."""
        return {
            "limits": {
                "free": {"max_download": 5},
                "premium": {"max_download": 999}
            }
        }

    def load_policies(self) -> Dict[str, Dict]:
        """Mock: in produzione si caricherebbe da file, DB o API."""
        return {
            "document_access": {
                "rules": [
                    {
                        "effect": "allow",
                        "condition": {
                            "and": [
                                {"==": ["PUBLISHED", "PUBLISHED"]},
                                #{"==": [{"var": "input.resource.status"}, "PUBLISHED"]},
                            ]
                        }
                    },
                    {
                        "effect": "allow",
                        "condition": {
                            "==": ["PUBLISHED", "PUBLISHED"],
                        }
                    }
                ]
            }
        }