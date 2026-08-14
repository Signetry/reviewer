# Changelog — signetry-reviewer

Follows [Keep a Changelog](https://keepachangelog.com/) / [SemVer](https://semver.org/).

## [Unreleased]

### Changed — Signetry naming

- The project is **`signetry-reviewer`**: the Python distribution
  (`[project].name`), the import package (`signetry_reviewer`), the CLI console
  command (`signetry-reviewer`), and all brand/prose references use **Signetry**.

## [0.1.1] — 2026-08-03

### Changed — source-available distribution (no PyPI)

- signetry-reviewer is **source-available** (All Rights Reserved) and is **not
  published to PyPI**. Install from source:
  `pip install "signetry-reviewer @ git+https://github.com/Signetry/reviewer@v0.1.2"`.
- `action.yml` installs from the git source by tag (the `signetry-reviewer-version`
  input is a git tag); README + `release.yml` updated to match (no PyPI publish).
  No functional change from `0.1.0`.

## [0.1.0] — 2026-07-29

### Added

- Initial release: an **advisory** PR reviewer with a deterministic merge-safety gate.
- **Deterministic scanners** (stdlib-only, no runtime deps) over a unified diff:
  introduced secrets, dangerous CI permission / OIDC / `pull_request_target` /
  `curl|sh`, unpinned third-party actions, prompt-injection surfaces in
  instruction files, dynamic-exec / disabled-TLS smells, and protected-path changes.
- **Cross-verification** against deterministic gates (required status check + clean
  secret scan + no forbidden permission change) → a verdict: `safe` / `needs_human`
  / `third_party` (escalate to a code owner) / `block`.
- **Safety model:** the reviewer never merges on its own judgement. Model/external
  findings are forced advisory (non-blocking) and can never flip a verdict to safe
  or fail the gate. Auto-merge is opt-in, off by default, and only fires on a `safe`
  verdict with green deterministic gates via GitHub-native `gh pr merge --auto`
  (branch protection still applies). Fails **closed** on a reviewer crash.
- Ships a **GitHub Action** (posts/updates one PR comment, cross-verifies the
  required check, optional guarded auto-merge) and a **CLI** (`signetry-reviewer review`).
