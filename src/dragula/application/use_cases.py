import hashlib
from dataclasses import dataclass

from dragula.application.code_processing import build_chunks, parse_file_symbols
from dragula.application.ports import (
    ChatClientPort,
    DescriptionCachePort,
    EmbeddingClientPort,
    ProjectFileSourcePort,
    SymbolReadRepositoryPort,
    SymbolWriteRepositoryPort,
    VectorIndexPort,
)
from dragula.domain import Chunk, GeneratedDescription, StoredSymbol


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class IndexStats:
    files_scanned: int
    symbols_found: int
    chunks_saved: int
    errors: list[str]


@dataclass(slots=True)
class SymbolDetails:
    symbol: StoredSymbol
    chunks: list[Chunk]


@dataclass(slots=True)
class DescriptionResult:
    symbol_id: str
    symbol_name: str
    purpose: str
    responsibilities: list[str]
    references: list[str]


class RetrieveContextUseCase:
    def __init__(
        self, vector_index: VectorIndexPort, embedding_client: EmbeddingClientPort
    ) -> None:
        self.vector_index = vector_index
        self.embedding_client = embedding_client

    def retrieve(self, query: str, top_k: int) -> list[str]:
        query_embedding = self.embedding_client.embed_texts([query])[0]
        return self.vector_index.search_documents(
            query_embedding=query_embedding, top_k=top_k
        )


class IndexProjectUseCase:
    def __init__(
        self,
        file_source: ProjectFileSourcePort,
        symbol_writer: SymbolWriteRepositoryPort,
        vector_index: VectorIndexPort,
        embedding_client: EmbeddingClientPort,
    ) -> None:
        self.file_source = file_source
        self.symbol_writer = symbol_writer
        self.vector_index = vector_index
        self.embedding_client = embedding_client

    def run(self) -> IndexStats:
        files = self.file_source.iter_python_files()
        errors: list[str] = []
        symbols_count = 0
        chunks_count = 0
        run_id = self.symbol_writer.start_index_run()

        for project_file in files:
            try:
                self.symbol_writer.upsert_file(
                    project_file.relative_path,
                    project_file.content,
                    project_file.size_bytes,
                    project_file.mtime,
                )
                symbols = parse_file_symbols(
                    project_file.relative_path, project_file.content
                )
                self.symbol_writer.replace_symbols_for_file(
                    project_file.relative_path, symbols
                )
                file_chunks: list[Chunk] = []
                for symbol in symbols:
                    file_chunks.extend(build_chunks(symbol))
                self.symbol_writer.replace_chunks_for_file(
                    project_file.relative_path, file_chunks
                )
                embeddings = (
                    self.embedding_client.embed_texts(
                        [chunk.content for chunk in file_chunks]
                    )
                    if file_chunks
                    else []
                )
                self.vector_index.replace_file_chunks(
                    project_file.relative_path, file_chunks, embeddings
                )
                symbols_count += len(symbols)
                chunks_count += len(file_chunks)
            except Exception as exc:  # pragma: no cover
                message = (
                    f"{project_file.relative_path}: {exc.__class__.__name__}: {exc}"
                )
                if "429" in str(exc) or "insufficient_quota" in str(exc):
                    message += " | Check provider quota/billing."
                if "404" in str(exc) or "model" in str(exc).lower():
                    message += " | Check [embedding].model in .dragula/config.ini."
                if "401" in str(exc) or "unauthorized" in str(exc).lower():
                    message += " | Check provider auth settings in [embedding]."
                errors.append(message)

        self.symbol_writer.finish_index_run(
            run_id=run_id,
            files_scanned=len(files),
            symbols_found=symbols_count,
            chunks_saved=chunks_count,
            errors=errors,
        )
        return IndexStats(
            files_scanned=len(files),
            symbols_found=symbols_count,
            chunks_saved=chunks_count,
            errors=errors,
        )


class DescribeSymbolUseCase:
    def __init__(
        self,
        symbol_reader: SymbolReadRepositoryPort,
        description_cache: DescriptionCachePort,
        retriever: RetrieveContextUseCase,
        chat_client: ChatClientPort,
        top_k: int,
    ) -> None:
        self.symbol_reader = symbol_reader
        self.description_cache = description_cache
        self.retriever = retriever
        self.chat_client = chat_client
        self.top_k = top_k

    def generate_for_symbol(self, symbol_id: str) -> DescriptionResult:
        symbol = self.symbol_reader.get_symbol(symbol_id)
        if symbol is None:
            raise ValueError(f"Symbol not found: {symbol_id}")
        symbol_name = symbol.qualified_name
        context = self.retriever.retrieve(symbol_name, top_k=self.top_k)
        prompt_hash = _hash_text(symbol_name)
        context_hash = _hash_text("\n".join(context))
        cached = self.description_cache.get_cached_description(
            symbol_id=symbol_id,
            model=self.chat_client.chat_model,
            prompt_hash=prompt_hash,
            context_hash=context_hash,
        )
        if cached is not None:
            return self._build_result(
                symbol_id=symbol_id,
                symbol_name=symbol_name,
                description=GeneratedDescription(
                    purpose=cached.purpose,
                    responsibilities=cached.responsibilities,
                    references=cached.references,
                    raw_response=cached.raw_response,
                ),
            )

        generated = self.chat_client.generate_description(
            symbol_name=symbol_name, context_chunks=context
        )
        self.description_cache.save_description(
            symbol_id=symbol_id,
            model=self.chat_client.chat_model,
            prompt_hash=prompt_hash,
            context_hash=context_hash,
            purpose=generated.purpose,
            responsibilities=generated.responsibilities,
            references=generated.references,
            raw_response=generated.raw_response,
        )
        return self._build_result(
            symbol_id=symbol_id, symbol_name=symbol_name, description=generated
        )

    def _build_result(
        self,
        symbol_id: str,
        symbol_name: str,
        description: GeneratedDescription,
    ) -> DescriptionResult:
        return DescriptionResult(
            symbol_id=symbol_id,
            symbol_name=symbol_name,
            purpose=description.purpose,
            responsibilities=description.responsibilities,
            references=description.references,
        )


class ListSymbolsUseCase:
    def __init__(self, symbol_reader: SymbolReadRepositoryPort) -> None:
        self.symbol_reader = symbol_reader

    def execute(self) -> list[StoredSymbol]:
        return self.symbol_reader.list_symbols()


class GetSymbolDetailsUseCase:
    def __init__(self, symbol_reader: SymbolReadRepositoryPort) -> None:
        self.symbol_reader = symbol_reader

    def execute(self, symbol_id: str) -> SymbolDetails:
        symbol = self.symbol_reader.get_symbol(symbol_id)
        if symbol is None:
            raise ValueError(f"Symbol not found: {symbol_id}")
        chunks = self.symbol_reader.get_chunks_by_symbol(symbol_id)
        return SymbolDetails(symbol=symbol, chunks=chunks)


class DeleteSymbolDescriptionsUseCase:
    def __init__(
        self,
        symbol_reader: SymbolReadRepositoryPort,
        description_cache: DescriptionCachePort,
    ) -> None:
        self.symbol_reader = symbol_reader
        self.description_cache = description_cache

    def execute(self, symbol_id: str) -> int:
        symbol = self.symbol_reader.get_symbol(symbol_id)
        if symbol is None:
            raise ValueError(f"Symbol not found: {symbol_id}")
        return self.description_cache.delete_descriptions_by_symbol(symbol_id)
