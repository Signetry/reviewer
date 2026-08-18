# Changelog — signetry-reviewer

Follows [Keep a Changelog](https://keepachangelog.com/) / [SemVer](https://semver.org/).

## [Unreleased]

### Added — insecure-deserialization check (`deser.introduced`)

- Flags a deserialization sink introduced by the diff, across Python (`pickle`,
  `marshal`, `shelve`, `yaml.load` without a safe Loader, `yaml.unsafe_load`), Java
  (`ObjectInputStream` / `readObject`), PHP (`unserialize`), Ruby (`Marshal.load` /
  `YAML.load`) and .NET (`BinaryFormatter` and friends).
- **Advisory, never blocking.** Whether the input is attacker-controlled cannot be
  read off a diff hunk, so this adds reviewer context rather than deciding
  mergeability — matching how `arch.dynamic_exec` treats `eval`/`exec`.
- Added lines only, so a *removed* sink (i.e. a fix) is not a finding.
- Whole-line comments are skipped, and `yaml.load(..., Loader=SafeLoader)` /
  `yaml.safe_load` / `json.loads` are not flagged. Sinks in test/fixture paths are
  reported at MEDIUM rather than HIGH.

## [0.2.0] — 2026-08-18

### Fixed — the pinned install default was stale

- `action.yml` fell back to `@v0.1.1` even after v0.1.2 shipped, so a workflow that
  did not set `signetry-reviewer-version` silently installed a release behind. Now
  tracks this release.

### Fixed — CI checks no longer fire on YAML comments

- `scan_ci_permissions` filtered nothing: every rule matched raw added text, so a
  workflow that **documented** a risk in a comment tripped the rule meant to
  catch it. Whole-line YAML comments (`#…`) are now skipped. Inline trailing
  comments are deliberately still scanned — `#` is legal inside a quoted scalar,
  so stripping it by regex could hide real configuration.
- `ci.pull_request_target` matched the bare string anywhere in a workflow file.
  It now matches the trigger itself in every form YAML permits: the mapping key
  (`pull_request_target:`), a scalar (`on: pull_request_target`), an inline
  sequence (`on: [push, pull_request_target]`), and a block sequence item
  (`- pull_request_target`).
- Found in the field: Signetry/core#92 was returned 🔴 **Block** on two comment
  lines explaining why that trigger is deliberately avoided.

### Added — dependency-skew check (`supply.dependency_skew`)

- Flags a lockfile that changed without its sibling manifest, across npm/yarn/pnpm/
  bun, uv/poetry/Pipenv, Cargo, Go, Composer and Bundler. Matching is
  per-directory, so a monorepo's `packages/a/package-lock.json` is not satisfied by
  `packages/b/package.json`.
- Advisory (non-blocking) by design: `npm audit fix`, `cargo update` and Dependabot
  all legitimately produce lockfile-only changes, and a failed gate means
  `verdict=BLOCK` / "not mergeable", which would reject every one of them. It is
  MEDIUM severity, so it still **withholds auto-merge** — a lockfile-substitution
  PR cannot auto-merge on a green verdict.

### Fixed — the `dependency_skew_ok` gate was dead, then would have over-blocked

- `supply.dependency_skew` was referenced by the gate report, the verdict logic and
  the rendered comment, but **no scanner ever produced it** — so the "Dependency
  skew ✅ ok" row was meaningless in every review to date.
- The gate also ignored the `blocking` flag, unlike `secret_scan_clean` and
  `no_forbidden_perm_change`. It now keys off a *blocking* skew, matching them;
  without this, implementing the check above would have hard-blocked every
  Dependabot PR.

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
