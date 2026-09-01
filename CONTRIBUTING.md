# Contributing to signetry-reviewer

`signetry-reviewer` is **[Apache-2.0](LICENSE)** — use it, fork it, run it in your own
CI, ship it commercially, no permission needed. This file covers what the licence means
for contributors, why a CLA still applies, and how to get a change merged.

The most valuable contribution here is **a new deterministic check**: something the
reviewer can assert about a diff without asking a model. The reviewer's whole claim is
that its advice is cross-verified against gates that cannot hallucinate, so every
deterministic check makes the advisory layer more trustworthy.

## Licensing, in plain terms

- **This repository is Apache-2.0.** You may use, copy, modify, distribute, and
  commercially deploy it, including forks and derivative reviewers. Nothing is gated on
  asking us first.
- **Signetry is open core.** The integration surface — this repo, the
  [GitHub Action](https://github.com/Signetry/action), the
  [editor/agent plugins](https://github.com/Signetry/plugins), the
  [pre-commit guard](https://github.com/Signetry/precommit) — is Apache-2.0. The engine
  ([`Signetry/core`](https://github.com/Signetry/core)) is source-available under
  BUSL-1.1 and converts to Apache-2.0 on **2030-08-31**. See
  [LICENSING.md](https://github.com/Signetry/signetry/blob/main/LICENSING.md).
- **This package installs from source, not PyPI.** That is a distribution choice, not a
  restriction on what you may do with the code.

### The CLA still applies — and why

Open source and a CLA are not in tension. Because Signetry is open core, code
legitimately moves **across the licence line**: a check that starts life here
(Apache-2.0) may later belong inside the engine (BUSL-1.1), and engine code may move out
to the integration surface. The [CLA](CLA.md) gives the maintainer the relicensing rights
that make those moves possible without tracking down every past contributor for
permission.

What it does **not** do is take anything from you: you keep the full Apache-2.0 grant on
this repository, exactly like every other user, and you keep the right to use your own
work however you like elsewhere. Contributors are credited in
[CONTRIBUTORS.md](CONTRIBUTORS.md), the Git history, and release notes.

## Signing the CLA (required before merge)

This is enforced by a bot. When you open a pull request, the **CLA Assistant** check
will ask you to sign the [Contributor License Agreement](CLA.md). Reply on the PR
with exactly:

```
I have read the CLA Document and I hereby sign the CLA
```

Your acceptance is recorded in `signatures/cla.json`. A PR **cannot be merged** until
the CLA is signed.

## Development setup

Python **3.11+**.

```bash
pip install -e ".[dev]"
```

A `uv.lock` is committed, so `uv sync --extra dev` installs the exact locked set if you
prefer [uv](https://docs.astral.sh/uv/).

## Lint and test (what CI runs)

```bash
ruff check signetry_reviewer/ tests/
pytest -q
```

## Adding a deterministic check

1. Add the check to [`signetry_reviewer/checks.py`](signetry_reviewer/checks.py).
2. It must be **deterministic and offline** — no model call, no network. A check that
   sometimes disagrees with itself cannot cross-verify anything.
3. Return a finding with enough context for a human to act on it without re-reading the
   diff.
4. Add a test under `tests/`.

## The one rule this repo will not bend

**The reviewer is advisory. It never merges and it never gates.** A change that makes
the reviewer's own judgement authoritative — auto-approving, auto-merging on its own
verdict, or failing a build on a model's opinion alone — will not be merged. Gating is
[`signetry-action`](https://github.com/Signetry/action)'s job, against deterministic
admission, with a signed receipt. Keep the two separate.

## Pull requests

- Start at the [good-first-issues board](https://github.com/Signetry/signetry/issues/10).
- Keep the diff focused; every new check ships with a test.
- Be decent to each other: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Found a security problem instead of a bug? Do not open a public issue — see
  [SECURITY.md](SECURITY.md).
