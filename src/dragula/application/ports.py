from dataclasses import dataclass
from typing import Protocol

from dragula.domain import (
    CachedDescription,
    Chunk,
    GeneratedDescription,
    ParsedSymbol,
    ProjectFile,
    StoredSymbol,
)


class SymbolReadRepositoryPort(Protocol):
    def list_symbols(self) -> list[StoredSymbol]: ...

    def get_symbol(self, symbol_id: str) -> StoredSymbol | None: ...

    def get_chunks_by_symbol(self, symbol_id: str) -> list[Chunk]: ...


class SymbolWriteRepositoryPort(Protocol):
    def upsert_file(
        self, path: str, content: str, size_bytes: int, mtime: float
    ) -> None: ...

    def replace_symbols_for_file(
        self, file_path: str, symbols: list[ParsedSymbol]
    ) -> None: ...

    def replace_chunks_for_file(self, file_path: str, chunks: list[Chunk]) -> None: ...

    def start_index_run(self) -> int: ...

    def finish_index_run(
        self,
        run_id: int,
        files_scanned: int,
        symbols_found: int,
        chunks_saved: int,
        errors: list[str],
    ) -> None: ...


class DescriptionCachePort(Protocol):
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
    ) -> None: ...

    def get_cached_description(
        self,
        symbol_id: str,
        model: str,
        prompt_hash: str,
        context_hash: str,
    ) -> CachedDescription | None: ...

    def delete_descriptions_by_symbol(self, symbol_id: str) -> int: ...


class VectorIndexPort(Protocol):
    def replace_file_chunks(
        self, file_path: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None: ...

    def search_documents(
        self, query_embedding: list[float], top_k: int
    ) -> list[str]: ...


class ProjectFileSourcePort(Protocol):
    def iter_python_files(self) -> list[ProjectFile]: ...


class EmbeddingClientPort(Protocol):
    provider_name: str
    embedding_model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class ChatClientPort(Protocol):
    provider_name: str
    chat_model: str

    def generate_description(
        self, symbol_name: str, context_chunks: list[str]
    ) -> GeneratedDescription: ...


@dataclass(slots=True)
class LLMProvider:
    embedding_client: EmbeddingClientPort
    chat_client: ChatClientPort
