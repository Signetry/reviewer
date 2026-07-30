# Contributing to umbra-reviewer

Thanks for helping improve the advisory PR reviewer. It's a small, deterministic
Python tool, so contributions are well-scoped and easy to validate.

## Setup

```bash
pip install -e ".[dev]"
pytest -q
ruff check umbra_reviewer/ tests/
```

## Good first contributions

- **A new deterministic check** — add a scanner over the PR diff (secrets, CI/OIDC
  footguns, dynamic-exec / TLS-off smells, protected-path changes) in
  `umbra_reviewer/checks.py`, with a test in `tests/`.
- **Verdict / rendering tweaks** — improve how findings map to
  `safe`/`needs_human`/`third_party`/`block` (`verdict.py`, `render.py`).
- **Docs** — clarify the safety model.

## Ground rules

- **Advisory only.** A model or heuristic finding may *add* context but can **never
  grant** mergeability, override a green deterministic gate, or auto-merge. The
  authority to merge is a deterministic gate + a human. Keep it that way.
- Every check ships with a test; CI runs on Python 3.11–3.13.
- Be kind — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report security issues via
  [private advisory](https://github.com/bkd-dotcom/umbra-reviewer/security/advisories/new),
  not a public issue.
