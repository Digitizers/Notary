"""
Notary Benchmark — scoring engine.

Takes a list of ProvenanceRecord dicts and produces four scores:

  governance_score           — fraction of facts with complete provenance
  stability_score            — fraction of PERMANENT authority checks that pass (default-deny)
  lifecycle_adherence_score  — fraction of in-snapshot overwrites that respect fact lifecycles
  provenance_coverage        — fraction of facts with agent_id + surface + lifecycle filled

Scores are 0.0–1.0. Higher is better.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Tuple


def _confidence_in_range(value: Any) -> bool:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return False
    return 0.0 <= confidence <= 1.0


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
        if conf is None or not _confidence_in_range(conf):
            issues.append(f"[{fact_id}] confidence out of range: {conf}")

        if issues:
            violations.extend(issues)
        else:
            passed += 1

    score = round(passed / len(facts), 4)
    return score, violations


def stability_score(facts: List[Dict[str, Any]], authorities: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """
    Checks PERMANENT facts for unauthorized overwrites, duplicate fact IDs,
    and writes without a covering WriteAuthority.

    Authority is default-deny: every PERMANENT fact must come from an agent
    registered in `authorities` whose allowed_surfaces covers the fact's
    surface. A snapshot that declares no authorities cannot score 1.0 if it
    contains permanent facts — an unverifiable write is treated as a failed
    check, not a passing one.

    An overwrite is authorized if:
      - The overwriting agent has can_overwrite=True in their WriteAuthority
      - AND the surface is in their allowed_surfaces

    Duplicate permanent fact IDs are flagged as possible undeclared overwrites,
    because a single snapshot cannot otherwise prove the write history.

    Returns (score, list_of_violation_messages).
    """
    permanent_facts = [f for f in facts if f.get("lifecycle") == "permanent"]
    permanent_overwrites = [f for f in permanent_facts if f.get("overwrite_of")]
    permanent_ids = [
        f.get("fact_id")
        for f in permanent_facts
        if f.get("fact_id")
    ]
    duplicate_ids = sorted(
        fact_id for fact_id, count in Counter(permanent_ids).items()
        if count > 1
    )

    auth_map = {
        a["agent_id"]: a
        for a in authorities
        if a.get("agent_id")
    }
    # Default deny: a permanent fact that is not a declared overwrite still
    # needs a registered WriteAuthority covering its surface. Declared
    # overwrites are excluded here — the overwrite loop below already fails
    # them on the same grounds.
    unauthorized_writes = []
    for f in permanent_facts:
        if f.get("overwrite_of"):
            continue
        fact_id = f.get("fact_id", "<unknown>")
        agent_id = f.get("agent_id", "")
        auth = auth_map.get(agent_id)
        if auth is None:
            unauthorized_writes.append(
                f"[{fact_id}] agent '{agent_id}' has no WriteAuthority — permanent write is unverifiable (default deny)"
            )
        elif f.get("surface", "") not in auth.get("allowed_surfaces", []):
            unauthorized_writes.append(
                f"[{fact_id}] agent '{agent_id}' not authorized for surface '{f.get('surface', '')}' — permanent write denied (default deny)"
            )

    if not permanent_overwrites and not duplicate_ids and not unauthorized_writes:
        return 1.0, []

    violations = []
    authorized = 0

    for fact_id in duplicate_ids:
        violations.append(
            f"[{fact_id}] duplicate permanent fact_id — possible undeclared overwrite"
        )

    violations.extend(unauthorized_writes)

    for f in permanent_overwrites:
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

    total_checks = len(permanent_overwrites) + len(duplicate_ids) + len(unauthorized_writes)
    score = round(authorized / total_checks, 4) if total_checks else 1.0
    return score, violations


def lifecycle_adherence_score(facts: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """
    Checks that overwrites respect fact lifecycles, for every overwrite whose
    target fact is present in the snapshot:

      - A session-scoped fact must not be overwritten from a different
        session — that means it outlived its session boundary.
      - An overwrite must not escalate lifecycle: replacing a session or
        volatile fact with a permanent one silently promotes unvetted
        content to permanent memory.

    Overwrites whose target is not in the snapshot are not counted — a
    single snapshot cannot check what it cannot see.

    Returns (score, list_of_violation_messages).
    """
    by_id = {f.get("fact_id"): f for f in facts if f.get("fact_id")}

    violations = []
    passed = 0
    total_checks = 0

    for f in facts:
        target = by_id.get(f.get("overwrite_of"))
        if target is None:
            continue

        fact_id = f.get("fact_id", "<unknown>")
        issues = []

        if (
            target.get("lifecycle") == "session"
            and f.get("session_id") != target.get("session_id")
        ):
            issues.append(
                f"[{fact_id}] overwrites session-scoped fact"
                f" '{target.get('fact_id')}' from a different session —"
                " session boundary crossed"
            )
        if (
            f.get("lifecycle") == "permanent"
            and target.get("lifecycle") in ("session", "volatile")
        ):
            issues.append(
                f"[{fact_id}] permanent overwrite of"
                f" {target.get('lifecycle')} fact '{target.get('fact_id')}' —"
                " lifecycle escalation"
            )

        total_checks += 1
        if issues:
            violations.extend(issues)
        else:
            passed += 1

    score = round(passed / total_checks, 4) if total_checks else 1.0
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
