"""
tests/test_news.py — tests for core/news.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.book import load
from core.news import (
    _replace_region,
    apply_draft,
    collect_commits,
    get_sync_commit,
    group_by_section,
    write_draft,
)
from tests.fixtures import book_root  # noqa: F401


# ---------------------------------------------------------------------------
# _replace_region
# ---------------------------------------------------------------------------

class TestReplaceRegion:
    def test_basic_replacement(self) -> None:
        text = "before\n<!-- book:foo:start -->\nold\n<!-- book:foo:end -->\nafter\n"
        result = _replace_region(text, "foo", "new content")
        assert "new content" in result
        assert "old" not in result
        assert "before" in result
        assert "after" in result

    def test_preserves_indentation(self) -> None:
        text = "    <!-- book:foo:start -->\n    old\n    <!-- book:foo:end -->\n"
        result = _replace_region(text, "foo", "new")
        assert "    new" in result

    def test_missing_start_raises(self) -> None:
        text = "no markers here\n<!-- book:foo:end -->\n"
        with pytest.raises(ValueError, match="start marker"):
            _replace_region(text, "foo", "x")

    def test_missing_end_raises(self) -> None:
        text = "<!-- book:foo:start -->\nno end\n"
        with pytest.raises(ValueError, match="end marker"):
            _replace_region(text, "foo", "x")


# ---------------------------------------------------------------------------
# collect_commits
# ---------------------------------------------------------------------------

class TestCollectCommits:
    def test_collects_commits_after_initial(self, book_root: Path) -> None:
        cfg = load(book_root)
        # Get the initial commit SHA.
        import subprocess
        initial = subprocess.run(
            ["git", "log", "--format=%H", "--reverse"],
            cwd=book_root, capture_output=True, text=True, check=True
        ).stdout.splitlines()[0]

        commits = collect_commits(cfg, since_commit=initial)
        assert len(commits) == 2  # feat and docs commits

    def test_noise_commits_filtered(self, book_root: Path) -> None:
        """Commits matching ignore_commits patterns must be excluded."""
        import os
        import subprocess
        (book_root / "docs" / "noise.md").write_text("x\n")
        env = {**os.environ, "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_EMAIL": "t@t.com",
               "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test"}
        subprocess.run(["git", "add", "."], cwd=book_root, check=True, capture_output=True, env=env)
        subprocess.run(
            ["git", "commit", "-m", "Merge branch 'main'"],
            cwd=book_root, check=True, capture_output=True, env=env,
        )
        cfg = load(book_root)
        commits = collect_commits(cfg)
        subjects = [c.subject for c in commits]
        assert not any(s.startswith("Merge") for s in subjects), f"Unexpected Merge commit: {subjects}"

    def test_no_since_collects_all(self, book_root: Path) -> None:
        cfg = load(book_root)
        commits = collect_commits(cfg)
        assert len(commits) >= 2  # at least the feat and docs commits (noise filtered)

    def test_duplicate_subjects_collapsed(self, book_root: Path) -> None:
        import os
        import subprocess
        env = {**os.environ, "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_EMAIL": "t@t.com",
               "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test"}
        for name in ("dup1.md", "dup2.md"):
            (book_root / "docs" / name).write_text("x\n")
            subprocess.run(["git", "add", "."], cwd=book_root, check=True, capture_output=True, env=env)
            subprocess.run(
                ["git", "commit", "-m", "update dup"],
                cwd=book_root, check=True, capture_output=True, env=env,
            )
        commits = collect_commits(load(book_root))
        dups = [c for c in commits if c.subject == "update dup"]
        assert len(dups) == 1
        assert {"docs/dup1.md", "docs/dup2.md"} <= set(dups[0].files)




# ---------------------------------------------------------------------------
# group_by_section
# ---------------------------------------------------------------------------

class TestGroupBySection:
    def test_groups_by_matching_prefix(self, book_root: Path) -> None:
        from datetime import date
        from core.news import Commit

        cfg = load(book_root)
        c1 = Commit("a" * 40, "aaaaaaa", date.today(), "feat: sql", files=["code/new.sql"])
        c2 = Commit("b" * 40, "bbbbbbb", date.today(), "docs: idx", files=["docs/index.md"])
        groups = group_by_section(cfg, [c1, c2])
        assert "Coding" in groups
        assert "Documentation" in groups

    def test_unmatched_goes_to_other(self, book_root: Path) -> None:
        from datetime import date
        from core.news import Commit

        cfg = load(book_root)
        c = Commit("c" * 40, "ccccccc", date.today(), "chore", files=["unknown/file.txt"])
        groups = group_by_section(cfg, [c])
        assert "Other" in groups


# ---------------------------------------------------------------------------
# write_draft
# ---------------------------------------------------------------------------

class TestWriteDraft:
    def test_creates_draft_file(self, book_root: Path) -> None:
        from datetime import date
        from core.news import Commit

        cfg = load(book_root)
        c = Commit("d" * 40, "ddddddd", date.today(), "feat: new", files=["code/x.sql"])
        groups = group_by_section(cfg, [c])
        path = write_draft(cfg, groups, since_commit="abc1234", newest_commit="d" * 40)
        assert path.exists()
        content = path.read_text()
        assert "feat: new" in content
        assert "since: abc1234" in content

    def test_empty_groups_still_writes_file(self, book_root: Path) -> None:
        cfg = load(book_root)
        path = write_draft(cfg, {}, since_commit="abc1234")
        assert path.exists()
        assert "No new commits" in path.read_text()


# ---------------------------------------------------------------------------
# get_sync_commit
# ---------------------------------------------------------------------------

class TestGetSyncCommit:
    def test_reads_commit_from_marker(self, book_root: Path) -> None:
        cfg = load(book_root)
        commit = get_sync_commit(cfg)
        assert commit == "abc1234"

    def test_returns_none_when_marker_missing(self, tmp_path: Path) -> None:
        from tests.fixtures import BOOK_YML, MKDOCS_YML, INDEX_MD
        root = tmp_path / "nomarker"
        root.mkdir()
        (root / "book.yml").write_text(BOOK_YML)
        (root / "mkdocs.yml").write_text(MKDOCS_YML)
        (root / "docs").mkdir()
        (root / "docs" / "index.md").write_text(INDEX_MD)
        cfg = load(root)
        # No news file, and index has no sync marker
        assert get_sync_commit(cfg) is None


# ---------------------------------------------------------------------------
# apply_draft
# ---------------------------------------------------------------------------

class TestApplyDraft:
    def test_apply_updates_news_site_region(self, book_root: Path) -> None:
        from datetime import date
        from core.news import Commit

        cfg = load(book_root)
        c = Commit("e" * 40, "eeeeeee", date.today(), "feat: apply test", files=["code/x.sql"])
        groups = group_by_section(cfg, [c])
        draft_path = write_draft(cfg, groups, since_commit="abc1234", newest_commit="e" * 40)

        apply_draft(cfg, draft_path, region="news-site")

        news_text = cfg.sync_file().read_text()
        assert "feat: apply test" in news_text

    def test_apply_updates_sync_marker(self, book_root: Path) -> None:
        from datetime import date
        from core.news import Commit

        cfg = load(book_root)
        c = Commit("f" * 40, "fffffff", date.today(), "feat: marker test", files=["docs/x.md"])
        groups = group_by_section(cfg, [c])
        draft_path = write_draft(cfg, groups, since_commit="abc1234", newest_commit="f" * 40)

        apply_draft(cfg, draft_path, region="news-site")

        news_text = cfg.sync_file().read_text()
        assert "fffffff" in news_text  # short hash updated in sync marker

    def test_apply_missing_draft_raises(self, book_root: Path) -> None:
        cfg = load(book_root)
        with pytest.raises(FileNotFoundError):
            apply_draft(cfg, Path("/nonexistent/draft.md"))

    def test_no_agno_import_in_news(self) -> None:
        import ast
        import importlib.util

        spec = importlib.util.find_spec("core.news")
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
                        f"core/news.py must not import agno, found: {name!r}"
                    )
