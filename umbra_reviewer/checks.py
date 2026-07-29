"""Deterministic checks over a PR's unified diff.

These are the TRUSTWORTHY signals — pure pattern analysis, no model, no network.
Everything the merge-safety verdict actually relies on comes from here (plus the
required-check status from the GitHub API). A model pass may ADD advisory context
on top, but it can never override or relax these.

Each check returns ``Finding``s. The scanners look only at ADDED lines (the diff's
``+`` lines) so a PR is judged on what it introduces, not on pre-existing code.
"""
from __future__ import annotations

import re

from .model import Category, Finding, Severity

# --- diff parsing -----------------------------------------------------------


def added_lines(diff: str) -> list[tuple[str, int, str]]:
    """Return (file, line_no, text) for every ADDED line in a unified diff.

    Ignores the +++ header lines and removed/context lines. Line numbers are the
    new-file line numbers derived from the @@ hunk headers (best-effort)."""
    out: list[tuple[str, int, str]] = []
    cur_file = "?"
    new_ln = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            cur_file = path[2:] if path.startswith("b/") else path
            continue
        if raw.startswith("--- "):
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if m:
            new_ln = int(m.group(1))
            continue
        if raw.startswith("+"):
            out.append((cur_file, new_ln, raw[1:]))
            new_ln += 1
        elif not raw.startswith("-"):
            new_ln += 1
    return out


def changed_files(diff: str) -> list[str]:
    files: list[str] = []
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            p = raw[4:].strip()
            p = p[2:] if p.startswith("b/") else p
            if p and p != "/dev/null":
                files.append(p)
    return files


# --- 1. secret scan ---------------------------------------------------------

_SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "OpenAI API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{22,})\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[0-9A-Z]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprsce]-[A-Za-z0-9-]{10,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "Generic assigned secret": re.compile(r"(?i)(secret|token|passwd|password|api[_-]?key)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
}
_FIXTURE_CONTENT_HINTS = ("example", "placeholder", "replace", "your-", "xxxx", "dummy", "sample", "changeme", "<", "redacted")


def _is_fixture_path(file: str) -> bool:
    """True only when the path is genuinely a test/fixture/example location — by
    path SEGMENT, not substring, so real names like ``contest.py`` or
    ``test_prod_config.py`` do NOT disable secret scanning."""
    import posixpath

    parts = [p.lower() for p in file.split("/")]
    name = parts[-1] if parts else ""
    # Directory segments that mean "test data".
    if any(seg in {"tests", "test", "fixtures", "fixture", "__mocks__", "mocks", "examples", "example", "testdata"} for seg in parts[:-1]):
        return True
    # Filename shaped like a sample/example (suffix or clear example name).
    stem = posixpath.splitext(name)[0]
    if name.endswith((".sample", ".example", ".dist", ".template")):
        return True
    if stem.startswith(("example", "sample", "mock_", "dummy_")) or stem.endswith(("_example", "_sample", ".example")):
        return True
    return False


def scan_secrets(diff: str) -> list[Finding]:
    findings: list[Finding] = []
    for file, ln, text in added_lines(diff):
        fixture = _is_fixture_path(file)
        for kind, pat in _SECRET_PATTERNS.items():
            if pat.search(text):
                # In a genuine fixture/example file, only skip when the value also
                # looks like an obvious placeholder — a real-looking secret in a
                # test file is still flagged (lower severity, non-blocking).
                looks_placeholder = any(h in text.lower() for h in _FIXTURE_CONTENT_HINTS)
                if fixture and looks_placeholder:
                    break
                blocking = not fixture
                sev = Severity.CRITICAL if not fixture else Severity.MEDIUM
                findings.append(Finding(
                    id="secret.introduced",
                    category=Category.SECURITY,
                    severity=sev,
                    title=f"Possible {kind} committed" + (" (in a test/fixture file)" if fixture else ""),
                    detail=f"An added line looks like a {kind}. Committing a live credential is a leak; rotate it if real.",
                    file=file, line=ln,
                    remediation="Remove the secret, use a secret manager / env var, and rotate the credential.",
                    blocking=blocking,
                ))
                break
    return findings


# --- 2. dangerous CI / permission / OIDC changes ----------------------------

_WORKFLOW_RE = re.compile(r"(^|/)\.github/workflows/.*\.ya?ml$")


def scan_ci_permissions(diff: str) -> list[Finding]:
    findings: list[Finding] = []
    for file, ln, text in added_lines(diff):
        if not _WORKFLOW_RE.search(file):
            continue
        t = text.strip()
        # Escalated permissions.
        if re.search(r"(?i)permissions:\s*write-all", t):
            findings.append(Finding(
                id="ci.permissions_write_all", category=Category.SECURITY, severity=Severity.HIGH,
                title="Workflow requests permissions: write-all",
                detail="A workflow now grants itself blanket write permissions — over-broad and a common privilege-escalation footgun.",
                file=file, line=ln, remediation="Scope permissions to the minimum the job needs (e.g. contents: read).",
                blocking=True,
            ))
        if re.search(r"(?i)\bid-token:\s*write", t):
            findings.append(Finding(
                id="ci.oidc_id_token_write", category=Category.SECURITY, severity=Severity.HIGH,
                title="Workflow enables OIDC id-token: write",
                detail="`id-token: write` mints an OIDC token (used for cloud/registry federation & Trusted Publishing). Legitimate for release jobs, but a powerful capability.",
                file=file, line=ln, remediation="Confirm this is a release/publish job and the federated trust policy is scoped to this repo.",
                blocking=False,
            ))
        # Untrusted checkout of PR head in a privileged trigger.
        if re.search(r"(?i)pull_request_target", t):
            findings.append(Finding(
                id="ci.pull_request_target", category=Category.SECURITY, severity=Severity.HIGH,
                title="Workflow uses pull_request_target",
                detail="`pull_request_target` runs with the base repo's secrets while checking out untrusted PR code — a classic exfiltration vector if it checks out and runs the PR head.",
                file=file, line=ln, remediation="Avoid running untrusted code under pull_request_target; if unavoidable, never checkout PR head with secrets present.",
                blocking=True,
            ))
        # curl | sh style remote execution in CI.
        if re.search(r"(?i)curl[^\n|]*\|\s*(sh|bash)", t) or re.search(r"(?i)wget[^\n|]*\|\s*(sh|bash)", t):
            findings.append(Finding(
                id="ci.remote_pipe_shell", category=Category.SECURITY, severity=Severity.HIGH,
                title="Workflow pipes a remote script into a shell",
                detail="`curl … | sh` in CI executes unpinned remote code with the runner's privileges/secrets.",
                file=file, line=ln, remediation="Pin the script by digest, or download-verify-run in separate steps.",
                blocking=True,
            ))
        # Unpinned third-party action (uses: owner/repo@vN or @branch, not a SHA).
        m = re.search(r"(?i)uses:\s*([^\s@]+)@([^\s#]+)", t)
        if m:
            owner_repo, ref = m.group(1), m.group(2)
            first_party = owner_repo.startswith(("actions/", "github/")) or "/" not in owner_repo
            is_sha = bool(re.fullmatch(r"[0-9a-f]{40}", ref))
            if not first_party and not is_sha:
                findings.append(Finding(
                    id="ci.unpinned_action", category=Category.SUPPLY_CHAIN, severity=Severity.MEDIUM,
                    title=f"Third-party action not pinned to a SHA: {owner_repo}@{ref}",
                    detail="A third-party action pinned to a tag/branch can be moved to malicious code without changing the ref. Pin to a full commit SHA.",
                    file=file, line=ln, remediation=f"Pin as `{owner_repo}@<40-char-commit-sha>`.",
                    blocking=False,
                ))
    return findings


# --- 3. prompt-injection surfaces in instruction files ----------------------

_INSTRUCTION_FILES = ("readme", "agents.md", "claude.md", ".cursorrules", "contributing", "copilot-instructions")
_INJECTION_PATTERNS = (
    ("policy_override", re.compile(r"(?i)(ignore|disregard|forget|override|bypass)\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|policy)")),
    ("agent_directive", re.compile(r"(?i)\b(you must|you should|ai agent|assistant must|as an ai)\b")),
    ("secret_exfil", re.compile(r"(?i)(print|reveal|exfiltrate|send|leak|curl)\s+.{0,20}(secret|token|api[_-]?key|\.env)")),
    ("scope_expansion", re.compile(r"(?i)(also|then)\s+(edit|modify|change|delete)\s+.{0,30}(deploy|ci|workflow|\.github)")),
)


def scan_injection_surfaces(diff: str) -> list[Finding]:
    findings: list[Finding] = []
    for file, ln, text in added_lines(diff):
        low = file.lower()
        if not any(m in low for m in _INSTRUCTION_FILES):
            continue
        for cat, pat in _INJECTION_PATTERNS:
            if pat.search(text):
                findings.append(Finding(
                    id=f"injection.{cat}", category=Category.INJECTION, severity=Severity.HIGH,
                    title=f"Possible prompt-injection ({cat}) added to an instruction file",
                    detail=f"An added line in `{file}` reads as agent-directed manipulation ({cat}). Coding agents ingest these files as context; this could steer them.",
                    file=file, line=ln,
                    remediation="Remove or neutralize the directive; instruction files should describe the project, not command an agent.",
                    blocking=False,
                ))
                break
    return findings


# --- 4. architectural smells ------------------------------------------------


def scan_architecture(diff: str, *, protected_globs: tuple[str, ...] = ()) -> list[Finding]:
    findings: list[Finding] = []
    files = changed_files(diff)
    # Touching protected/ownership paths (declared by the repo) → escalate.
    for f in files:
        for g in protected_globs:
            import fnmatch
            if fnmatch.fnmatch(f, g):
                findings.append(Finding(
                    id="arch.protected_path", category=Category.ARCHITECTURE, severity=Severity.MEDIUM,
                    title=f"Change touches a protected path: {f}",
                    detail=f"`{f}` matches a protected pattern (`{g}`). Changes here alter shared/foundational surface and warrant a designated reviewer.",
                    file=f, remediation="Route to a code owner / architecture reviewer.",
                    blocking=False, source="cross-check",
                ))
                break
    # Signals in added code that hint at architectural risk.
    for file, ln, text in added_lines(diff):
        t = text.strip()
        if re.search(r"(?i)\beval\s*\(|\bexec\s*\(|subprocess.*shell\s*=\s*True|os\.system\s*\(", t):
            findings.append(Finding(
                id="arch.dynamic_exec", category=Category.SECURITY, severity=Severity.HIGH,
                title="Dynamic code / shell execution introduced",
                detail="`eval`/`exec`/`shell=True`/`os.system` on untrusted input is an RCE surface.",
                file=file, line=ln, remediation="Avoid dynamic execution; use explicit dispatch and pass args as a list without a shell.",
                blocking=False,
            ))
        if re.search(r"(?i)verify\s*=\s*False|InsecureRequestWarning|ssl\._create_unverified", t):
            findings.append(Finding(
                id="arch.tls_verify_disabled", category=Category.SECURITY, severity=Severity.HIGH,
                title="TLS verification disabled",
                detail="Disabling certificate verification exposes traffic to MITM.",
                file=file, line=ln, remediation="Keep TLS verification on; fix the cert chain instead.",
                blocking=True,
            ))
    return findings


def run_all_deterministic(diff: str, *, protected_globs: tuple[str, ...] = ()) -> list[Finding]:
    """Run every deterministic scanner over the diff and return all findings."""
    findings: list[Finding] = []
    findings += scan_secrets(diff)
    findings += scan_ci_permissions(diff)
    findings += scan_injection_surfaces(diff)
    findings += scan_architecture(diff, protected_globs=protected_globs)
    return findings
