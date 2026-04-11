import json

from dragula.adapters.outbound.storage.sqlite.base import SQLiteRepositoryBase


class SQLiteIndexRunStore(SQLiteRepositoryBase):
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
