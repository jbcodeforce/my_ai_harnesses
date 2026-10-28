"""
tests/test_book_sync_agent.py — tests for agents/book_sync.py tool functions.

These tests call tool functions directly (no LLM) against the fixture book.
They verify path validation, read tools, and write tools.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.book_sync import (
    _validate_book_path,
    tool_audit,
    tool_news_draft,
    tool_stats,
    tool_validate,
    tool_versions,
    tool_apply_stats,
)
from tests.fixtures import book_root  # noqa: F401


class TestValidateBookPath:
    def test_rejects_nonexistent_path(self) -> None:
        with pytest.raises(ValueError, match="Not a directory"):
            _validate_book_path("/nonexistent/path/xyz")

    def test_rejects_path_without_book_yml(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No book.yml"):
            _validate_book_path(str(tmp_path))

    def test_accepts_valid_book(self, book_root: Path) -> None:
        root = _validate_book_path(str(book_root))
        assert root == book_root

    def test_allowed_roots_env_restricts_access(
        self, book_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOOK_SYNC_ALLOWED_ROOTS", "/some/other/path")
        with pytest.raises(ValueError, match="not under any allowed root"):
            _validate_book_path(str(book_root))

    def test_allowed_roots_env_permits_valid_path(
        self, book_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOOK_SYNC_ALLOWED_ROOTS", str(book_root.parent))
        root = _validate_book_path(str(book_root))
        assert root == book_root


class TestReadTools:
    def test_tool_validate_returns_ok(self, book_root: Path) -> None:
        result = tool_validate(str(book_root))
        assert "valid" in result
        assert "ERROR" not in result

    def test_tool_validate_returns_error_for_bad_path(self) -> None:
        result = tool_validate("/nonexistent")
        assert result.startswith("ERROR")

    def test_tool_audit_returns_check_names(self, book_root: Path) -> None:
        result = tool_audit(str(book_root))
        assert "github_urls" in result
        assert "mkdocs_nav" in result
        assert "versions" in result
        assert str(book_root) in result

    def test_tool_versions_returns_canonical(self, book_root: Path) -> None:
        result = tool_versions(str(book_root))
        assert "cp-kafka" in result
        assert "7.8.0" in result

    def test_tool_news_draft_with_since(self, book_root: Path) -> None:
        # Use the real initial commit SHA from the fixture git repo.
        import subprocess
        initial_sha = subprocess.run(
            ["git", "log", "--format=%H", "--reverse"],
            cwd=book_root, capture_output=True, text=True, check=True
        ).stdout.splitlines()[0]
        result = tool_news_draft(str(book_root), since=initial_sha)
        # Should produce a draft (2 non-noise commits after initial)
        assert "ERROR" not in result
        assert "draft" in result.lower() or "no new commits" in result

    def test_tool_stats_returns_counts(self, book_root: Path) -> None:
        result = tool_stats(str(book_root))
        assert "sql_scripts" in result
        assert str(book_root) in result


class TestWriteTools:
    def test_tool_apply_stats_writes_region(self, book_root: Path) -> None:
        # Add stats markers to the index first
        idx = book_root / "docs" / "index.md"
        idx.write_text(
            idx.read_text()
            + "\n<!-- book:stats:start -->\nold\n<!-- book:stats:end -->\n"
        )
        result = tool_apply_stats(str(book_root))
        assert "ERROR" not in result
        assert "updated" in result.lower() or "✓" in result

    def test_tool_apply_stats_fails_gracefully_without_markers(
        self, book_root: Path
    ) -> None:
        # Index has no stats markers
        result = tool_apply_stats(str(book_root))
        assert "ERROR" in result
