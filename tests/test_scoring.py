import unittest

from benchmark.scoring import governance_score, stability_score


def valid_fact(**overrides):
    fact = {
        "fact_id": "f001",
        "content": "User prefers concise answers.",
        "agent_id": "agent-preferences",
        "session_id": "sess-001",
        "timestamp": "2026-05-01T09:12:00Z",
        "surface": "user_profile",
        "lifecycle": "permanent",
        "confidence": 0.95,
        "overwrite_of": None,
    }
    fact.update(overrides)
    return fact


class ScoringTests(unittest.TestCase):
    def test_governance_rejects_non_numeric_confidence_without_crashing(self):
        score, violations = governance_score([
            valid_fact(confidence="high"),
        ])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("confidence out of range" in violation for violation in violations))

    def test_stability_denies_missing_authority_for_declared_overwrite(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", overwrite_of="f001"),
        ], authorities=[])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("has no WriteAuthority" in violation for violation in violations))

    def test_stability_flags_duplicate_permanent_fact_id_as_possible_undeclared_overwrite(self):
        score, violations = stability_score([
            valid_fact(fact_id="f001", content="Original preference."),
            valid_fact(fact_id="f001", content="Changed preference.", session_id="sess-002"),
        ], authorities=[])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("duplicate permanent fact_id" in violation for violation in violations))

    def test_stability_ignores_malformed_authority_without_crashing(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", overwrite_of="f001"),
        ], authorities=[{"allowed_surfaces": ["user_profile"], "can_overwrite": True}])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("has no WriteAuthority" in violation for violation in violations))

    def test_stability_allows_authorized_overwrite(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", overwrite_of="f001"),
        ], authorities=[{
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": True,
        }])

        self.assertEqual(score, 1.0)
        self.assertEqual(violations, [])

    def test_stability_rejects_unauthorized_surface(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", surface="task_state", overwrite_of="f001"),
        ], authorities=[{
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": True,
        }])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("not authorized for surface" in violation for violation in violations))

    def test_stability_rejects_agent_without_overwrite_permission(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", overwrite_of="f001"),
        ], authorities=[{
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": False,
        }])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("overwrite not permitted" in violation for violation in violations))


if __name__ == "__main__":
    unittest.main()
