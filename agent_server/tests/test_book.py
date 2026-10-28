"""
tests/test_book.py — tests for core/book.py (load and validate).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from core.book import load, validate
from tests.fixtures import book_root, book_root_no_markers  # noqa: F401 (fixtures)


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_valid_book(self, book_root: Path) -> None:
        cfg = load(book_root)
        assert cfg.name == "test-book"
        assert cfg.repo.url == "https://github.com/example/test-book"
        assert cfg.repo.branch == "main"
        assert cfg.paths.docs == "docs"
        assert cfg.paths.news == "docs/news/index.md"
        assert len(cfg.sections) == 2
        assert cfg.sections[0].title == "Coding"
        assert len(cfg.stats) == 1
        assert cfg.stats[0].id == "sql_scripts"
        assert len(cfg.versions) == 1
        assert cfg.versions[0].id == "cp-kafka"
        assert len(cfg.ignore_commits) == 2

    def test_missing_book_yml(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load(tmp_path)

    def test_missing_required_key(self, tmp_path: Path) -> None:
        (tmp_path / "book.yml").write_text("name: x\nrepo:\n  url: u\n  branch: b\n")
        with pytest.raises(ValueError, match="schema"):
            load(tmp_path)

    def test_missing_repo_branch(self, tmp_path: Path) -> None:
        (tmp_path / "book.yml").write_text("schema: 1\nname: x\nrepo:\n  url: u\n")
        with pytest.raises(ValueError, match="repo.branch"):
            load(tmp_path)

    def test_abs_helper(self, book_root: Path) -> None:
        cfg = load(book_root)
        assert cfg.abs("docs/index.md") == book_root / "docs" / "index.md"

    def test_sync_file_is_news_when_present(self, book_root: Path) -> None:
        cfg = load(book_root)
        assert cfg.sync_file().name == "index.md"
        assert "news" in str(cfg.sync_file())


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_book_has_no_errors(self, book_root: Path) -> None:
        errors = validate(book_root)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_index_is_an_error(self, book_root: Path) -> None:
        (book_root / "docs" / "index.md").unlink()
        errors = validate(book_root)
        assert any("paths.index" in e for e in errors)

    def test_missing_updates_marker_is_an_error(self, book_root: Path) -> None:
        idx = book_root / "docs" / "index.md"
        # Remove the start marker
        text = idx.read_text()
        idx.write_text(text.replace("<!-- book:updates:start -->", ""))
        errors = validate(book_root)
        assert any("updates" in e for e in errors)

    def test_missing_news_markers_are_errors(self, book_root: Path) -> None:
        news = book_root / "docs" / "news" / "index.md"
        news.write_text("# News\n\nNo markers here.\n")
        errors = validate(book_root)
        assert any("news-site" in e for e in errors)
        assert any("news-log" in e for e in errors)

    def test_missing_sync_marker_is_an_error(self, book_root: Path) -> None:
        news = book_root / "docs" / "news" / "index.md"
        text = news.read_text()
        news.write_text(text.replace("<!-- book:sync commit=abc1234 date=2024-01 -->", ""))
        errors = validate(book_root)
        assert any("sync marker" in e for e in errors)

    def test_invalid_regex_in_ignore_commits(self, book_root: Path) -> None:
        book_yml = book_root / "book.yml"
        raw = yaml.safe_load(book_yml.read_text())
        raw["ignore_commits"] = ["[invalid"]
        book_yml.write_text(yaml.dump(raw))
        errors = validate(book_root)
        assert any("invalid regex" in e for e in errors)

    def test_absolute_path_is_rejected(self, book_root: Path) -> None:
        book_yml = book_root / "book.yml"
        raw = yaml.safe_load(book_yml.read_text())
        raw["paths"] = {"index": "/etc/passwd"}
        book_yml.write_text(yaml.dump(raw))
        errors = validate(book_root)
        assert any("absolute" in e for e in errors)

    def test_missing_version_source_file_is_an_error(self, book_root: Path) -> None:
        (book_root / "deployment" / "docker-compose.yaml").unlink()
        errors = validate(book_root)
        assert any("cp-kafka" in e and "not found" in e for e in errors)


# ---------------------------------------------------------------------------
# Guard: core/ must not import agno
# ---------------------------------------------------------------------------

class TestNoAgnoImport:
    def test_core_book_does_not_import_agno(self) -> None:
        import ast
        import importlib.util

        spec = importlib.util.find_spec("core.book")
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
                        f"core/book.py must not import agno, found: {name!r}"
                    )
