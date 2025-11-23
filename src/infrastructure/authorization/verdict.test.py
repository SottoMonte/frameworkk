imports = {
    'verdict': 'infrastructure/authorization/verdict.py',
    'contract': 'framework/service/contract.py',
}

exports = {
    'adapter': 'adapter',
}

class Testadapter(contract.Contract):

    async def test_check(self):
        import infrastructure.authorization.verdict as verdict
        engine = verdict.adapter(config={'project':{'policy':
            {'presentation':'web.toml'}
        }})
        await engine.load_policies()
        request_allow = {
            "principal": {
                "id": "user-101",
                "roles": ["premium"]
            },
            "resource": {
                "id": "doc-456",
                "status": "PUBLISHED",
                "owner_id": "user-202"
            }
        }

        request_deny = {
             "principal": {
                "id": "user-101",
                "roles": ["guest"] # Role not allowed presumably
            },
            "resource": {
                "id": "doc-456",
                "status": "DRAFT", # Status not allowed presumably
                "owner_id": "user-202"
            }
        }

        success = [
            {'args':("rule-1-read-published", request_allow), 'equal':True},
            # Assuming there is a case that returns False, but let's stick to what we know works or is expected.
            # If the policy returns False for deny, we can add it.
            # Based on verdict.py: return bool(result) and effect == "allow" -> so if it fails it returns False.
            {'args':("rule-1-read-published", request_deny), 'equal':False},
        ]

        failure = [
            {'args':("non-existent-policy", request_allow), 'error': Exception},
        ]

        await self.check_cases(engine.check, success + failure)

    async def test_load_policy(self):
        pass

    async def test_load_policies(self):
        pass