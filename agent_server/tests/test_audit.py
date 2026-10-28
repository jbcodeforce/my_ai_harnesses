"""
tests/test_audit.py — tests for core/audit.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.audit import (
    AuditResult,
    audit,
    check_github_urls,
    check_mkdocs_nav,
    check_versions,
    print_versions,
)
from core.book import load
from tests.fixtures import book_root  # noqa: F401


class TestCheckGithubUrls:
    def test_no_errors_when_links_use_correct_branch(self, book_root: Path) -> None:
        # fixture has no GitHub links in docs, so should be clean
        cfg = load(book_root)
        result = check_github_urls(cfg)
        assert result.ok

    def test_detects_wrong_branch_link(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(
            idx.read_text()
            + "\n[code](https://github.com/example/test-book/blob/master/code/query.sql)\n"
        )
        result = check_github_urls(cfg)
        # branch 'master' ≠ canonical 'main'
        assert not result.ok
        assert any("master" in e for e in result.errors)

    def test_fix_rewrites_wrong_branch(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        original = idx.read_text()
        idx.write_text(
            original
            + "\n[code](https://github.com/example/test-book/blob/master/code/query.sql)\n"
        )
        result = check_github_urls(cfg, fix=True)
        assert result.fixed
        new_text = idx.read_text()
        assert "blob/main/" in new_text
        assert "blob/master/" not in new_text

    def test_ignores_links_to_other_repos(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(
            idx.read_text()
            + "\n[other](https://github.com/someone/other-repo/blob/old-branch/file.md)\n"
        )
        result = check_github_urls(cfg)
        assert result.ok


class TestCheckMkdocsNav:
    def test_valid_nav_has_no_errors(self, book_root: Path) -> None:
        cfg = load(book_root)
        result = check_mkdocs_nav(cfg)
        assert result.ok, result.errors

    def test_missing_nav_file_is_error(self, book_root: Path) -> None:
        cfg = load(book_root)
        # Break mkdocs.yml reference
        (book_root / "docs" / "coding" / "intro.md").unlink()
        result = check_mkdocs_nav(cfg)
        assert not result.ok
        assert any("intro.md" in e for e in result.errors)

    def test_http_nav_entries_are_skipped(self, book_root: Path) -> None:
        cfg = load(book_root)
        mkdocs = book_root / "mkdocs.yml"
        mkdocs.write_text(
            mkdocs.read_text()
            + "  - External: https://example.com/page\n"
        )
        result = check_mkdocs_nav(cfg)
        assert result.ok


class TestCheckVersions:
    def test_matching_version_has_no_errors(self, book_root: Path) -> None:
        cfg = load(book_root)
        # docs don't mention any cp-kafka version yet — should be clean
        result = check_versions(cfg)
        assert result.ok

    def test_version_mismatch_is_an_error(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(idx.read_text() + "\ncp-kafka:6.0.0\n")
        result = check_versions(cfg)
        assert not result.ok
        assert any("6.0.0" in e for e in result.errors)

    def test_fix_rewrites_version(self, book_root: Path) -> None:
        cfg = load(book_root)
        idx = book_root / "docs" / "index.md"
        idx.write_text(idx.read_text() + "\ncp-kafka:6.0.0\n")
        result = check_versions(cfg, fix=True)
        assert result.fixed
        assert "7.8.0" in idx.read_text()


class TestPrintVersions:
    def test_returns_canonical_version(self, book_root: Path) -> None:
        cfg = load(book_root)
        rows = print_versions(cfg)
        assert len(rows) == 1
        assert rows[0]["id"] == "cp-kafka"
        assert rows[0]["canonical"] == "7.8.0"

    def test_missing_source_returns_sentinel(self, book_root: Path) -> None:
        cfg = load(book_root)
        (book_root / "deployment" / "docker-compose.yaml").unlink()
        rows = print_versions(cfg)
        assert "missing" in rows[0]["canonical"]


class TestAuditCombined:
    def test_all_three_results_returned(self, book_root: Path) -> None:
        cfg = load(book_root)
        results = audit(cfg)
        assert len(results) == 3
        assert {r.check for r in results} == {"github_urls", "mkdocs_nav", "versions"}

    def test_no_agno_import_in_audit(self) -> None:
        import ast
        import importlib.util

        spec = importlib.util.find_spec("core.audit")
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
                        f"core/audit.py must not import agno, found: {name!r}"
                    )
