"""
tests/test_cli.py — tests for cli/book_sync.py (validate and init commands).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.book_sync import app
from tests.fixtures import book_root, book_root_no_markers  # noqa: F401

runner = CliRunner()


class TestValidateCommand:
    def test_valid_book_exits_0(self, book_root: Path) -> None:
        result = runner.invoke(app, ["validate", str(book_root)])
        assert result.exit_code == 0, result.output
        assert "valid" in result.output

    def test_invalid_book_exits_1(self, book_root: Path) -> None:
        (book_root / "docs" / "index.md").unlink()
        result = runner.invoke(app, ["validate", str(book_root)])
        assert result.exit_code == 1

    def test_missing_book_yml_exits_nonzero(self, tmp_path: Path) -> None:
        # tmp_path has no book.yml — validate should fail
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code != 0


class TestInitCommand:
    def test_init_creates_book_yml(self, tmp_path: Path) -> None:
        root = tmp_path / "new-book"
        root.mkdir()
        (root / "docs").mkdir()
        (root / "docs" / "index.md").write_text("# New Book\n")
        (root / "mkdocs.yml").write_text("site_name: New Book\n")

        result = runner.invoke(app, ["init", str(root)])
        assert result.exit_code == 0, result.output
        assert (root / "book.yml").exists()
        assert (root / "AGENTS.md").exists()
        assert (root / ".context").is_dir()

    def test_init_does_not_overwrite_existing_book_yml(self, book_root: Path) -> None:
        original = (book_root / "book.yml").read_text()
        result = runner.invoke(app, ["init", str(book_root)])
        assert result.exit_code == 0
        assert (book_root / "book.yml").read_text() == original
        assert "already exists" in result.output

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        root = tmp_path / "dry-book"
        root.mkdir()
        result = runner.invoke(app, ["init", "--dry-run", str(root)])
        assert result.exit_code == 0
        assert not (root / "book.yml").exists()
        assert "DRY RUN" in result.output

    def test_init_inserts_markers_in_existing_admonition(
        self, book_root_no_markers: Path
    ) -> None:
        result = runner.invoke(app, ["init", str(book_root_no_markers)])
        assert result.exit_code == 0, result.output
        text = (book_root_no_markers / "docs" / "index.md").read_text()
        assert "<!-- book:updates:start -->" in text
        assert "<!-- book:updates:end -->" in text

    def test_init_is_idempotent_on_markers(self, book_root: Path) -> None:
        """Running init twice must not duplicate markers."""
        runner.invoke(app, ["init", str(book_root)])
        runner.invoke(app, ["init", str(book_root)])
        text = (book_root / "docs" / "index.md").read_text()
        assert text.count("<!-- book:updates:start -->") == 1
