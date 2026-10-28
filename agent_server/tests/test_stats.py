"""
tests/test_stats.py — tests for core/stats.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.book import load
from core.stats import (
    StatMeasurement,
    apply_stats,
    compare_with_region,
    measure,
    write_stats_region,
)
from tests.fixtures import book_root  # noqa: F401


class TestMeasure:
    def test_counts_sql_files(self, book_root: Path) -> None:
        cfg = load(book_root)
        results = measure(cfg)
        sql = next(r for r in results if r.id == "sql_scripts")
        # fixture has code/query.sql and code/new.sql → 2
        assert sql.count == 2

    def test_returns_zero_when_no_files_match(self, book_root: Path) -> None:
        cfg = load(book_root)
        (book_root / "code" / "query.sql").unlink()
        (book_root / "code" / "new.sql").unlink()
        results = measure(cfg)
        sql = next(r for r in results if r.id == "sql_scripts")
        assert sql.count == 0

    def test_empty_stats_returns_empty_list(self, book_root: Path) -> None:
        import yaml
        book_yml = book_root / "book.yml"
        raw = yaml.safe_load(book_yml.read_text())
        raw.pop("stats", None)
        book_yml.write_text(yaml.dump(raw))
        cfg = load(book_root)
        assert measure(cfg) == []


class TestCompareWithRegion:
    def test_no_stats_region_returns_warning(self, book_root: Path) -> None:
        cfg = load(book_root)
        drift = compare_with_region(cfg, [StatMeasurement("sql_scripts", "SQL scripts", 2)])
        assert any("stats region not found" in w for w in drift)

    def test_in_sync_returns_no_drift(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(
            idx.read_text()
            + "\n<!-- book:stats:start -->\n- 2 SQL scripts\n<!-- book:stats:end -->\n"
        )
        drift = compare_with_region(cfg, [StatMeasurement("sql_scripts", "SQL scripts", 2)])
        assert drift == []

    def test_drift_is_detected(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(
            idx.read_text()
            + "\n<!-- book:stats:start -->\n- 99 SQL scripts\n<!-- book:stats:end -->\n"
        )
        drift = compare_with_region(cfg, [StatMeasurement("sql_scripts", "SQL scripts", 2)])
        assert any("99" in w and "2" in w for w in drift)


class TestWriteStatsRegion:
    def test_generates_bullet_list(self) -> None:
        measured = [
            StatMeasurement("a", "SQL scripts", 10),
            StatMeasurement("b", "Java files", 20),
        ]
        text = write_stats_region(measured)
        assert "- 10 SQL scripts" in text
        assert "- 20 Java files" in text


class TestApplyStats:
    def test_writes_region(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(
            idx.read_text()
            + "\n<!-- book:stats:start -->\nold content\n<!-- book:stats:end -->\n"
        )
        measured = [StatMeasurement("sql_scripts", "SQL scripts", 5)]
        apply_stats(cfg, measured)
        text = idx.read_text()
        assert "- 5 SQL scripts" in text
        assert "old content" not in text

    def test_missing_markers_raises(self, book_root: Path) -> None:
        cfg = load(book_root)
        # index.md has no stats markers
        with pytest.raises(ValueError, match="stats"):
            apply_stats(cfg, [StatMeasurement("x", "x", 1)])

    def test_no_agno_import(self) -> None:
        import ast
        import importlib.util

        spec = importlib.util.find_spec("core.stats")
        assert spec is not None
        source = Path(spec.origin).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else ([node.module] if node.module else [])
                )
                for name in names:
                    assert not (name or "").startswith("agno"), (
                        f"core/stats.py must not import agno, found: {name!r}"
                    )
