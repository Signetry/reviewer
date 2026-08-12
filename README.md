<div align="center">

# umbra-reviewer

> **Copyright (c) 2026 Binay Dalai. All rights reserved.**
> This repository is strictly for viewing and contributing to the original project. You may not use, copy, modify, distribute, or commercialize this code for your own personal or commercial projects without explicit written permission. Only the original author retains the right to use and monetize this project.


**An advisory PR reviewer that finds architecture + security issues, cross-verifies them against deterministic gates, and tells you whether a change is safe to merge — without ever merging on its own judgement.**

Part of the [Umbra platform](https://github.com/Signetry/signetry).

[![Source-available](https://img.shields.io/badge/source-available-informational.svg)](CLA.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome%20(CLA)-brightgreen.svg)](https://github.com/Signetry/signetry/issues/10)

</div>

---

## What it does

On every pull request, it:

1. **Finds issues** with a deterministic scanner over the diff — introduced secrets, dangerous CI permission / OIDC changes, `pull_request_target` + `curl|sh` footguns, unpinned third-party actions, prompt-injection surfaces in instruction files (`README`/`CLAUDE.md`/…), dynamic-exec / disabled-TLS smells, and changes to protected paths.
2. **Cross-verifies** those findings against **deterministic gates**: the repo's required status check (looked up from the GitHub API), a clean secret scan, and no forbidden permission change.
3. **Recommends a verdict** — 🟢 `safe` · 🟡 `needs_human` · 🟣 `third_party` (escalate to a code owner) · 🔴 `block` — and posts one PR comment.
4. Optionally, **enables auto-merge** — opt-in, off by default, and only ever on a `safe` verdict whose eligibility came from **green deterministic gates** (see the safety model).

## The safety model (why it won't rubber-stamp your repo)

This mirrors Umbra's own principle: **an agent must not approve its own authority.**

- The reviewer is **advisory**. Its findings never *grant* mergeability.
- The **authority** to merge is the deterministic gate — a required status check + a clean secret scan + no forbidden permission change — plus a **human**.
- A **model** finding (if you wire one in) is recorded but **can never be blocking** and can never flip a gated-clean PR away from `safe` on its own.
- **Auto-merge** is opt-in and, even then, uses **GitHub's native auto-merge** (the PR merges only when *branch-protection* required checks pass). The bot never force-merges; the platform does, only if your rules allow.
- A blocking finding **or** a failed/absent required check → `block` / `needs_human`. Sensitive surface (workflows, Dockerfiles, auth, secrets) → `third_party`, always escalated to a human.
- A green verdict is **not a guarantee** — deterministic scanners have false negatives. It's defense-in-depth, not a proof.

## Use it (GitHub Action)

```yaml
# .github/workflows/review.yml
name: Umbra Reviewer
on: { pull_request: {} }
permissions:
  contents: read
  pull-requests: write     # to post the review comment (+ enable auto-merge if opted in)
  checks: read
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: Signetry/reviewer@v1
        with:
          required-check: "Umbra Admission"   # cross-verify your merge gate (optional)
          protected-paths: "infra/**,src/auth/**"
          # auto-merge: "true"                 # opt in; still needs green branch-protection checks
```

## Use it (CLI)

```bash
# source-available (All Rights Reserved); not on PyPI — install from source
pip install "umbra-reviewer @ git+https://github.com/Signetry/reviewer@v0.1.1"

git diff origin/main...HEAD | umbra-reviewer review --repo owner/name --pr 12 \
  --required-check success --comment-out comment.md
# exit 1 on a BLOCK verdict, so it gates CI. Add --fail-on-needs-human for a stricter gate.
```

## Pairs with the rest of Umbra

- [`umbra-action`](https://github.com/Signetry/action) is the **hard gate** (the required check + signed receipt). `umbra-reviewer` is the **advisory layer** on top; point `required-check` at the Umbra Admission check to cross-verify.
- [`umbra-core`](https://github.com/Signetry/core) is the governance kernel.

## Contributing

**Source-available, PRs welcome** (not open source; All Rights Reserved). Contribute under the [CLA](CLA.md) — you're **credited** ([CONTRIBUTORS.md](CONTRIBUTORS.md)) but gain no ownership or right to use/sell it. Good first task: add a deterministic PR-diff check (`umbra_reviewer/checks.py`) with a test. Start at the [good-first-issues board](https://github.com/Signetry/signetry/issues/10) and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

**Copyright (c) 2026 Binay Dalai. All rights reserved.** This code is not open source. You may not use, copy, modify, distribute, or commercialize it for your own personal or commercial purposes without explicit written permission from the author, who alone retains the right to use and monetize this project. See [CONTRIBUTING.md](CONTRIBUTING.md).
