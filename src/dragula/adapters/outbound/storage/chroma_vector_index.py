from pathlib import Path

import chromadb

from dragula.domain import Chunk


class ChromaVectorIndexAdapter:
    def __init__(self, db_dir: Path, collection_name: str = "code_chunks") -> None:
        db_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(db_dir))
        self.collection = self.client.get_or_create_collection(collection_name)

    def replace_file_chunks(
        self, file_path: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        existing = self.collection.get(where={"file_path": file_path})
        ids = existing.get("ids", []) if existing else []
        if ids:
            self.collection.delete(ids=ids)

        if not chunks:
            return

        self.collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "symbol_id": chunk.symbol_id,
                    "file_path": chunk.file_path,
                    "kind": chunk.kind,
                    "chunk_index": chunk.chunk_index,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
                for chunk in chunks
            ],
        )

    def search_documents(self, query_embedding: list[float], top_k: int) -> list[str]:
        result = self.collection.query(
            query_embeddings=[query_embedding], n_results=top_k
        )
        docs = result.get("documents", [])
        if not docs:
            return []
        return [str(item) for item in docs[0]]
