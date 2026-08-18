"""signetry-reviewer — an advisory PR reviewer that surfaces architecture + security
issues, cross-verifies them against deterministic gates, and recommends whether a
change is safe to merge, needs a human, or should be blocked.

Safety model: the reviewer is ADVISORY. It never merges on its own judgement. The
merge authority is the deterministic gate (a required status check + a clean
secret scan + no forbidden permission change) plus a human. Auto-merge is opt-in,
off by default, and only ever fires when those deterministic gates are green.
"""
from __future__ import annotations

from .checks import changed_files, run_all_deterministic
from .model import Category, Finding, GateReport, Review, Severity, Verdict
from .render import render_comment
from .verdict import DEFAULT_SENSITIVE_GLOBS, decide, eligible_for_auto_merge


def review_diff(
    diff: str,
    *,
    repo: str,
    pr_number: int | None = None,
    required_check: str = "unknown",
    protected_globs: tuple[str, ...] = (),
    sensitive_globs: tuple[str, ...] = DEFAULT_SENSITIVE_GLOBS,
    extra_findings: list[Finding] | None = None,
    require_gate: bool = True,
) -> Review:
    """Run the full advisory review over a unified ``diff``.

    ``required_check`` is the status of the repo's required check from the GitHub
    API. ``extra_findings`` lets an optional model pass contribute advisory items
    (they are merged in but can never relax the deterministic verdict).
    """
    findings = run_all_deterministic(diff, protected_globs=protected_globs)
    for f in (extra_findings or []):
        # Anything supplied via the model/external channel is ADVISORY by force:
        # we unconditionally tag it as model-sourced and strip any blocking flag, so
        # an external finding can never masquerade as a deterministic blocking signal
        # nor influence the deterministic gate. (Deterministic scanners are the only
        # source of blocking findings and of the gate report below.)
        f.source = "model"
        f.blocking = False
        findings.append(f)

    changed = changed_files(diff)

    # Build the deterministic gate report from the findings we just computed.
    # secret_scan_clean keys off a *blocking* secret (a real leak); a flagged
    # placeholder in a test/fixture file is surfaced but does not fail the gate.
    secret_clean = not any(f.id == "secret.introduced" and f.blocking for f in findings)
    perm_ok = not any(f.blocking and f.id.startswith("ci.") for f in findings)
    # Same rule as secret_scan_clean above: this gate keys off a *blocking* skew.
    # A lockfile-only change is a review signal, not a merge blocker — audit-fix
    # and Dependabot refreshes are exactly that shape, and a failed gate means
    # verdict=BLOCK / "not mergeable until resolved", which would reject them all.
    dep_ok = not any(f.id == "supply.dependency_skew" and f.blocking for f in findings)
    gates = GateReport(
        required_check=required_check,
        secret_scan_clean=secret_clean,
        no_forbidden_perm_change=perm_ok,
        dependency_skew_ok=dep_ok,
    )

    review = Review(repo=repo, pr_number=pr_number, findings=findings, gates=gates)
    return decide(review, changed=changed, sensitive_globs=sensitive_globs, require_gate=require_gate)


__all__ = [
    "DEFAULT_SENSITIVE_GLOBS",
    "Category",
    "Finding",
    "GateReport",
    "Review",
    "Severity",
    "Verdict",
    "eligible_for_auto_merge",
    "render_comment",
    "review_diff",
]
