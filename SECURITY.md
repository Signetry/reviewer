# Security policy

umbra-reviewer is an **advisory** reviewer. It never merges on its own judgement:
merge authority is the deterministic gate (a required status check + a clean
secret scan + no forbidden permission change) plus a human. Auto-merge is opt-in,
off by default, and delegates to GitHub's native auto-merge (branch protection
still applies).

## Reporting

Open a private security advisory on this repository, or use the umbrella contact:
<https://github.com/bkd-dotcom/umbra-umbrella>. Do not open a public issue for an
unpatched vulnerability.

## Design guarantees

- The deterministic scanners are stdlib-only (no runtime deps, no network).
- Model/heuristic findings can never be blocking and can never flip a gated-clean
  PR to `safe` on their own.
- A green verdict is defense-in-depth, not a proof; scanners have false negatives.
- The Action never interpolates untrusted PR input into a shell body.
