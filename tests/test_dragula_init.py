import sqlite3
from argparse import Namespace
from pathlib import Path

from dragula.adapters.inbound.cli import cmd_init
from tests.support import create_project


def test_dragula_init_creates_layout(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    assert cmd_init(Namespace(path=str(project))) == 0
    dragula = project / ".dragula"
    assert (dragula / "config.ini").is_file()
    assert (dragula / "symbols.sqlite3").is_file()
    assert (dragula / "chroma").is_dir()
    conn = sqlite3.connect(dragula / "symbols.sqlite3")
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert "symbols" in tables
    assert "files" in tables


def test_dragula_init_refuses_when_dragula_exists(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    (project / ".dragula").mkdir()
    assert cmd_init(Namespace(path=str(project))) == 1
