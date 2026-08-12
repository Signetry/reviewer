"""Cross-verification + the merge-safety verdict.

This is the heart of the safety model. It takes the deterministic findings and
the deterministic gate report and decides a verdict — WITHOUT ever letting a
model/heuristic finding *grant* mergeability. The rules, in order:

  BLOCK        if any finding is blocking, OR a deterministic gate failed.
  THIRD_PARTY  if a sensitive/protected surface was touched (needs a designated
               human reviewer), unless already BLOCKed.
  SAFE         only if the deterministic gates are ALL green AND there is no
               blocking finding AND nothing sensitive was touched.
  NEEDS_HUMAN  everything else (the honest default — a human decides).

Auto-merge eligibility is stricter still and is computed here, never by the model.
"""
from __future__ import annotations

import fnmatch

from .model import Review, Severity, Verdict

# Paths whose change always escalates to a designated reviewer (third party),
# regardless of how clean the diff looks. Security-sensitive by default.
DEFAULT_SENSITIVE_GLOBS = (
    ".github/workflows/*",
    ".github/actions/**",
    "**/Dockerfile",
    "Dockerfile",
    "**/*deploy*",
    "**/auth/**",
    "**/security/**",
    "**/*.pem",
    "**/settings.py",
    "**/secrets*",
)


def _touched_sensitive(files: list[str], globs: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for f in files:
        for g in globs:
            if fnmatch.fnmatch(f, g):
                hits.append(f)
                break
    return sorted(set(hits))


def decide(
    review: Review,
    *,
    changed: list[str],
    sensitive_globs: tuple[str, ...] = DEFAULT_SENSITIVE_GLOBS,
    require_gate: bool = True,
) -> Review:
    """Compute ``review.verdict`` / ``verdict_reason`` / ``auto_merge_eligible``
    from the (already-populated) findings + gates. Deterministic and honest."""
    review.sensitive_paths = _touched_sensitive(changed, sensitive_globs)
    gates = review.gates
    blocking = review.blocking_findings

    # 1. BLOCK — a hard finding or a failed deterministic gate.
    gate_failures = []
    if not gates.secret_scan_clean:
        gate_failures.append("secret scan flagged a credential")
    if not gates.no_forbidden_perm_change:
        gate_failures.append("a forbidden CI permission/OIDC change")
    if not gates.dependency_skew_ok:
        gate_failures.append("a risky dependency version skew")
    if require_gate and gates.required_check == "failure":
        gate_failures.append("the required status check failed")

    if blocking or gate_failures:
        review.verdict = Verdict.BLOCK
        parts = []
        if blocking:
            parts.append(f"{len(blocking)} blocking finding(s): " + ", ".join(f.title for f in blocking[:3]))
        if gate_failures:
            parts.append("; ".join(gate_failures))
        review.verdict_reason = "Blocked — " + " · ".join(parts) + ". Not mergeable until resolved."
        review.auto_merge_eligible = False
        return review

    # 2. THIRD_PARTY — sensitive surface touched; a designated human must review.
    if review.sensitive_paths:
        review.verdict = Verdict.THIRD_PARTY
        review.verdict_reason = (
            "Escalate to a designated reviewer — this PR touches security-sensitive "
            f"surface ({', '.join(review.sensitive_paths[:4])}). No blocking issue was "
            "found automatically, but a human owner should sign off."
        )
        review.auto_merge_eligible = False
        return review

    # 3. SAFE — only when deterministic gates are ALL green and nothing sensitive.
    if gates.all_green and not blocking:
        review.verdict = Verdict.SAFE
        worst = review.worst_severity
        note = "" if worst == Severity.INFO else f" ({len(review.findings)} non-blocking note(s) to consider)"
        review.verdict_reason = (
            "Deterministic gates are green (required check passed, no secrets, no "
            f"forbidden permission change) and no blocking issue was found{note}. "
            "A human still merges."
        )
        # Auto-merge eligibility (computed ONLY from deterministic signals):
        review.auto_merge_eligible = gates.all_green and not blocking and worst.rank <= Severity.LOW.rank
        return review

    # 4. NEEDS_HUMAN — the honest default (e.g. required check pending/missing).
    review.verdict = Verdict.NEEDS_HUMAN
    reasons = []
    if gates.required_check in ("pending", "unknown"):
        reasons.append(f"the required check is {gates.required_check}")
    if gates.required_check == "missing":
        reasons.append("no required check is configured to gate this repo")
    if review.findings:
        reasons.append(f"{len(review.findings)} advisory finding(s) to weigh")
    review.verdict_reason = (
        "A human should decide" + (" — " + "; ".join(reasons) if reasons else "") + "."
    )
    review.auto_merge_eligible = False
    return review


def eligible_for_auto_merge(review: Review, *, enabled: bool) -> tuple[bool, str]:
    """Final auto-merge gate. Even when a repo opts in (``enabled=True``), auto-merge
    is allowed ONLY on a SAFE verdict whose eligibility was derived from green
    deterministic gates. The model's opinion alone can never trigger a merge."""
    if not enabled:
        return False, "auto-merge is disabled for this repo (opt-in; off by default)."
    if review.verdict != Verdict.SAFE:
        return False, f"verdict is '{review.verdict.value}', not 'safe'."
    if not review.auto_merge_eligible:
        return False, "the safe verdict did not meet the deterministic auto-merge bar."
    if not review.gates.all_green:
        return False, "deterministic gates are not all green."
    if review.blocking_findings:
        return False, "blocking findings are present."
    return True, "deterministic gates green + no blocking findings; a human-equivalent bar is met."
