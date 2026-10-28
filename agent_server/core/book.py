"""
core/book.py — load, validate and resolve a book.yml contract.

No agno import.  Works with the standard library + PyYAML only.

Public API
----------
load(root)         -> BookConfig
validate(root)     -> list[str]   (human-readable error lines; empty = OK)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# YAML loader that tolerates !!python/name: tags in mkdocs.yml files
# ---------------------------------------------------------------------------

class _TagTolerantLoader(yaml.SafeLoader):
    """SafeLoader that maps unknown tags to plain strings instead of failing."""


def _tag_constructor(loader: yaml.Loader, tag_suffix: str, node: yaml.Node) -> str:
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_TagTolerantLoader.add_multi_constructor("", _tag_constructor)


def load_yaml_tolerant(path: Path) -> Any:
    """Load a YAML file, silently converting unsupported tags to strings."""
    with path.open(encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_TagTolerantLoader)  # noqa: S506 (controlled loader)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RepoConfig:
    url: str
    branch: str


@dataclass
class PathsConfig:
    docs: str = "docs"
    mkdocs: str = "mkdocs.yml"
    index: str = "docs/index.md"
    news: str | None = None
    changelog: str | None = None
    scratch: str = ".context"


@dataclass
class SectionConfig:
    title: str
    paths: list[str] = field(default_factory=list)


@dataclass
class StatConfig:
    id: str
    label: str
    count: str          # "files" | "dirs"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class VersionConfig:
    id: str
    source_file: str
    source_pattern: str
    docs_pattern: str | None = None
    fix: bool = False


@dataclass
class FixRule:
    match: str
    replace: str


@dataclass
class BookConfig:
    root: Path
    schema_version: int
    name: str
    repo: RepoConfig
    site_url: str | None
    paths: PathsConfig
    sections: list[SectionConfig]
    ignore_commits: list[str]
    stats: list[StatConfig]
    versions: list[VersionConfig]
    fix_rules: list[FixRule]

    # -----------------------------------------------------------------------
    # Convenience helpers
    # -----------------------------------------------------------------------

    def abs(self, rel: str) -> Path:
        """Resolve a path relative to the book root."""
        return (self.root / rel).resolve()

    def index_path(self) -> Path:
        return self.abs(self.paths.index)

    def news_path(self) -> Path | None:
        return self.abs(self.paths.news) if self.paths.news else None

    def changelog_path(self) -> Path | None:
        return self.abs(self.paths.changelog) if self.paths.changelog else None

    def mkdocs_path(self) -> Path:
        return self.abs(self.paths.mkdocs)

    def docs_path(self) -> Path:
        return self.abs(self.paths.docs)

    def scratch_path(self) -> Path:
        return self.abs(self.paths.scratch)

    def sync_file(self) -> Path:
        """File that carries the ``book:sync`` marker."""
        return self.news_path() or self.index_path()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = ("schema", "name", "repo")


def _parse_paths(raw: dict[str, Any]) -> PathsConfig:
    p = raw.get("paths") or {}
    return PathsConfig(
        docs=p.get("docs", "docs"),
        mkdocs=p.get("mkdocs", "mkdocs.yml"),
        index=p.get("index", "docs/index.md"),
        news=p.get("news"),
        changelog=p.get("changelog"),
        scratch=p.get("scratch", ".context"),
    )


def _parse_sections(raw: list[dict]) -> list[SectionConfig]:
    result = []
    for s in raw or []:
        result.append(SectionConfig(
            title=s["title"],
            paths=s.get("paths") or [],
        ))
    return result


def _parse_stats(raw: list[dict]) -> list[StatConfig]:
    result = []
    for s in raw or []:
        result.append(StatConfig(
            id=s["id"],
            label=s.get("label", s["id"]),
            count=s.get("count", "files"),
            include=s.get("include") or [],
            exclude=s.get("exclude") or [],
        ))
    return result


def _parse_versions(raw: list[dict]) -> list[VersionConfig]:
    result = []
    for v in raw or []:
        src = v.get("source") or {}
        result.append(VersionConfig(
            id=v["id"],
            source_file=src.get("file", ""),
            source_pattern=src.get("pattern", ""),
            docs_pattern=v.get("docs_pattern"),
            fix=bool(v.get("fix", False)),
        ))
    return result


def _parse_fix_rules(raw: list[dict]) -> list[FixRule]:
    result = []
    for r in raw or []:
        result.append(FixRule(match=r["match"], replace=r["replace"]))
    return result


def _reject_unsafe_path(rel: str, field_name: str) -> str | None:
    """Return an error string if *rel* is absolute or escapes the root."""
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        return f"{field_name}: absolute paths are not allowed ({rel!r})"
    parts = p.parts
    if ".." in parts:
        return f"{field_name}: paths with '..' are not allowed ({rel!r})"
    return None


def load(root: str | Path) -> "BookConfig":
    """Load and parse ``book.yml`` from *root*.

    Raises ``FileNotFoundError`` if the file is missing.
    Raises ``ValueError`` for missing required keys or malformed values.
    """
    root = Path(root).resolve()
    book_file = root / "book.yml"
    if not book_file.exists():
        raise FileNotFoundError(f"book.yml not found in {root}")

    with book_file.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    for key in _REQUIRED_KEYS:
        if key not in raw:
            raise ValueError(f"book.yml is missing required key: {key!r}")

    repo_raw = raw["repo"]
    if not isinstance(repo_raw, dict):
        raise ValueError("book.yml: 'repo' must be a mapping")
    for sub in ("url", "branch"):
        if not repo_raw.get(sub):
            raise ValueError(f"book.yml: 'repo.{sub}' is required")

    return BookConfig(
        root=root,
        schema_version=int(raw.get("schema", 1)),
        name=str(raw["name"]),
        repo=RepoConfig(url=repo_raw["url"], branch=repo_raw["branch"]),
        site_url=raw.get("site_url"),
        paths=_parse_paths(raw),
        sections=_parse_sections(raw.get("sections") or []),
        ignore_commits=[str(p) for p in (raw.get("ignore_commits") or [])],
        stats=_parse_stats(raw.get("stats") or []),
        versions=_parse_versions(raw.get("versions") or []),
        fix_rules=_parse_fix_rules(raw.get("fix_rules") or []),
    )


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

_MARKER_PAIRS = {
    "updates":  ("<!-- book:updates:start -->",  "<!-- book:updates:end -->"),
    "stats":    ("<!-- book:stats:start -->",     "<!-- book:stats:end -->"),
    "news-site":("<!-- book:news-site:start -->", "<!-- book:news-site:end -->"),
    "news-log": ("<!-- book:news-log:start -->",  "<!-- book:news-log:end -->"),
}
_SYNC_MARKER_RE = re.compile(r"<!--\s*book:sync\s+commit=\S+\s+date=\S+\s*-->")


def _check_markers(path: Path, needed: list[str]) -> list[str]:
    """Return error lines for missing or mis-ordered markers in *path*."""
    errors: list[str] = []
    if not path.exists():
        errors.append(f"file missing: {path}")
        return errors
    text = path.read_text(encoding="utf-8")
    for name in needed:
        start, end = _MARKER_PAIRS[name]
        si = text.find(start)
        ei = text.find(end)
        if si == -1:
            errors.append(f"{path}: missing marker {start!r}")
        elif ei == -1:
            errors.append(f"{path}: missing marker {end!r}")
        elif ei < si:
            errors.append(f"{path}: end marker appears before start for {name!r}")
    return errors


def validate(root: str | Path) -> list[str]:
    """Validate the book at *root*.  Returns a (possibly empty) list of errors.

    Checks performed:
    1. ``book.yml`` loads and passes schema checks.
    2. Required paths exist.
    3. No absolute or ``..`` paths in ``book.yml``.
    4. Regex patterns in ``versions`` and ``ignore_commits`` compile.
    5. Required markers are present in the index and news files.
    6. ``versions`` source files exist.
    """
    errors: list[str] = []

    # 1. Load
    try:
        cfg = load(root)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]

    # 2. Required files
    for label, path in [
        ("paths.index", cfg.index_path()),
        ("paths.mkdocs", cfg.mkdocs_path()),
    ]:
        if not path.exists():
            errors.append(f"{label} does not exist: {path}")

    # 3. Path safety
    all_path_fields = {
        "paths.docs": cfg.paths.docs,
        "paths.mkdocs": cfg.paths.mkdocs,
        "paths.index": cfg.paths.index,
        "paths.news": cfg.paths.news or "",
        "paths.changelog": cfg.paths.changelog or "",
        "paths.scratch": cfg.paths.scratch,
    }
    for fld, rel in all_path_fields.items():
        if rel:
            err = _reject_unsafe_path(rel, fld)
            if err:
                errors.append(err)

    # 4. Regex patterns
    for vc in cfg.versions:
        for attr, pattern in [
            (f"versions[{vc.id}].source.pattern", vc.source_pattern),
            (f"versions[{vc.id}].docs_pattern", vc.docs_pattern or ""),
        ]:
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"{attr}: invalid regex — {exc}")

    for i, pat in enumerate(cfg.ignore_commits):
        try:
            re.compile(pat)
        except re.error as exc:
            errors.append(f"ignore_commits[{i}]: invalid regex — {exc}")

    # 5. Markers
    index_markers = ["updates"]
    if any(s.id == "stats" for s in cfg.stats):
        pass  # stats marker is optional; only check if explicitly present
    errors.extend(_check_markers(cfg.index_path(), index_markers))

    if cfg.paths.news:
        news_path = cfg.news_path()
        assert news_path is not None
        errors.extend(_check_markers(news_path, ["news-site", "news-log"]))
        # sync marker
        if news_path.exists():
            text = news_path.read_text(encoding="utf-8")
            if not _SYNC_MARKER_RE.search(text):
                errors.append(
                    f"{news_path}: sync marker missing "
                    "(expected <!-- book:sync commit=... date=... -->)"
                )

    # 6. Version source files
    for vc in cfg.versions:
        if vc.source_file:
            src = cfg.abs(vc.source_file)
            if not src.exists():
                errors.append(f"versions[{vc.id}].source.file not found: {src}")

    return errors
