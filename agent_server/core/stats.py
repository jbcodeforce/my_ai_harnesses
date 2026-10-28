"""
core/stats.py — glob-based counters and stats-region comparison.

Public API
----------
measure(cfg)                    -> list[StatMeasurement]
compare_with_region(cfg, measured) -> list[str]   (drift warnings, empty = OK)
write_stats_region(cfg, measured)  -> str         (new region text, not written yet)
apply_stats(cfg, measured)         -> None         (writes the region in-place)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.book import BookConfig, StatConfig


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

@dataclass
class StatMeasurement:
    id: str
    label: str
    count: int


def _count_files(root: Path, include: list[str], exclude: list[str]) -> int:
    """Count files matching at least one include glob, not matching any exclude glob."""
    seen: set[Path] = set()
    for pat in include:
        for p in root.glob(pat):
            if p.is_file():
                seen.add(p)

    # Apply excludes.
    if exclude:
        to_remove: set[Path] = set()
        for ex_pat in exclude:
            for p in root.glob(ex_pat):
                to_remove.add(p)
        seen -= to_remove

    return len(seen)


def _count_dirs(root: Path, include: list[str]) -> int:
    """Count directories matching at least one include glob."""
    seen: set[Path] = set()
    for pat in include:
        for p in root.glob(pat):
            if p.is_dir():
                seen.add(p)
    return len(seen)


def measure(cfg: BookConfig) -> list[StatMeasurement]:
    """Measure all stats counters defined in ``book.yml``."""
    results: list[StatMeasurement] = []
    for stat in cfg.stats:
        if stat.count == "files":
            count = _count_files(cfg.root, stat.include, stat.exclude)
        elif stat.count == "dirs":
            count = _count_dirs(cfg.root, stat.include)
        else:
            count = 0
        results.append(StatMeasurement(id=stat.id, label=stat.label, count=count))
    return results


# ---------------------------------------------------------------------------
# Compare with region
# ---------------------------------------------------------------------------

# Matches lines like "- 20+ SQL scripts" or "- 50 Java source files"
_STAT_LINE_RE = re.compile(r"-\s+(\d+)\+?\s+(.+)")


def _parse_region_counts(region_text: str) -> dict[str, int]:
    """Extract ``{label: count}`` from the stats region text."""
    counts: dict[str, int] = {}
    for line in region_text.splitlines():
        m = _STAT_LINE_RE.search(line)
        if m:
            counts[m.group(2).strip()] = int(m.group(1))
    return counts


def _read_region(path: Path, region: str = "stats") -> str | None:
    """Read the content between ``book:<region>:start`` and ``:end`` markers.

    Returns None if the markers are absent.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    start_marker = f"<!-- book:{region}:start -->"
    end_marker   = f"<!-- book:{region}:end -->"
    si = text.find(start_marker)
    ei = text.find(end_marker)
    if si == -1 or ei == -1 or ei < si:
        return None
    return text[si + len(start_marker):ei]


def compare_with_region(cfg: BookConfig, measured: list[StatMeasurement]) -> list[str]:
    """Compare measured values against the numbers quoted in the stats region.

    Returns a list of human-readable drift warnings (empty = in sync).
    Also warns if the stats region is missing from the index file.
    """
    warnings: list[str] = []
    region_text = _read_region(cfg.index_path(), "stats")
    if region_text is None:
        warnings.append("stats region not found in index file (add <!-- book:stats:start/end --> markers)")
        return warnings

    current = _parse_region_counts(region_text)
    label_map = {m.label: m for m in measured}

    for label, doc_count in current.items():
        m = label_map.get(label)
        if m is None:
            warnings.append(f"stats: label {label!r} in region but not in book.yml — skipped")
            continue
        if m.count != doc_count:
            warnings.append(
                f"stats[{m.id}]: docs say {doc_count} {label!r}, measured {m.count}"
            )

    return warnings


# ---------------------------------------------------------------------------
# Write / apply
# ---------------------------------------------------------------------------

def write_stats_region(measured: list[StatMeasurement]) -> str:
    """Return the replacement text for the stats region (without the markers)."""
    lines = [f"- {m.count} {m.label}" for m in measured]
    return "\n".join(lines)


def apply_stats(cfg: BookConfig, measured: list[StatMeasurement]) -> None:
    """Write the measured stats into the ``stats`` region of the index file.

    Raises ``ValueError`` if the stats markers are missing.
    """
    from core.news import _replace_region  # avoid circular import at module level

    index_path = cfg.index_path()
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    text = index_path.read_text(encoding="utf-8")
    new_content = write_stats_region(measured)
    new_text = _replace_region(text, "stats", new_content)
    index_path.write_text(new_text, encoding="utf-8")
