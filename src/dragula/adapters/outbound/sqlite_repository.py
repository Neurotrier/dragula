import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dragula.domain import CachedDescription, Chunk, ParsedSymbol, StoredSymbol


class SQLiteCodeDocumentRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                checksum TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mtime REAL NOT NULL,
                indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS symbols (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                parent_symbol_id TEXT,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                signature TEXT,
                docstring TEXT,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                is_async INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                symbol_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                kind TEXT NOT NULL,
                embedding_ref TEXT
            );

            CREATE TABLE IF NOT EXISTS ai_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_id TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                context_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                responsibilities_json TEXT NOT NULL,
                references_json TEXT NOT NULL,
                raw_response TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS index_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                status TEXT NOT NULL,
                files_scanned INTEGER DEFAULT 0,
                symbols_found INTEGER DEFAULT 0,
                chunks_saved INTEGER DEFAULT 0,
                errors_json TEXT
            );
            """)
            self._ensure_ai_descriptions_schema(conn)

    def _ensure_ai_descriptions_schema(self, conn: sqlite3.Connection) -> None:
        columns = [
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(ai_descriptions)").fetchall()
        ]
        expected_columns = [
            "id",
            "symbol_id",
            "model",
            "prompt_hash",
            "context_hash",
            "purpose",
            "responsibilities_json",
            "references_json",
            "raw_response",
            "created_at",
        ]
        if columns == expected_columns:
            return

        conn.execute("ALTER TABLE ai_descriptions RENAME TO ai_descriptions_old")
        conn.executescript("""
            CREATE TABLE ai_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_id TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                context_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                responsibilities_json TEXT NOT NULL,
                references_json TEXT NOT NULL,
                raw_response TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
        old_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(ai_descriptions_old)").fetchall()
        }
        if "references_json" in old_columns:
            references_expr = "references_json"
        elif "referencies_json" in old_columns:
            references_expr = "referencies_json"
        else:
            references_expr = "'[]'"
        conn.execute(f"""
            INSERT INTO ai_descriptions (
                id,
                symbol_id,
                model,
                prompt_hash,
                context_hash,
                purpose,
                responsibilities_json,
                references_json,
                raw_response,
                created_at
            )
            SELECT
                id,
                symbol_id,
                model,
                prompt_hash,
                context_hash,
                purpose,
                responsibilities_json,
                {references_expr},
                raw_response,
                created_at
            FROM ai_descriptions_old
            """)
        conn.execute("DROP TABLE ai_descriptions_old")

    def upsert_file(
        self, path: str, content: str, size_bytes: int, mtime: float
    ) -> None:
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connection() as conn:
            conn.execute(
                """
            INSERT INTO files(path, checksum, size_bytes, mtime)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              checksum=excluded.checksum,
              size_bytes=excluded.size_bytes,
              mtime=excluded.mtime,
              indexed_at=CURRENT_TIMESTAMP
            """,
                (path, checksum, size_bytes, mtime),
            )

    def replace_symbols_for_file(
        self, file_path: str, symbols: list[ParsedSymbol]
    ) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            for symbol in symbols:
                conn.execute(
                    """
                INSERT INTO symbols(id, file_path, parent_symbol_id, name, qualified_name, kind, signature, docstring, start_line, end_line, is_async)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        symbol.symbol_id,
                        symbol.file_path,
                        symbol.parent_symbol_id,
                        symbol.name,
                        symbol.qualified_name,
                        symbol.kind,
                        symbol.signature,
                        symbol.docstring,
                        symbol.start_line,
                        symbol.end_line,
                        int(symbol.is_async),
                    ),
                )

    def replace_chunks_for_file(self, file_path: str, chunks: list[Chunk]) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (file_path,))
            for chunk in chunks:
                conn.execute(
                    """
                INSERT INTO chunks(id, symbol_id, file_path, chunk_index, content, start_line, end_line, kind, embedding_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        chunk.chunk_id,
                        chunk.symbol_id,
                        chunk.file_path,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.start_line,
                        chunk.end_line,
                        chunk.kind,
                        chunk.embedding_ref or chunk.chunk_id,
                    ),
                )

    def save_description(
        self,
        symbol_id: str,
        model: str,
        prompt_hash: str,
        context_hash: str,
        purpose: str,
        responsibilities: list[str],
        references: list[str],
        raw_response: str,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_descriptions(symbol_id, model, prompt_hash, context_hash, purpose, responsibilities_json, references_json, raw_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol_id,
                    model,
                    prompt_hash,
                    context_hash,
                    purpose,
                    json.dumps(responsibilities, ensure_ascii=False),
                    json.dumps(references, ensure_ascii=False),
                    raw_response,
                ),
            )

    def get_cached_description(
        self,
        symbol_id: str,
        model: str,
        prompt_hash: str,
        context_hash: str,
    ) -> CachedDescription | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT purpose, responsibilities_json, references_json, raw_response
                FROM ai_descriptions
                WHERE symbol_id = ? AND model = ? AND prompt_hash = ? AND context_hash = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (symbol_id, model, prompt_hash, context_hash),
            ).fetchone()
        if row is None:
            return None
        return CachedDescription(
            purpose=str(row["purpose"]),
            responsibilities=self._parse_json_string_list(
                str(row["responsibilities_json"])
            ),
            references=self._parse_json_string_list(str(row["references_json"])),
            raw_response=str(row["raw_response"]),
        )

    def delete_descriptions_by_symbol(self, symbol_id: str) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM ai_descriptions WHERE symbol_id = ?",
                (symbol_id,),
            )
            return int(cursor.rowcount)

    def start_index_run(self) -> int:
        with self._connection() as conn:
            cursor = conn.execute("INSERT INTO index_runs(status) VALUES ('running')")
            return int(cursor.lastrowid)

    def finish_index_run(
        self,
        run_id: int,
        files_scanned: int,
        symbols_found: int,
        chunks_saved: int,
        errors: list[str],
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE index_runs
                SET finished_at=CURRENT_TIMESTAMP, status=?, files_scanned=?, symbols_found=?, chunks_saved=?, errors_json=?
                WHERE id=?
                """,
                (
                    "success" if not errors else "partial",
                    files_scanned,
                    symbols_found,
                    chunks_saved,
                    json.dumps(errors, ensure_ascii=False),
                    run_id,
                ),
            )

    def list_symbols(self) -> list[StoredSymbol]:
        with self._connection() as conn:
            rows = conn.execute("""
            SELECT id, parent_symbol_id, name, qualified_name, kind, file_path, signature, docstring, start_line, end_line, is_async
            FROM symbols
            ORDER BY qualified_name
            """).fetchall()
        return [self._map_symbol(row) for row in rows]

    def get_symbol(self, symbol_id: str) -> StoredSymbol | None:
        with self._connection() as conn:
            row = conn.execute(
                """
            SELECT id, parent_symbol_id, name, qualified_name, kind, file_path, signature, docstring, start_line, end_line, is_async
            FROM symbols
            WHERE id = ?
            """,
                (symbol_id,),
            ).fetchone()
        if row is None:
            return None
        return self._map_symbol(row)

    def get_chunks_by_symbol(self, symbol_id: str) -> list[Chunk]:
        with self._connection() as conn:
            rows = conn.execute(
                """
            SELECT id, symbol_id, file_path, chunk_index, content, start_line, end_line, kind, embedding_ref
            FROM chunks
            WHERE symbol_id = ?
            ORDER BY chunk_index
            """,
                (symbol_id,),
            ).fetchall()
        return [self._map_chunk(row) for row in rows]

    def close(self) -> None:
        return None

    def _parse_json_string_list(self, value: str) -> list[str]:
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        result: list[str] = []
        for item in data:
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    def _map_symbol(self, row: sqlite3.Row) -> StoredSymbol:
        return StoredSymbol(
            id=str(row["id"]),
            parent_symbol_id=(
                str(row["parent_symbol_id"])
                if row["parent_symbol_id"] is not None
                else None
            ),
            name=str(row["name"]),
            qualified_name=str(row["qualified_name"]),
            kind=str(row["kind"]),
            file_path=str(row["file_path"]),
            signature=str(row["signature"]) if row["signature"] is not None else None,
            docstring=str(row["docstring"]) if row["docstring"] is not None else None,
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            is_async=bool(row["is_async"]),
        )

    def _map_chunk(self, row: sqlite3.Row) -> Chunk:
        return Chunk(
            chunk_id=str(row["id"]),
            symbol_id=str(row["symbol_id"]),
            file_path=str(row["file_path"]),
            chunk_index=int(row["chunk_index"]),
            content=str(row["content"]),
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            kind=str(row["kind"]),
            embedding_ref=(
                str(row["embedding_ref"]) if row["embedding_ref"] is not None else None
            ),
        )
