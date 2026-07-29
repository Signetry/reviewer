"""Render a Review into a GitHub PR comment (Markdown)."""
from __future__ import annotations

from .model import Review, Severity, Verdict

_VERDICT_BADGE = {
    Verdict.SAFE: "🟢 Safe",
    Verdict.NEEDS_HUMAN: "🟡 Needs human review",
    Verdict.THIRD_PARTY: "🟣 Escalate to a designated reviewer",
    Verdict.BLOCK: "🔴 Block",
}
_SEV_EMOJI = {
    Severity.CRITICAL: "🔴", Severity.HIGH: "🟠", Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵", Severity.INFO: "⚪",
}


def render_comment(review: Review) -> str:
    g = review.gates
    lines: list[str] = []
    lines.append(f"## Umbra Reviewer — {_VERDICT_BADGE.get(review.verdict, review.verdict.value)}")
    lines.append("")
    lines.append(f"_{review.verdict_reason}_")
    lines.append("")

    # Deterministic gate table — the signals the verdict is actually built on.
    def y(v: bool) -> str:
        return "✅" if v else "❌"
    check_glyph = {"success": "✅ passed", "failure": "❌ failed", "pending": "⏳ pending",
                   "missing": "— none configured", "unknown": "— unknown"}.get(g.required_check, g.required_check)
    lines += [
        "### Deterministic gates (the authority)",
        "",
        "| Gate | Status |",
        "|---|---|",
        f"| Required status check | {check_glyph} |",
        f"| Secret scan | {y(g.secret_scan_clean)} clean |",
        f"| CI permission / OIDC | {y(g.no_forbidden_perm_change)} no forbidden change |",
        f"| Dependency skew | {y(g.dependency_skew_ok)} ok |",
        f"| **All green** | {y(g.all_green)} |",
        "",
    ]

    # Findings, worst first.
    if review.findings:
        ordered = sorted(review.findings, key=lambda f: (-f.severity.rank, not f.blocking))
        lines.append(f"### Findings ({len(review.findings)}, {len(review.blocking_findings)} blocking)")
        lines.append("")
        for f in ordered:
            loc = f" `{f.file}`" + (f":{f.line}" if f.line else "") if f.file else ""
            block = " **[blocking]**" if f.blocking else ""
            src = "" if f.source == "deterministic" else f" _(via {f.source})_"
            lines.append(f"- {_SEV_EMOJI.get(f.severity, '')} **{f.title}**{block}{loc}{src}")
            lines.append(f"  - {f.detail}")
            if f.remediation:
                lines.append(f"  - _Fix:_ {f.remediation}")
        lines.append("")
    else:
        lines += ["### Findings", "", "No issues found by the deterministic scanners.", ""]

    if review.sensitive_paths:
        lines += [
            "### Sensitive surface",
            "",
            "This PR changes security-sensitive paths that warrant a designated reviewer:",
            "",
            *[f"- `{p}`" for p in review.sensitive_paths],
            "",
        ]

    # Merge guidance — honest about what the bot will/won't do.
    lines.append("### Merge")
    if review.verdict == Verdict.SAFE and review.auto_merge_eligible:
        lines.append("Deterministic gates are green and no blocking issue was found. "
                     "Eligible for auto-merge **only if the repo opted in**; otherwise a human merges.")
    elif review.verdict == Verdict.BLOCK:
        lines.append("**Do not merge** until the blocking items above are resolved.")
    elif review.verdict == Verdict.THIRD_PARTY:
        lines.append("A **designated reviewer / code owner** should sign off before merge (sensitive surface).")
    else:
        lines.append("A **human** should review and merge.")
    lines.append("")
    lines.append("> This review is **advisory**. It never merges on its own judgement — "
                 "the deterministic gates + a human are the authority. Findings can have false "
                 "negatives; a green bot verdict is not a guarantee.")
    return "\n".join(lines)
