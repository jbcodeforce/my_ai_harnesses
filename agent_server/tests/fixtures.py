"""
tests/fixtures.py — shared pytest fixtures.

Provides `book_root` — a temporary directory pre-populated with:
- book.yml          valid minimal config
- mkdocs.yml        simple nav
- docs/index.md     with an updates marker and a broken GitHub link
- docs/news/index.md  with news-site, news-log and sync markers
- A tiny git history (3 commits across two sections)

All files are plain text; no real git network calls are needed.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest


BOOK_YML = textwrap.dedent("""\
    schema: 1
    name: test-book
    repo:
      url: https://github.com/example/test-book
      branch: main

    paths:
      docs: docs
      mkdocs: mkdocs.yml
      index: docs/index.md
      news: docs/news/index.md
      scratch: .context

    sections:
      - title: Coding
        paths: [code/]
      - title: Documentation
        paths: [docs/]

    ignore_commits:
      - '^Merge '
      - '(?i)^(typo|wip)\\b'

    stats:
      - id: sql_scripts
        label: SQL scripts
        count: files
        include: ["code/**/*.sql"]

    versions:
      - id: cp-kafka
        source:
          file: deployment/docker-compose.yaml
          pattern: 'cp-kafka:(\\d+\\.\\d+\\.\\d+)'
        docs_pattern: 'cp-kafka:(\\d+\\.\\d+\\.\\d+)'
        fix: true
""")

MKDOCS_YML = textwrap.dedent("""\
    site_name: Test Book
    nav:
      - Home: index.md
      - Coding: coding/intro.md
""")

INDEX_MD = textwrap.dedent("""\
    # Test Book

    ??? info "Updates"
        <!-- book:updates:start -->
        - 2024-01 First entry
        <!-- book:updates:end -->
""")

NEWS_MD = textwrap.dedent("""\
    # News

    <!-- book:sync commit=abc1234 date=2024-01 -->

    ## Site updates

    <!-- book:news-site:start -->
    - 2024-01 Initial news
    <!-- book:news-site:end -->

    ## Log

    <!-- book:news-log:start -->
    - 2024-01 sync
    <!-- book:news-log:end -->
""")

DOCKER_COMPOSE = textwrap.dedent("""\
    services:
      kafka:
        image: confluentinc/cp-kafka:7.8.0
""")


@pytest.fixture()
def book_root(tmp_path: Path) -> Path:
    """Temporary book root with a valid layout and a small git history."""
    root = tmp_path / "test-book"
    root.mkdir()

    # Write all files
    (root / "book.yml").write_text(BOOK_YML, encoding="utf-8")
    (root / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "index.md").write_text(INDEX_MD, encoding="utf-8")
    (root / "docs" / "news").mkdir()
    (root / "docs" / "news" / "index.md").write_text(NEWS_MD, encoding="utf-8")
    (root / "docs" / "coding").mkdir()
    (root / "docs" / "coding" / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (root / "deployment").mkdir()
    (root / "deployment" / "docker-compose.yaml").write_text(DOCKER_COMPOSE, encoding="utf-8")
    (root / "code").mkdir()
    (root / "code" / "query.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (root / ".context").mkdir()

    # Minimal git history (needed by news tests in sub-task 5)
    _git = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=root, check=True, capture_output=True
    )
    _git("init", "-b", "main")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test")
    _git("add", ".")
    _git("commit", "-m", "Initial commit")
    (root / "code" / "new.sql").write_text("SELECT 2;\n", encoding="utf-8")
    _git("add", "code/new.sql")
    _git("commit", "-m", "feat: add new SQL query")
    (root / "docs" / "index.md").write_text(
        INDEX_MD + "\n<!-- extra line -->\n", encoding="utf-8"
    )
    _git("add", "docs/index.md")
    _git("commit", "-m", "docs: update index")

    return root


@pytest.fixture()
def book_root_no_markers(tmp_path: Path) -> Path:
    """Book root where docs/index.md has NO markers — for init tests."""
    root = tmp_path / "bare-book"
    root.mkdir()
    (root / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "index.md").write_text(
        "# Bare Book\n\n??? info \"Updates\"\n    Some hand-written text.\n",
        encoding="utf-8",
    )
    return root
