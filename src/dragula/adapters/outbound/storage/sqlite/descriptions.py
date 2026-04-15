import json

from dragula.adapters.outbound.storage.sqlite.base import SQLiteRepositoryBase
from dragula.domain import CachedDescription


class SQLiteDescriptionStore(SQLiteRepositoryBase):
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
        return self._map_cached_description(row)

    def delete_descriptions_by_symbol(self, symbol_id: str) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM ai_descriptions WHERE symbol_id = ?",
                (symbol_id,),
            )
            return int(cursor.rowcount)
