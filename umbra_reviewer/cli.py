"""``umbra-reviewer`` CLI / GitHub Action entrypoint.

    umbra-reviewer review --diff pr.diff --repo owner/name --pr 12 \
        --required-check success --comment-out comment.md

Reads a unified diff (from --diff FILE, or stdin), runs the advisory review,
writes the PR-comment Markdown, and sets an exit code a CI step can gate on:

  0  safe / needs-human / third-party  (advisory; not a hard failure)
  1  block                              (a blocking finding or failed gate)

With --fail-on-needs-human, NEEDS_HUMAN/THIRD_PARTY also exit non-zero (stricter
gate for teams that want the bot to hold non-clean PRs).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import eligible_for_auto_merge, render_comment, review_diff
from .model import Verdict


def _read_diff(args: argparse.Namespace) -> str:
    if args.diff and args.diff != "-":
        return Path(args.diff).read_text(errors="replace")
    return sys.stdin.read()


def _write_outputs(path: str | None, verdict: str, worst: str, blocking: int, auto_merge: bool) -> None:
    if not path:
        return
    with open(path, "a") as fh:
        fh.write(f"verdict={verdict}\n")
        fh.write(f"worst-severity={worst}\n")
        fh.write(f"blocking-count={blocking}\n")
        fh.write(f"auto-merge-eligible={'true' if auto_merge else 'false'}\n")


def cmd_review(args: argparse.Namespace) -> int:
    diff = _read_diff(args)
    if not diff.strip():
        print("umbra-reviewer: empty diff (nothing to review)", file=sys.stderr)
        # Always emit outputs so a downstream gate never reads a stale/empty value.
        _write_outputs(args.github_output, "empty_diff", "info", 0, False)
        return 0

    protected = tuple(g.strip() for g in (args.protected or "").split(",") if g.strip())
    review = review_diff(
        diff,
        repo=args.repo,
        pr_number=args.pr,
        required_check=args.required_check,
        protected_globs=protected,
        require_gate=not args.no_require_gate,
    )

    comment = render_comment(review)
    if args.comment_out:
        Path(args.comment_out).write_text(comment)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(review.to_public(), indent=2))

    can_merge, why = eligible_for_auto_merge(review, enabled=args.auto_merge)

    if args.json:
        payload = review.to_public()
        payload["auto_merge"] = {"eligible": can_merge, "reason": why}
        print(json.dumps(payload, indent=2))
    else:
        print(comment)
        print("\n---")
        print(f"verdict: {review.verdict.value} · auto-merge: {can_merge} ({why})")

    # GitHub Actions outputs (if running in a workflow).
    _write_outputs(args.github_output, review.verdict.value, review.worst_severity.value,
                   len(review.blocking_findings), can_merge)

    # Exit code.
    if review.verdict == Verdict.BLOCK:
        return 1
    if args.fail_on_needs_human and review.verdict in (Verdict.NEEDS_HUMAN, Verdict.THIRD_PARTY):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="umbra-reviewer", description="Advisory PR reviewer with a deterministic merge-safety gate.")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("review", help="Review a unified diff and emit findings + a merge-safety verdict.")
    r.add_argument("--diff", default="-", help="Path to a unified diff file (default: stdin).")
    r.add_argument("--repo", default="unknown", help="owner/name, for the comment header.")
    r.add_argument("--pr", type=int, default=None, help="PR number, for the comment header.")
    r.add_argument("--required-check", default="unknown",
                   choices=["success", "failure", "pending", "missing", "unknown"],
                   help="Status of the repo's required check (from the GitHub API).")
    r.add_argument("--protected", default="", help="Comma-separated globs of protected/ownership paths (escalate to a reviewer).")
    r.add_argument("--no-require-gate", action="store_true", help="Don't treat a failed required check as a block (not recommended).")
    r.add_argument("--auto-merge", action="store_true", help="Opt in to auto-merge eligibility (off by default; still requires green deterministic gates).")
    r.add_argument("--fail-on-needs-human", action="store_true", help="Exit non-zero on needs-human / third-party verdicts too.")
    r.add_argument("--comment-out", help="Write the PR-comment Markdown to this file.")
    r.add_argument("--json-out", help="Write the full review JSON to this file.")
    r.add_argument("--json", action="store_true", help="Print the review as JSON instead of the comment.")
    r.add_argument("--github-output", default=__import__("os").getenv("GITHUB_OUTPUT"), help="Path to write GitHub Actions outputs (defaults to $GITHUB_OUTPUT).")
    r.set_defaults(func=cmd_review)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
