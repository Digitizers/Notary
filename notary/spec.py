"""
Notary — Governance interfaces for multi-agent memory systems.

These are the core abstractions. Implementation is production-only.
The benchmark runner (benchmark/runner.py) accepts any memory store
that produces ProvenanceRecord objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Protocol, runtime_checkable


class FactLifecycle(str, Enum):
    """How long a fact should live in the memory store."""

    PERMANENT = "permanent"   # survives across all sessions, never auto-expired
    SESSION = "session"       # scoped to a single agent session, then dropped
    VOLATILE = "volatile"     # can be overwritten freely, no provenance required


@dataclass
class ProvenanceRecord:
    """Full audit trail for a single fact written to memory."""

    fact_id: str
    content: str
    agent_id: str
    session_id: str
    timestamp: str                          # ISO-8601
    surface: str                            # e.g. "user_profile", "task_state"
    lifecycle: FactLifecycle
    confidence: float = 1.0                 # 0.0–1.0, agent self-reported
    overwrite_of: str | None = None         # fact_id of the record this replaces
    tags: List[str] = field(default_factory=list)


@dataclass
class WriteAuthority:
    """Declares what a given agent is allowed to write and where."""

    agent_id: str
    allowed_surfaces: List[str]
    can_overwrite: bool = False             # must be True to replace an existing fact
    max_confidence_claim: float = 1.0      # agent cannot self-report above this


@runtime_checkable
class NotaryProtocol(Protocol):
    """
    The interface any Notary implementation must satisfy.

    Implementations are not included in this repository.
    If you want Notary running on your production agent stack — see CONTACT.md.
    """

    def validate_write(
        self,
        agent: WriteAuthority,
        surface: str,
        overwriting: bool = False,
    ) -> bool:
        """Return True if this agent is allowed to write to this surface."""
        ...

    def record_provenance(self, fact: ProvenanceRecord) -> str:
        """Persist a provenance record. Returns the stored fact_id."""
        ...

    def compute_governance_score(self, facts: List[ProvenanceRecord]) -> float:
        """
        0.0–1.0. Measures what fraction of facts have complete, valid provenance.
        A score of 1.0 means every fact is traceable to an authorized agent write.
        """
        ...

    def compute_stability_score(self, facts: List[ProvenanceRecord]) -> float:
        """
        0.0–1.0. Measures resistance to uncontrolled overwrites.
        A score of 1.0 means no PERMANENT fact was overwritten without explicit authority.
        """
        ...
