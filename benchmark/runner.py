#!/usr/bin/env python3
"""
notary score <memory_file.json>

Runs the Notary governance benchmark on a memory store export.

Input format (JSON):
{
  "facts": [ ... ],           # list of ProvenanceRecord dicts
  "authorities": [ ... ]      # optional list of WriteAuthority dicts
}

Or just a bare list of fact dicts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from benchmark.scoring import (
    cross_agent_conflict_score,
    governance_score,
    lifecycle_adherence_score,
    poisoning_resistance_score,
    provenance_coverage,
    stability_score,
)


RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def color_score(score: float) -> str:
    s = f"{score:.2f}"
    if score >= 0.95:
        return f"{GREEN}{BOLD}{s}{RESET}"
    elif score >= 0.75:
        return f"{YELLOW}{BOLD}{s}{RESET}"
    else:
        return f"{RED}{BOLD}{s}{RESET}"


def run(path: str) -> None:
    data = json.loads(Path(path).read_text())

    if isinstance(data, list):
        facts: List[Dict[str, Any]] = data
        authorities: List[Dict[str, Any]] = []
    else:
        facts = data.get("facts", [])
        authorities = data.get("authorities", [])

    gs, gov_violations  = governance_score(facts)
    ss, stab_violations = stability_score(facts, authorities)
    la, life_violations = lifecycle_adherence_score(facts)
    cc, conf_violations = cross_agent_conflict_score(facts, authorities)
    pr, pois_violations = poisoning_resistance_score(facts, authorities)
    pc                  = provenance_coverage(facts)

    print(f"\n{BOLD}{CYAN}Notary Benchmark Results{RESET}")
    print(f"{DIM}{'─' * 40}{RESET}")
    print(f"  Facts analyzed:        {BOLD}{len(facts)}{RESET}")
    print(f"  Governance score:      {color_score(gs)}")
    print(f"  Stability score:       {color_score(ss)}")
    print(f"  Lifecycle adherence:   {color_score(la)}")
    print(f"  Cross-agent conflicts: {color_score(cc)}")
    print(f"  Poisoning resistance:  {color_score(pr)}")
    print(f"  Provenance coverage:   {color_score(pc)}")
    print(f"{DIM}{'─' * 40}{RESET}")

    all_violations = (
        gov_violations + stab_violations + life_violations
        + conf_violations + pois_violations
    )
    if all_violations:
        print(f"\n{YELLOW}Issues found:{RESET}")
        for v in all_violations[:20]:
            print(f"  {DIM}!{RESET} {v}")
        if len(all_violations) > 20:
            print(f"  {DIM}... and {len(all_violations) - 20} more{RESET}")
    else:
        print(f"\n{GREEN}No violations found.{RESET}")

    print()

    if gs == 1.0 and ss == 1.0 and la == 1.0 and cc == 1.0 and pr == 1.0 and pc == 1.0:
        print(
            f"{GREEN}{BOLD}"
            "Perfect benchmark score. This snapshot passes Notary's current governance checks."
            f"{RESET}\n"
        )
    elif gs < 0.5 or ss < 0.5:
        print(f"{RED}Significant governance gaps detected. See CONTACT.md if you want help.{RESET}\n")
    else:
        print(f"{YELLOW}Room to improve. See CONTACT.md if you want Notary on your stack.{RESET}\n")


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] == "score":
        if len(args) < 2:
            print("Usage: notary score <memory_file.json>")
            sys.exit(1)
        run(args[1])
    else:
        # allow `notary <file>` shorthand
        run(args[0])


if __name__ == "__main__":
    main()
