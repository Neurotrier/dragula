from dataclasses import dataclass
from pathlib import Path

from dragula.adapters.outbound.chroma_vector_index import ChromaVectorIndexAdapter
from dragula.adapters.outbound.filesystem_source import LocalProjectFileSource
from dragula.adapters.outbound.llm_factory import build_llm_provider
from dragula.adapters.outbound.sqlite_repository import SQLiteCodeDocumentRepository
from dragula.application.use_cases import (
    DeleteSymbolDescriptionsUseCase,
    DescribeSymbolUseCase,
    GetSymbolDetailsUseCase,
    IndexProjectUseCase,
    ListSymbolsUseCase,
    RetrieveContextUseCase,
)
from dragula.config import Settings, load_settings


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    repository: SQLiteCodeDocumentRepository
    vector_index: ChromaVectorIndexAdapter
    index_project: IndexProjectUseCase
    list_symbols: ListSymbolsUseCase
    get_symbol_details: GetSymbolDetailsUseCase
    describe_symbol: DescribeSymbolUseCase
    delete_symbol_descriptions: DeleteSymbolDescriptionsUseCase


def build_application(
    project_root: Path,
    settings: Settings | None = None,
    repository: SQLiteCodeDocumentRepository | None = None,
    describe_symbol: DescribeSymbolUseCase | None = None,
) -> ApplicationContainer:
    resolved_settings = settings or load_settings(project_root)
    resolved_repository = repository or SQLiteCodeDocumentRepository(
        resolved_settings.sqlite_path
    )
    llm_provider = build_llm_provider(resolved_settings)
    vector_index = ChromaVectorIndexAdapter(resolved_settings.chroma_dir)
    file_source = LocalProjectFileSource(
        resolved_settings.project_root,
        excluded_roots=[resolved_settings.dragula_dir],
    )
    retriever = RetrieveContextUseCase(vector_index, llm_provider.embedding_client)

    return ApplicationContainer(
        settings=resolved_settings,
        repository=resolved_repository,
        vector_index=vector_index,
        index_project=IndexProjectUseCase(
            file_source=file_source,
            symbol_writer=resolved_repository,
            vector_index=vector_index,
            embedding_client=llm_provider.embedding_client,
        ),
        list_symbols=ListSymbolsUseCase(resolved_repository),
        get_symbol_details=GetSymbolDetailsUseCase(resolved_repository),
        describe_symbol=describe_symbol
        or DescribeSymbolUseCase(
            symbol_reader=resolved_repository,
            description_cache=resolved_repository,
            retriever=retriever,
            chat_client=llm_provider.chat_client,
            top_k=resolved_settings.top_k,
        ),
        delete_symbol_descriptions=DeleteSymbolDescriptionsUseCase(
            symbol_reader=resolved_repository,
            description_cache=resolved_repository,
        ),
    )
