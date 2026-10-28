"""
core/news.py — git commit grouping, draft generation and region replacement.

Public API
----------
collect_commits(cfg, since_commit=None)  -> list[Commit]
group_by_section(cfg, commits)           -> dict[str, list[Commit]]
write_draft(cfg, groups, since_commit)   -> Path
apply_draft(cfg, draft_path)             -> None   (rewrites marked regions + sync marker)
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from core.book import BookConfig


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Commit:
    sha: str          # full 40-char hash
    short: str        # 7-char abbreviation
    date: date
    subject: str
    files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Git helpers (stdlib subprocess only)
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: Path) -> str:
    """Run git in *cwd* and return stdout as a string.  Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _list_commits_since(cwd: Path, since_commit: str | None) -> list[str]:
    """Return raw git log lines ``<sha> <iso-date> <subject>`` since *since_commit*.

    If *since_commit* is None, returns all commits.
    The result is ordered newest-first.
    """
    if since_commit:
        rev_range = f"{since_commit}..HEAD"
    else:
        rev_range = "HEAD"

    output = _run_git(
        ["log", rev_range, "--format=%H %aI %s"],
        cwd,
    )
    return [line for line in output.splitlines() if line.strip()]


def _files_for_commit(cwd: Path, sha: str) -> list[str]:
    """Return the list of files changed in *sha*."""
    output = _run_git(
        ["diff-tree", "--no-commit-id", "-r", "--name-only", sha],
        cwd,
    )
    return [f for f in output.splitlines() if f.strip()]


def _is_noise(subject: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, subject):
            return True
    return False


# ---------------------------------------------------------------------------
# Collect
# ---------------------------------------------------------------------------

def collect_commits(
    cfg: BookConfig,
    since_commit: str | None = None,
) -> list[Commit]:
    """Collect commits after *since_commit*, filtering noise via ``ignore_commits``.

    If *since_commit* is None, collects everything.
    Commits are returned newest-first.  Commits sharing the same subject are
    collapsed into the newest one, which also inherits the older commits' files.
    """
    raw_lines = _list_commits_since(cfg.root, since_commit)
    commits: list[Commit] = []
    by_subject: dict[str, Commit] = {}
    for line in raw_lines:
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        sha, iso_date_str, subject = parts[0], parts[1], parts[2]
        if _is_noise(subject, cfg.ignore_commits):
            continue
        try:
            commit_date = datetime.fromisoformat(iso_date_str).date()
        except ValueError:
            commit_date = date.today()
        files = _files_for_commit(cfg.root, sha)
        existing = by_subject.get(subject.strip())
        if existing is not None:
            existing.files.extend(f for f in files if f not in existing.files)
            continue
        commit = Commit(
            sha=sha,
            short=sha[:7],
            date=commit_date,
            subject=subject,
            files=files,
        )
        by_subject[subject.strip()] = commit
        commits.append(commit)
    return commits


# ---------------------------------------------------------------------------
# Group by section
# ---------------------------------------------------------------------------

def group_by_section(
    cfg: BookConfig,
    commits: list[Commit],
) -> dict[str, list[Commit]]:
    """Map each commit to the first section whose path prefix matches any of its files.

    A commit may appear in multiple sections.  Commits that match no section go
    into ``"Other"``.  Sections with no commits are omitted.
    """
    groups: dict[str, list[Commit]] = {}

    for commit in commits:
        matched_sections: list[str] = []
        for section in cfg.sections:
            for prefix in section.paths:
                if any(f.startswith(prefix) for f in commit.files):
                    if section.title not in matched_sections:
                        matched_sections.append(section.title)
                    break
        if not matched_sections:
            matched_sections = ["Other"]
        for title in matched_sections:
            groups.setdefault(title, []).append(commit)

    return groups


# ---------------------------------------------------------------------------
# Write draft
# ---------------------------------------------------------------------------

_DATE_FORMAT = "%Y-%m"  # YYYY-MM per BOOK_STANDARD


def _format_date(d: date) -> str:
    return d.strftime(_DATE_FORMAT)


def write_draft(
    cfg: BookConfig,
    groups: dict[str, list[Commit]],
    since_commit: str | None,
    newest_commit: str | None = None,
) -> Path:
    """Write a news draft to ``<scratch>/news-draft.md`` and return the path.

    The draft contains one section per group, each with bullet points.
    It does NOT touch the live docs — the user reviews it first.
    """
    scratch = cfg.scratch_path()
    scratch.mkdir(parents=True, exist_ok=True)
    draft_path = scratch / "news-draft.md"

    today = _format_date(date.today())
    lines: list[str] = [
        f"<!-- book-sync news draft — generated {today} -->",
        f"<!-- since: {since_commit or 'beginning'} -->",
        f"<!-- newest commit: {newest_commit or 'HEAD'} -->",
        "",
        "# News draft",
        "",
    ]

    if not groups:
        lines.append("*No new commits since the last sync.*")
    else:
        for title, commits in groups.items():
            lines.append(f"## {title}")
            lines.append("")
            for c in commits:
                lines.append(f"- {_format_date(c.date)} {c.subject} ({c.short})")
            lines.append("")

    draft_path.write_text("\n".join(lines), encoding="utf-8")
    return draft_path


# ---------------------------------------------------------------------------
# Region replacement
# ---------------------------------------------------------------------------

_MARKER_START_RE = re.compile(r"<!--\s*book:(?P<name>[a-z-]+):start\s*-->")
_MARKER_END_RE   = re.compile(r"<!--\s*book:(?P<name>[a-z-]+):end\s*-->")
_SYNC_RE         = re.compile(r"<!--\s*book:sync\s+commit=\S+\s+date=\S+\s*-->")


def _replace_region(text: str, region: str, new_content: str) -> str:
    """Replace the content between ``book:<region>:start`` and ``:end`` markers.

    *new_content* is the replacement text (without the markers themselves).
    Raises ``ValueError`` if the markers are missing or mis-ordered.
    Preserves the indentation of the start-marker line on every new line.
    """
    start_marker = f"<!-- book:{region}:start -->"
    end_marker   = f"<!-- book:{region}:end -->"

    si = text.find(start_marker)
    ei = text.find(end_marker)
    if si == -1:
        raise ValueError(f"Missing start marker: {start_marker!r}")
    if ei == -1:
        raise ValueError(f"Missing end marker: {end_marker!r}")
    if ei < si:
        raise ValueError(f"End marker appears before start marker for region {region!r}")

    # Detect indentation from the start-marker line.
    line_start = text.rfind("\n", 0, si) + 1
    indent = ""
    for ch in text[line_start:si]:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break

    # Re-indent new_content lines.
    indented_lines = []
    for line in new_content.splitlines():
        indented_lines.append(indent + line if line.strip() else line)
    indented = "\n".join(indented_lines)

    after_start = si + len(start_marker)
    before_end  = ei
    return text[:after_start] + "\n" + indented + "\n" + indent + text[before_end:]


def apply_draft(
    cfg: BookConfig,
    draft_path: Path,
    region: str = "news-site",
) -> None:
    """Apply a reviewed draft into the ``region`` marked region.

    Also rewrites the ``news-log`` region with a one-line entry and updates
    the ``book:sync`` marker.

    Raises ``FileNotFoundError`` if the draft or the target file is missing.
    Raises ``ValueError`` if a required marker is absent.
    """
    if not draft_path.exists():
        raise FileNotFoundError(f"Draft not found: {draft_path}")

    target = cfg.sync_file()
    if not target.exists():
        raise FileNotFoundError(f"Sync target file not found: {target}")

    draft_text = draft_path.read_text(encoding="utf-8")
    target_text = target.read_text(encoding="utf-8")

    # Extract the newest commit hash from the draft header.
    newest_commit: str | None = None
    for line in draft_text.splitlines():
        m = re.match(r"<!--\s*newest commit:\s*(\S+)\s*-->", line)
        if m:
            newest_commit = m.group(1)
            break

    # Build section body from draft (strip the header comment lines).
    body_lines: list[str] = []
    in_body = False
    for line in draft_text.splitlines():
        if line.startswith("# News draft"):
            in_body = True
            continue
        if in_body:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()

    # Replace the news-site region.
    target_text = _replace_region(target_text, region, body)

    # Update news-log: prepend a one-liner.
    today = _format_date(date.today())
    log_entry = f"- {today} sync"
    # Prepend inside news-log.
    start_marker = "<!-- book:news-log:start -->"
    si = target_text.find(start_marker)
    if si != -1:
        after_start = si + len(start_marker)
        # Find the indentation.
        line_start = target_text.rfind("\n", 0, si) + 1
        indent = ""
        for ch in target_text[line_start:si]:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break
        target_text = (
            target_text[:after_start]
            + "\n"
            + indent + log_entry
            + target_text[after_start:]
        )

    # Rewrite the sync marker.
    if newest_commit and newest_commit != "HEAD":
        new_sync = f"<!-- book:sync commit={newest_commit[:7]} date={today} -->"
        if _SYNC_RE.search(target_text):
            target_text = _SYNC_RE.sub(new_sync, target_text)

    target.write_text(target_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Read current sync position
# ---------------------------------------------------------------------------

def get_sync_commit(cfg: BookConfig) -> str | None:
    """Return the commit hash from the ``book:sync`` marker, or None."""
    sync_file = cfg.sync_file()
    if not sync_file.exists():
        return None
    text = sync_file.read_text(encoding="utf-8")
    m = _SYNC_RE.search(text)
    if not m:
        return None
    inner = m.group(0)
    cm = re.search(r"commit=(\S+)", inner)
    return cm.group(1) if cm else None
