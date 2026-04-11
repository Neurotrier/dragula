import sqlite3
from pathlib import Path

from dragula.adapters.outbound.filesystem import LocalProjectFileSource
from dragula.adapters.outbound.storage.sqlite import SQLiteCodeDocumentRepository
from dragula.application.use_cases import IndexProjectUseCase
from dragula.domain import Chunk


class FakeLLMClient:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 10)] * 4 for t in texts]


class FakeChromaStore:
    def __init__(self) -> None:
        self.saved = {}

    def replace_file_chunks(
        self, file_path: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        self.saved[file_path] = (chunks, embeddings)


def test_indexing_pipeline(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "sample.py").write_text(
        "class Service:\n" "    def run(self, x):\n" "        return x\n",
        encoding="utf-8",
    )
    db = SQLiteCodeDocumentRepository(tmp_path / "symbols.sqlite3")
    pipeline = IndexProjectUseCase(
        LocalProjectFileSource(project), db, FakeChromaStore(), FakeLLMClient()
    )
    stats = pipeline.run()
    assert stats.files_scanned == 1
    assert stats.symbols_found >= 2
    assert stats.chunks_saved >= 2
    symbols = db.list_symbols()
    assert any(symbol.qualified_name.endswith("Service") for symbol in symbols)


def test_sqlite_store_migrates_old_ai_descriptions_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "symbols.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE ai_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol_id TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            context_hash TEXT NOT NULL,
            purpose TEXT NOT NULL,
            responsibilities_json TEXT NOT NULL,
            key_methods_json TEXT NOT NULL,
            dependencies_json TEXT NOT NULL,
            usage_notes TEXT NOT NULL,
            raw_response TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
    conn.commit()
    conn.close()

    store = SQLiteCodeDocumentRepository(db_path)
    store.save_description(
        symbol_id="class:123",
        model="gemini-test",
        prompt_hash="prompt",
        context_hash="context",
        purpose="Service object",
        responsibilities=["Process requests"],
        references=["sample.run_service"],
        raw_response='{"purpose":"Service object"}',
    )

    conn = sqlite3.connect(db_path)
    columns = [
        row[1] for row in conn.execute("PRAGMA table_info(ai_descriptions)").fetchall()
    ]
    row = conn.execute(
        "SELECT purpose, responsibilities_json, references_json FROM ai_descriptions WHERE symbol_id = ?",
        ("class:123",),
    ).fetchone()
    conn.close()

    assert "references_json" in columns
    assert "key_methods_json" not in columns
    assert row is not None
    assert row[0] == "Service object"
    assert row[1] == '["Process requests"]'
    assert row[2] == '["sample.run_service"]'
