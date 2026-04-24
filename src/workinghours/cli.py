# pyright: reportUnusedCallResult=false
import argparse
import sys

import pygit2

from workinghours.apply import apply_plan
from workinghours.interval import combine_intervals, parse_interval
from workinghours.plan import generate_plan


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workinghours",
        description="Rewrite git commit timestamps to fall within specified time intervals.",
    )
    parser.add_argument(
        "--interval",
        "-i",
        action="append",
        dest="intervals",
        metavar="INTERVAL",
        help=(
            "Target interval (may be repeated). Named: workhours, sleepytime. "
            "Prefix ! to exclude: !workhours, !sleepytime. "
            "Custom: HH:MM-HH:MM or !HH:MM-HH:MM. "
            "Multiple --interval values are combined: inclusive intervals are "
            "unioned; exclusive intervals exclude all named ranges. "
            "Mixing inclusive and exclusive is an error. Default: workhours."
        ),
    )
    parser.add_argument(
        "--repo",
        "-r",
        default=".",
        metavar="PATH",
        help="Path to git repository (default: current directory).",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the timestamp plan to stdout without rewriting history.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Hard boundaries — no commits will fall outside the target window.",
    )
    parser.add_argument(
        "--softness",
        "-s",
        type=float,
        default=1.0,
        metavar="HOURS",
        help=(
            "Exponential decay rate for soft boundaries, in hours (default: 1.0). "
            "Ignored when --strict is set."
        ),
    )
    parser.add_argument(
        "revspec",
        nargs="?",
        default="HEAD",
        help="Commit range to rewrite, e.g. HEAD~10..HEAD (default: HEAD).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.softness < 0:
        parser.error("--softness must be non-negative")

    try:
        intervals = [parse_interval(s) for s in (args.intervals or ["workhours"])]
        windows = combine_intervals(intervals)
    except ValueError as e:
        parser.error(str(e))

    try:
        repo = pygit2.Repository(args.repo)
    except pygit2.GitError as e:
        sys.exit(f"error: cannot open repository at {args.repo!r}: {e}")

    try:
        plan = generate_plan(
            repo=repo,
            revspec=args.revspec,
            windows=windows,
            softness=args.softness,
            strict=args.strict,
        )
    except pygit2.GitError as e:
        sys.exit(f"error: cannot resolve revspec {args.revspec!r}: {e}")
    except ValueError as e:
        sys.exit(f"error: {e}")

    if args.plan:
        for cid, new_dt in plan.items():
            print(f"{cid} {new_dt.isoformat()}")
        return

    try:
        repo_path = repo.workdir.rstrip("/")
        apply_plan(repo_path, plan)
    except Exception as e:
        sys.exit(f"error: failed to apply plan: {e}")
