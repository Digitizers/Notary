"""
Notary Benchmark — scoring engine.

Takes a list of ProvenanceRecord dicts and produces three scores:

  governance_score      — fraction of facts with complete provenance
  stability_score       — fraction of PERMANENT facts never overwritten without authority
  provenance_coverage   — fraction of facts with agent_id + surface + lifecycle filled

Scores are 0.0–1.0. Higher is better.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def governance_score(facts: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """
    A fact passes governance if it has:
      - agent_id
      - session_id
      - surface
      - lifecycle (valid value)
      - confidence between 0.0 and 1.0
      - timestamp (non-empty)

    Returns (score, list_of_violation_messages).
    """
    if not facts:
        return 0.0, ["No facts provided"]

    violations = []
    passed = 0
    valid_lifecycles = {"permanent", "session", "volatile"}

    for f in facts:
        fact_id = f.get("fact_id", "<unknown>")
        issues = []

        if not f.get("agent_id"):
            issues.append(f"[{fact_id}] missing agent_id")
        if not f.get("session_id"):
            issues.append(f"[{fact_id}] missing session_id")
        if not f.get("surface"):
            issues.append(f"[{fact_id}] missing surface")
        if not f.get("timestamp"):
            issues.append(f"[{fact_id}] missing timestamp")

        lc = f.get("lifecycle", "")
        if lc not in valid_lifecycles:
            issues.append(f"[{fact_id}] invalid lifecycle '{lc}' (expected: permanent/session/volatile)")

        conf = f.get("confidence")
        if conf is None or not (0.0 <= float(conf) <= 1.0):
            issues.append(f"[{fact_id}] confidence out of range: {conf}")

        if issues:
            violations.extend(issues)
        else:
            passed += 1

    score = round(passed / len(facts), 4)
    return score, violations


def stability_score(facts: List[Dict[str, Any]], authorities: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """
    Checks PERMANENT facts for unauthorized overwrites.

    An overwrite is authorized if:
      - The overwriting agent has can_overwrite=True in their WriteAuthority
      - AND the surface is in their allowed_surfaces

    Returns (score, list_of_violation_messages).
    """
    permanent = [f for f in facts if f.get("lifecycle") == "permanent" and f.get("overwrite_of")]
    if not permanent:
        return 1.0, []

    auth_map = {a["agent_id"]: a for a in authorities}
    violations = []
    authorized = 0

    for f in permanent:
        agent_id = f.get("agent_id", "")
        surface = f.get("surface", "")
        fact_id = f.get("fact_id", "<unknown>")

        auth = auth_map.get(agent_id)
        if not auth:
            violations.append(f"[{fact_id}] agent '{agent_id}' has no WriteAuthority — unauthorized overwrite")
            continue
        if not auth.get("can_overwrite"):
            violations.append(f"[{fact_id}] agent '{agent_id}' overwrite not permitted")
            continue
        if surface not in auth.get("allowed_surfaces", []):
            violations.append(f"[{fact_id}] agent '{agent_id}' not authorized for surface '{surface}'")
            continue

        authorized += 1

    score = round(authorized / len(permanent), 4) if permanent else 1.0
    return score, violations


def provenance_coverage(facts: List[Dict[str, Any]]) -> float:
    """Fraction of facts with all three core provenance fields present."""
    if not facts:
        return 0.0
    covered = sum(
        1 for f in facts
        if f.get("agent_id") and f.get("surface") and f.get("lifecycle")
    )
    return round(covered / len(facts), 4)
