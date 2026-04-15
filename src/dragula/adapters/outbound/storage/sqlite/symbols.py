import hashlib

from dragula.adapters.outbound.storage.sqlite.base import SQLiteRepositoryBase
from dragula.domain import Chunk, ParsedSymbol, StoredSymbol


class SQLiteSymbolStore(SQLiteRepositoryBase):
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
