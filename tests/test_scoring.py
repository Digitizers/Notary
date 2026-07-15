import unittest

from benchmark.scoring import governance_score, lifecycle_adherence_score, stability_score


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

    def test_stability_denies_permanent_write_by_unregistered_agent(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", agent_id="agent-rogue"),
        ], authorities=[{
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": True,
        }])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("unverifiable (default deny)" in violation for violation in violations))

    def test_stability_denies_permanent_facts_when_no_authorities_declared(self):
        score, violations = stability_score([
            valid_fact(fact_id="f001"),
            valid_fact(fact_id="f002", session_id="sess-002"),
        ], authorities=[])

        self.assertEqual(score, 0.0)
        self.assertEqual(len(violations), 2)

    def test_stability_denies_permanent_write_on_disallowed_surface(self):
        score, violations = stability_score([
            valid_fact(fact_id="f002", surface="task_state"),
        ], authorities=[{
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": True,
        }])

        self.assertEqual(score, 0.0)
        self.assertTrue(any(
            "not authorized for surface 'task_state' — permanent write denied (default deny)" in violation
            for violation in violations
        ))

    def test_stability_allows_registered_non_overwrite_permanent_write(self):
        score, violations = stability_score([
            valid_fact(fact_id="f001"),
        ], authorities=[{
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": False,
        }])

        self.assertEqual(score, 1.0)
        self.assertEqual(violations, [])

    def test_stability_ignores_non_permanent_facts_from_unregistered_agents(self):
        score, violations = stability_score([
            valid_fact(fact_id="f001", lifecycle="session", agent_id="agent-rogue"),
            valid_fact(fact_id="f002", lifecycle="volatile", agent_id="agent-rogue"),
        ], authorities=[])

        self.assertEqual(score, 1.0)
        self.assertEqual(violations, [])

    def test_stability_scores_rogue_write_proportionally(self):
        authority = {
            "agent_id": "agent-preferences",
            "allowed_surfaces": ["user_profile"],
            "can_overwrite": False,
        }
        score, violations = stability_score([
            valid_fact(fact_id="f001"),
            valid_fact(fact_id="f002"),
            valid_fact(fact_id="f003"),
            valid_fact(fact_id="f004", agent_id="agent-rogue"),
        ], authorities=[authority])

        self.assertEqual(score, 0.75)
        self.assertEqual(len(violations), 1)

    def test_lifecycle_flags_cross_session_overwrite_of_session_fact(self):
        score, violations = lifecycle_adherence_score([
            valid_fact(fact_id="f001", lifecycle="session", session_id="sess-001"),
            valid_fact(
                fact_id="f002",
                lifecycle="session",
                session_id="sess-002",
                overwrite_of="f001",
            ),
        ])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("session boundary crossed" in violation for violation in violations))

    def test_lifecycle_flags_permanent_overwrite_of_session_fact_as_escalation(self):
        score, violations = lifecycle_adherence_score([
            valid_fact(fact_id="f001", lifecycle="volatile"),
            valid_fact(fact_id="f002", lifecycle="permanent", overwrite_of="f001"),
        ])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("lifecycle escalation" in violation for violation in violations))

    def test_lifecycle_allows_same_session_and_same_lifecycle_overwrites(self):
        score, violations = lifecycle_adherence_score([
            valid_fact(fact_id="f001"),
            valid_fact(fact_id="f002", overwrite_of="f001"),
            valid_fact(fact_id="f003", lifecycle="session"),
            valid_fact(fact_id="f004", lifecycle="session", overwrite_of="f003"),
        ])

        self.assertEqual(score, 1.0)
        self.assertEqual(violations, [])

    def test_lifecycle_checks_overwrite_that_reuses_the_same_fact_id(self):
        score, violations = lifecycle_adherence_score([
            valid_fact(fact_id="f001", lifecycle="session", session_id="sess-001"),
            valid_fact(
                fact_id="f001",
                lifecycle="permanent",
                session_id="sess-002",
                overwrite_of="f001",
            ),
        ])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("session boundary crossed" in violation for violation in violations))
        self.assertTrue(any("lifecycle escalation" in violation for violation in violations))

    def test_lifecycle_does_not_check_overwrites_against_later_records(self):
        score, violations = lifecycle_adherence_score([
            valid_fact(
                fact_id="f001",
                lifecycle="session",
                session_id="sess-001",
                timestamp="2026-05-01T09:00:00Z",
            ),
            valid_fact(
                fact_id="f001",
                lifecycle="session",
                session_id="sess-001",
                overwrite_of="f001",
                timestamp="2026-05-01T10:00:00Z",
            ),
            valid_fact(
                fact_id="f001",
                lifecycle="session",
                session_id="sess-002",
                overwrite_of="f001",
                timestamp="2026-05-01T11:00:00Z",
            ),
        ])

        # The same-session update must not be penalized for the later
        # cross-session record; only the cross-session update fails, and it
        # is checked against both prior records.
        self.assertEqual(score, 0.5)
        self.assertEqual(len(violations), 2)
        self.assertTrue(all("session boundary crossed" in v for v in violations))

    def test_lifecycle_orders_records_by_parsed_time_across_utc_offsets(self):
        # 10:00+02:00 is 08:00Z — earlier than the 09:30Z overwrite even
        # though it sorts later lexicographically.
        score, violations = lifecycle_adherence_score([
            valid_fact(
                fact_id="f001",
                lifecycle="session",
                session_id="sess-001",
                timestamp="2026-05-01T10:00:00+02:00",
            ),
            valid_fact(
                fact_id="f002",
                lifecycle="session",
                session_id="sess-002",
                overwrite_of="f001",
                timestamp="2026-05-01T09:30:00Z",
            ),
        ])

        self.assertEqual(score, 0.0)
        self.assertTrue(any("session boundary crossed" in violation for violation in violations))

    def test_lifecycle_ignores_overwrites_of_facts_outside_the_snapshot(self):
        score, violations = lifecycle_adherence_score([
            valid_fact(fact_id="f002", overwrite_of="f-not-here"),
        ])

        self.assertEqual(score, 1.0)
        self.assertEqual(violations, [])

    def test_gaming_vector_is_flagged(self):
        import json
        from pathlib import Path

        data = json.loads(
            (Path(__file__).parent / "gaming_vector.json").read_text()
        )
        score, violations = stability_score(
            data.get("facts", []), data.get("authorities", [])
        )

        self.assertLess(score, 1.0)
        self.assertGreater(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
