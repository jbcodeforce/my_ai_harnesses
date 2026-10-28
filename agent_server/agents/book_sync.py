"""
agents/book_sync.py — Agno agent that wraps core/ for book maintenance.

Read tools are freely callable.
Write tools (apply_news, apply_stats, apply_audit_fix) are listed in
``requires_confirmation_tools`` so the AgentOS UI pauses for human approval.

The target book is supplied by the user as any directory path that resolves
to a folder containing a valid ``book.yml``.  An optional env var
``BOOK_SYNC_ALLOWED_ROOTS`` (colon-separated paths) restricts which parent
folders are accepted.
"""
from __future__ import annotations

import os
from pathlib import Path

from agno.agent import Agent
from agno.models.openai.like import OpenAILike
from agno.tools import Toolkit

from agents.config import (
    DEFAULT_LLM_API_KEY,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TEMPERATURE,
)
from core.audit import audit as run_audit, print_versions
from core.book import load, validate
from core.news import (
    apply_draft,
    collect_commits,
    get_sync_commit,
    group_by_section,
    write_draft,
)
from core.stats import apply_stats, compare_with_region, measure

# ---------------------------------------------------------------------------
# Path validation helpers
# ---------------------------------------------------------------------------

_ALLOWED_ROOTS_ENV = "BOOK_SYNC_ALLOWED_ROOTS"


def _allowed_roots() -> list[Path] | None:
    """Return the list of allowed parent roots, or None (any path allowed)."""
    raw = os.getenv(_ALLOWED_ROOTS_ENV)
    if not raw:
        return None
    return [Path(p).resolve() for p in raw.split(":") if p.strip()]


def _validate_book_path(path_str: str) -> Path:
    """Resolve *path_str* and verify it is a valid book root.

    Raises ``ValueError`` with a human-readable message on any problem:
    - not a directory
    - contains no ``book.yml``
    - symlinks resolve outside an allowed root (if ``BOOK_SYNC_ALLOWED_ROOTS`` is set)
    - ``book.yml`` fails to parse
    """
    p = Path(path_str).resolve()
    if not p.is_dir():
        raise ValueError(f"Not a directory: {p}")
    if not (p / "book.yml").exists():
        raise ValueError(f"No book.yml found in: {p}")

    allowed = _allowed_roots()
    if allowed:
        if not any(str(p).startswith(str(root)) for root in allowed):
            raise ValueError(
                f"Path {p} is not under any allowed root. "
                f"Set {_ALLOWED_ROOTS_ENV} to allow it."
            )

    # Validate the contract.
    errors = validate(p)
    if errors:
        raise ValueError("book.yml validation errors:\n" + "\n".join(f"  {e}" for e in errors))

    return p


def _safe_path(root: Path, rel: str) -> Path:
    """Resolve *rel* relative to *root* and ensure it stays inside *root*."""
    resolved = (root / rel).resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path escapes book root: {rel!r}")
    return resolved


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def tool_validate(book_path: str) -> str:
    """Validate book.yml and the book's files.  Returns a summary."""
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    errors = validate(root)
    if errors:
        return "Validation errors:\n" + "\n".join(f"  • {e}" for e in errors)
    cfg = load(root)
    return f"✓ {cfg.name} ({root}) — book.yml is valid"


def tool_audit(book_path: str, fix: bool = False) -> str:
    """Run all three checks (GitHub URLs, mkdocs nav, versions).

    Set fix=True to rewrite fixable problems in the docs (requires confirmation).
    Returns a summary of errors, warnings and fixes.
    """
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    cfg = load(root)
    results = run_audit(cfg, fix=fix)
    lines: list[str] = [f"Audit — {cfg.name} ({root})"]
    for r in results:
        status = "✓" if r.ok else "✗"
        lines.append(f"  {status} {r.check}")
        lines.extend(f"    ERROR  {e}" for e in r.errors)
        lines.extend(f"    WARN   {w}" for w in r.warnings)
        lines.extend(f"    FIXED  {f}" for f in r.fixed)
    return "\n".join(lines)


def tool_versions(book_path: str) -> str:
    """Print the canonical version for each configured versions entry."""
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    cfg = load(root)
    rows = print_versions(cfg)
    if not rows:
        return "No versions configured."
    lines = [f"Versions — {cfg.name}"]
    for r in rows:
        lines.append(f"  {r['id']}: {r['canonical']}  (from {r['source_file']})")
    return "\n".join(lines)


def tool_news_draft(book_path: str, since: str | None = None) -> str:
    """Collect commits since the last sync and write a draft to .context/news-draft.md.

    The draft is NOT applied to docs — the user must review it and call apply_news.
    Returns the draft content for review.
    """
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    cfg = load(root)
    since_commit = since or get_sync_commit(cfg)
    if since_commit is None:
        return (
            "No sync marker found.  Pass since=<commit-sha> to start from a specific commit."
        )
    commits = collect_commits(cfg, since_commit=since_commit)
    if not commits:
        return "No new commits since the last sync."
    newest = commits[0].sha
    groups = group_by_section(cfg, commits)
    draft_path = write_draft(cfg, groups, since_commit, newest_commit=newest)
    total = sum(len(v) for v in groups.values())
    draft_text = draft_path.read_text(encoding="utf-8")
    return (
        f"Draft written to {draft_path}  ({total} commit(s) across {len(groups)} section(s)).\n"
        f"Book root: {root}\n\n"
        f"--- DRAFT ---\n{draft_text}"
    )


def tool_stats(book_path: str) -> str:
    """Measure stats counters and compare with the stats region in the index file."""
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    cfg = load(root)
    measured = measure(cfg)
    if not measured:
        return "No stats configured."
    lines = [f"Stats — {cfg.name}  (book root: {root})"]
    for m in measured:
        lines.append(f"  {m.id}: {m.count} {m.label}")
    drift = compare_with_region(cfg, measured)
    if drift:
        lines.append("Drift detected:")
        lines.extend(f"  DRIFT  {w}" for w in drift)
    else:
        lines.append("Stats region is in sync.")
    return "\n".join(lines)


# ---- write tools (require confirmation) ------------------------------------

def tool_apply_news(book_path: str, region: str = "news-site") -> str:
    """Apply the reviewed .context/news-draft.md into the marked region.

    WRITE OPERATION — requires confirmation before executing.
    Also updates the news-log region and the book:sync marker.
    """
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    cfg = load(root)
    draft_path = cfg.scratch_path() / "news-draft.md"
    try:
        apply_draft(cfg, draft_path, region=region)
    except (FileNotFoundError, ValueError) as exc:
        return f"ERROR: {exc}"
    return f"✓ Applied {draft_path} → {cfg.sync_file()}  (book root: {root})"


def tool_apply_stats(book_path: str) -> str:
    """Write measured stats into the stats region of the index file.

    WRITE OPERATION — requires confirmation before executing.
    """
    try:
        root = _validate_book_path(book_path)
    except ValueError as exc:
        return f"ERROR: {exc}"
    cfg = load(root)
    measured = measure(cfg)
    if not measured:
        return "No stats configured — nothing to write."
    try:
        apply_stats(cfg, measured)
    except (FileNotFoundError, ValueError) as exc:
        return f"ERROR: {exc}"
    return f"✓ Stats region updated in {cfg.index_path()}  (book root: {root})"


def tool_apply_audit_fix(book_path: str) -> str:
    """Re-run audit with fix=True to rewrite broken GitHub links and version strings.

    WRITE OPERATION — requires confirmation before executing.
    """
    return tool_audit(book_path, fix=True)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_INSTRUCTIONS = """\
You are book-sync, an assistant for maintaining MkDocs-based technical books.

## Your scope
- The user tells you which book to work on by providing a directory path.
- All operations are scoped to that book's root directory (resolved from book.yml).
- You must show the resolved book root in every tool result.
- Never edit files outside the book root or outside the regions marked with
  <!-- book:...:start --> / <!-- book:...:end --> markers.

## News curation rules
- Summarize and group commit messages by section.
- Never invent items; drop anything not traceable to a commit.
- Use bullet points and the YYYY-MM date format.
- Present the draft for human review before applying.

## Write operations
- Apply only after the user has reviewed the draft or the audit results.
- For tool_apply_news, tool_apply_stats, and tool_apply_audit_fix, always
  summarize what will change and wait for confirmation.

## What you cannot do
- Run arbitrary shell commands.
- Edit files other than the index and news files named in book.yml.
- Commit or push to git.
"""

_WRITE_TOOLS = [
    "tool_apply_news",
    "tool_apply_stats",
    "tool_apply_audit_fix",
]


def build_agent() -> Agent:
    """Build the book_sync agent."""
    model = OpenAILike(
        id=DEFAULT_LLM_MODEL,
        base_url=DEFAULT_LLM_BASE_URL,
        temperature=DEFAULT_LLM_TEMPERATURE,
        api_key=DEFAULT_LLM_API_KEY,
    )
    toolkit = Toolkit(
        name="book_sync_tools",
        tools=[
            tool_validate,
            tool_audit,
            tool_versions,
            tool_news_draft,
            tool_stats,
            tool_apply_news,
            tool_apply_stats,
            tool_apply_audit_fix,
        ],
        requires_confirmation_tools=_WRITE_TOOLS,
    )
    return Agent(
        name="Book Sync",
        model=model,
        tools=[toolkit],
        instructions=_INSTRUCTIONS,
        markdown=True,
    )


# ---------------------------------------------------------------------------
# CLI entry point (terminal chat)
# ---------------------------------------------------------------------------

def main() -> None:
    agent = build_agent()
    agent.cli_app()


if __name__ == "__main__":
    main()
