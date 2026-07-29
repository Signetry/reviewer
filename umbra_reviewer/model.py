"""The reviewer's result model — findings, the deterministic-gate report, and the
merge-safety verdict.

Design invariant (mirrors Umbra's own governance): the reviewer is ADVISORY. Its
LLM/heuristic findings never *grant* merge authority. Authority to merge comes
only from **deterministic gates** — the required status check, a clean secret
scan, no forbidden permission/OIDC change — cross-verified here. A human (or a
required check) is always the real gate; ``auto_merge`` is opt-in, off by default,
and only ever true when the deterministic gates are green AND no blocking finding
is present. The bot never approves on its own judgement alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# Ordered by severity so a scan's worst finding drives the verdict.
class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class Category(str, Enum):
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    SUPPLY_CHAIN = "supply_chain"
    INJECTION = "injection"
    QUALITY = "quality"


@dataclass
class Finding:
    """One issue the reviewer raises. ``blocking`` means it must be resolved before
    the change can be considered mergeable at all — but a blocking finding still
    only *withholds* the safe verdict; it never merges or grants anything."""

    id: str
    category: Category
    severity: Severity
    title: str
    detail: str
    file: str | None = None
    line: int | None = None
    remediation: str | None = None
    blocking: bool = False
    # Where the signal came from, so a reader can weigh it (deterministic > model).
    source: str = "deterministic"  # "deterministic" | "model" | "cross-check"

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "file": self.file,
            "line": self.line,
            "remediation": self.remediation,
            "blocking": self.blocking,
            "source": self.source,
        }


class Verdict(str, Enum):
    SAFE = "safe"                    # deterministic gates green + no blocking finding
    NEEDS_HUMAN = "needs_human"      # non-blocking concerns, or gates unproven → a human decides
    BLOCK = "block"                  # a blocking finding or a failed deterministic gate
    THIRD_PARTY = "third_party"      # sensitive surface touched → escalate to a designated reviewer


@dataclass
class GateReport:
    """The DETERMINISTIC signals the verdict is actually built on — never the model.

    ``required_check`` is the status of the repo's required check (e.g. the Umbra
    Admission action) as reported by the GitHub API. ``secret_scan_clean`` and
    ``no_forbidden_perms`` come from this package's deterministic scanners.
    """

    required_check: str = "unknown"   # "success" | "failure" | "pending" | "missing" | "unknown"
    secret_scan_clean: bool = True
    no_forbidden_perm_change: bool = True
    dependency_skew_ok: bool = True

    @property
    def all_green(self) -> bool:
        return (
            self.required_check == "success"
            and self.secret_scan_clean
            and self.no_forbidden_perm_change
            and self.dependency_skew_ok
        )

    def to_public(self) -> dict[str, Any]:
        return {
            "required_check": self.required_check,
            "secret_scan_clean": self.secret_scan_clean,
            "no_forbidden_perm_change": self.no_forbidden_perm_change,
            "dependency_skew_ok": self.dependency_skew_ok,
            "all_green": self.all_green,
        }


@dataclass
class Review:
    repo: str
    pr_number: int | None
    findings: list[Finding] = field(default_factory=list)
    gates: GateReport = field(default_factory=GateReport)
    verdict: Verdict = Verdict.NEEDS_HUMAN
    verdict_reason: str = ""
    sensitive_paths: list[str] = field(default_factory=list)
    auto_merge_eligible: bool = False

    @property
    def worst_severity(self) -> Severity:
        if not self.findings:
            return Severity.INFO
        return max((f.severity for f in self.findings), key=lambda s: s.rank)

    @property
    def blocking_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking]

    def to_public(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "pr_number": self.pr_number,
            "verdict": self.verdict.value,
            "verdict_reason": self.verdict_reason,
            "worst_severity": self.worst_severity.value,
            "findings": [f.to_public() for f in self.findings],
            "finding_count": len(self.findings),
            "blocking_count": len(self.blocking_findings),
            "gates": self.gates.to_public(),
            "sensitive_paths": list(self.sensitive_paths),
            "auto_merge_eligible": self.auto_merge_eligible,
            # Stated in the payload so it can't be quietly dropped: the bot never
            # merges on model judgement; deterministic gates are the authority.
            "advisory": True,
        }
