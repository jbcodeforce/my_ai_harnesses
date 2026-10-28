"""
core/audit.py — book-generic audit checks.

All three checks from ``tools/doc_sync.py`` are ported here with every
flink-specific constant replaced by lookups in ``BookConfig``.

Public API
----------
check_github_urls(cfg, fix=False)  -> AuditResult
check_mkdocs_nav(cfg)              -> AuditResult
check_versions(cfg, fix=False)     -> AuditResult
audit(cfg, fix=False)              -> list[AuditResult]

``fix=True`` rewrites problems in-place.  Every function is pure until
``fix=True``; it then writes to the book's docs files only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from core.book import BookConfig, load_yaml_tolerant


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AuditResult:
    check: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md_files(docs_dir: Path) -> Iterator[Path]:
    """Yield all .md files under *docs_dir* (recursively)."""
    yield from docs_dir.rglob("*.md")


def _nav_md_entries(nav_node: object, base: str = "") -> Iterator[str]:
    """Walk an mkdocs nav structure and yield relative .md paths."""
    if isinstance(nav_node, list):
        for item in nav_node:
            yield from _nav_md_entries(item, base)
    elif isinstance(nav_node, dict):
        for value in nav_node.values():
            yield from _nav_md_entries(value, base)
    elif isinstance(nav_node, str):
        if not nav_node.startswith("http"):
            yield nav_node


# ---------------------------------------------------------------------------
# 1. GitHub URL check
# ---------------------------------------------------------------------------

_GITHUB_BLOB_RE = re.compile(
    r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"/(?:blob|tree)/(?P<branch>[^/]+)/(?P<path>[^\s\"')>]+)"
)


def check_github_urls(cfg: BookConfig, fix: bool = False) -> AuditResult:
    """Check that GitHub blob/tree links in docs point to the canonical branch.

    Wrong-branch links are reported as errors; with ``fix=True`` they are
    rewritten to the branch declared in ``book.yml``.
    """
    result = AuditResult(check="github_urls")
    canonical_branch = cfg.repo.branch
    repo_url_prefix = cfg.repo.url  # e.g. https://github.com/jbcodeforce/flink-studies

    docs_dir = cfg.docs_path()
    if not docs_dir.is_dir():
        result.errors.append(f"docs directory not found: {docs_dir}")
        return result

    for md_file in _md_files(docs_dir):
        text = md_file.read_text(encoding="utf-8")
        new_text = text

        for m in _GITHUB_BLOB_RE.finditer(text):
            full_url = m.group(0)
            branch = m.group("branch")
            # Only check links that point to this book's repo.
            owner_repo = f"https://github.com/{m.group('owner')}/{m.group('repo')}"
            if owner_repo != repo_url_prefix:
                continue
            if branch == canonical_branch:
                continue
            # Wrong branch
            correct_url = full_url.replace(
                f"/{branch}/", f"/{canonical_branch}/"
            )
            msg = f"{md_file.relative_to(cfg.root)}: {full_url!r} → {correct_url!r}"
            if fix:
                new_text = new_text.replace(full_url, correct_url)
                result.fixed.append(msg)
            else:
                result.errors.append(msg)

        if fix and new_text != text:
            md_file.write_text(new_text, encoding="utf-8")

    # Apply fix_rules for broken repo paths in links
    if fix and cfg.fix_rules:
        for md_file in _md_files(docs_dir):
            text = md_file.read_text(encoding="utf-8")
            new_text = text
            for rule in cfg.fix_rules:
                pattern = re.compile(rule.match)
                for m in pattern.finditer(new_text):
                    candidate = pattern.sub(rule.replace, m.group(0))
                    # Only apply if the rewritten path exists.
                    if cfg.abs(candidate).exists():
                        new_text = new_text.replace(m.group(0), candidate)
                        result.fixed.append(
                            f"{md_file.relative_to(cfg.root)}: fix_rule "
                            f"{m.group(0)!r} → {candidate!r}"
                        )
            if new_text != text:
                md_file.write_text(new_text, encoding="utf-8")

    return result


# ---------------------------------------------------------------------------
# 2. MkDocs nav check
# ---------------------------------------------------------------------------

def check_mkdocs_nav(cfg: BookConfig) -> AuditResult:
    """Check that every .md file listed in the mkdocs nav exists on disk."""
    result = AuditResult(check="mkdocs_nav")
    mkdocs_path = cfg.mkdocs_path()

    if not mkdocs_path.exists():
        result.errors.append(f"mkdocs.yml not found: {mkdocs_path}")
        return result

    try:
        mkdocs = load_yaml_tolerant(mkdocs_path)
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"could not parse mkdocs.yml: {exc}")
        return result

    nav = mkdocs.get("nav") if isinstance(mkdocs, dict) else None
    if not nav:
        result.warnings.append("mkdocs.yml has no 'nav' key — skipping nav check")
        return result

    docs_dir = cfg.docs_path()
    for rel_path in _nav_md_entries(nav):
        full = docs_dir / rel_path
        if not full.exists():
            result.errors.append(f"nav entry not found: {rel_path}")

    return result


# ---------------------------------------------------------------------------
# 3. Version check
# ---------------------------------------------------------------------------

def _extract_version(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def check_versions(cfg: BookConfig, fix: bool = False) -> AuditResult:
    """Check that version strings in docs match the canonical source.

    For each ``versions`` entry in ``book.yml``:
    - Extract the canonical version from ``source.file`` using ``source.pattern``.
    - Search all docs .md files for ``docs_pattern``.
    - Report mismatches; with ``fix=True`` rewrite docs to the canonical version.
    """
    result = AuditResult(check="versions")

    for vc in cfg.versions:
        if not vc.source_file or not vc.source_pattern:
            result.warnings.append(f"versions[{vc.id}]: source not configured — skipped")
            continue

        src_path = cfg.abs(vc.source_file)
        if not src_path.exists():
            result.errors.append(f"versions[{vc.id}]: source file not found: {src_path}")
            continue

        canonical = _extract_version(vc.source_pattern, src_path.read_text(encoding="utf-8"))
        if canonical is None:
            result.errors.append(
                f"versions[{vc.id}]: pattern {vc.source_pattern!r} "
                f"not found in {vc.source_file}"
            )
            continue

        if not vc.docs_pattern:
            # Nothing to check against docs — just report the canonical value.
            result.warnings.append(f"versions[{vc.id}]: {canonical} (no docs_pattern)")
            continue

        docs_dir = cfg.docs_path()
        for md_file in _md_files(docs_dir):
            text = md_file.read_text(encoding="utf-8")
            for m in re.finditer(vc.docs_pattern, text):
                found_version = m.group(1)
                if found_version == canonical:
                    continue
                old_match = m.group(0)
                new_match = old_match.replace(found_version, canonical)
                msg = (
                    f"{md_file.relative_to(cfg.root)}: "
                    f"versions[{vc.id}] {found_version!r} → {canonical!r}"
                )
                if fix and vc.fix:
                    text = text.replace(old_match, new_match)
                    result.fixed.append(msg)
                else:
                    result.errors.append(msg)
            if fix and vc.fix:
                md_file.write_text(text, encoding="utf-8")

    return result


def print_versions(cfg: BookConfig) -> list[dict[str, str]]:
    """Return a list of ``{id, canonical, source_file}`` dicts for display."""
    rows = []
    for vc in cfg.versions:
        if not vc.source_file or not vc.source_pattern:
            rows.append({"id": vc.id, "canonical": "(no source)", "source_file": ""})
            continue
        src_path = cfg.abs(vc.source_file)
        if not src_path.exists():
            rows.append({"id": vc.id, "canonical": "(file missing)", "source_file": vc.source_file})
            continue
        canonical = _extract_version(vc.source_pattern, src_path.read_text(encoding="utf-8"))
        rows.append({
            "id": vc.id,
            "canonical": canonical or "(not found)",
            "source_file": vc.source_file,
        })
    return rows


# ---------------------------------------------------------------------------
# Combined audit
# ---------------------------------------------------------------------------

def audit(cfg: BookConfig, fix: bool = False) -> list[AuditResult]:
    """Run all three checks.  Returns a list of three AuditResult objects."""
    return [
        check_github_urls(cfg, fix=fix),
        check_mkdocs_nav(cfg),
        check_versions(cfg, fix=fix),
    ]
