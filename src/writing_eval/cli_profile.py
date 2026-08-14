"""Named style-profile command implementation."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

from .cli_support import Parser, UserError
from .profile_cache import refresh_reference_caches
from .profiles import ProfileError, build_profile, list_profiles
from .style_audit import BUILTIN_RULES_PATH, load_rules


def parser() -> argparse.ArgumentParser:
    command = Parser(
        prog="writing-eval profile",
        description="Build and inspect named style profiles",
    )
    subparsers = command.add_subparsers(dest="subcommand", required=True)
    build = subparsers.add_parser("build", help="build a profile from local prose")
    build.add_argument("name", help="profile name (its directory under the root)")
    build.add_argument(
        "--from", dest="sources", nargs="+", required=True, type=Path,
        help="source directories or .md/.txt files",
    )
    build.add_argument(
        "--profiles-root", dest="profiles_root", type=Path,
        default=Path("data/profiles"),
    )
    build.add_argument("--rules", type=Path, default=BUILTIN_RULES_PATH)
    listing = subparsers.add_parser("list", help="list available profiles")
    listing.add_argument(
        "--profiles-root", dest="profiles_root", type=Path,
        default=Path("data/profiles"),
    )
    cache = subparsers.add_parser(
        "cache", help="rebuild a profile's precomputed reference-corpus cache"
    )
    cache.add_argument("name", help="profile name (its directory under the root)")
    cache.add_argument(
        "--profiles-root", dest="profiles_root", type=Path,
        default=Path("data/profiles"),
    )
    cache.add_argument("--rules", type=Path, default=BUILTIN_RULES_PATH)
    return command


def _load_rules(rules_path: Path):
    try:
        return load_rules(rules_path)
    except ValueError as exc:
        raise UserError(f"could not load style-audit rules: {exc}") from None


def run(args: argparse.Namespace) -> int:
    try:
        if args.subcommand == "build":
            out_dir = args.profiles_root / args.name
            rules = _load_rules(args.rules)
            data = build_profile(
                args.name, args.sources, out_dir, dt.date.today().isoformat(),
                rules=rules,
            )
            print(
                f"built profile {args.name!r}: {len(data['sources'])} sources, "
                f"{data['total_words']} words -> {out_dir}"
            )
            return 0
        if args.subcommand == "cache":
            directory = args.profiles_root / args.name
            rules = _load_rules(args.rules)
            refresh_reference_caches(directory, directory / "references.jsonl", rules)
            print(f"refreshed cache for profile {args.name!r} -> {directory / 'cache'}")
            return 0
        def _report_skip(profile_path: Path, error_text: str) -> None:
            print(
                f"note: skipped unreadable profile {profile_path}: {error_text}",
                file=sys.stderr,
            )

        for summary in list_profiles(args.profiles_root, on_skip=_report_skip):
            print(
                f"{summary['name']}: {summary['sources']} sources, "
                f"{summary['total_words']} words"
            )
        return 0
    except ProfileError as exc:
        raise UserError(str(exc)) from None
