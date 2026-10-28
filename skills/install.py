#!/usr/bin/env python3
"""
skills/install.py — link a skill into a harness skill folder.

Usage examples:

  # Install both skills into a Bob harness folder under flink-studies
  python skills/install.py --harness bob --target ~/Documents/Code/flink-studies

  # Install a specific skill into a Pi harness (user-level)
  python skills/install.py --harness pi --target ~/.pi --skill book-sync

  # Install into a Claude user-level folder
  python skills/install.py --harness claude --target ~/.claude

  # List supported harnesses
  python skills/install.py --list-harnesses

The script creates a symlink <target>/<harness_skills_dir>/<skill-name> → <skills-src-dir>/<skill-name>.
If the symlink already exists and is correct, it is left unchanged.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Harness → relative skills folder name inside the target directory.
# ---------------------------------------------------------------------------

HARNESS_DIRS: dict[str, str] = {
    "bob":    ".bob/skills",
    "claude": ".claude/skills",
    "pi":     ".pi/skills",
}

SKILLS_ROOT = Path(__file__).resolve().parent


def list_skills() -> list[Path]:
    return [p for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]


def install_skill(skill_src: Path, harness_skills_dir: Path, dry_run: bool) -> str:
    """Symlink *skill_src* into *harness_skills_dir*.  Returns a status string."""
    harness_skills_dir.mkdir(parents=True, exist_ok=True)
    link = harness_skills_dir / skill_src.name

    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == skill_src:
            return f"  already linked: {link} → {skill_src}"
        return f"  SKIP (already exists, not a matching symlink): {link}"

    if dry_run:
        return f"  DRY RUN  would link: {link} → {skill_src}"

    link.symlink_to(skill_src)
    return f"  linked: {link} → {skill_src}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Link book-sync skills into a harness skill folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--harness", "-H",
        choices=list(HARNESS_DIRS),
        help="Target harness (bob | claude | pi).",
    )
    parser.add_argument(
        "--target", "-t",
        type=Path,
        help="Root directory of the harness or book repo.  The harness skill folder "
             "is resolved as <target>/<harness-skills-dir>.",
    )
    parser.add_argument(
        "--skill", "-s",
        help="Install only this skill (default: all).",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without making any changes.",
    )
    parser.add_argument(
        "--list-harnesses",
        action="store_true",
        help="List supported harness names and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_harnesses:
        print("Supported harnesses:")
        for name, rel in HARNESS_DIRS.items():
            print(f"  {name:10}  → <target>/{rel}/")
        return 0

    if not args.harness or not args.target:
        parser.error("--harness and --target are required (unless --list-harnesses)")

    target = args.target.expanduser().resolve()
    if not target.exists():
        print(f"ERROR: target directory does not exist: {target}", file=sys.stderr)
        return 2

    harness_skills_dir = target / HARNESS_DIRS[args.harness]

    skills_to_install = list_skills()
    if args.skill:
        skills_to_install = [s for s in skills_to_install if s.name == args.skill]
        if not skills_to_install:
            print(f"ERROR: skill {args.skill!r} not found in {SKILLS_ROOT}", file=sys.stderr)
            return 2

    prefix = "DRY RUN  " if args.dry_run else ""
    print(f"{prefix}Installing {len(skills_to_install)} skill(s) into {harness_skills_dir}:")
    for skill_src in skills_to_install:
        status = install_skill(skill_src, harness_skills_dir, dry_run=args.dry_run)
        print(status)

    if not args.dry_run:
        print(f"\nDone.  Verify with: ls -la {harness_skills_dir}")
    else:
        print("\nRun without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
