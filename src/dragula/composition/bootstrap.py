from dataclasses import dataclass
from pathlib import Path

from dragula.adapters.outbound.filesystem import LocalProjectFileSource
from dragula.adapters.outbound.llm import build_llm_provider
from dragula.adapters.outbound.storage import ChromaVectorIndexAdapter
from dragula.adapters.outbound.storage.sqlite import SQLiteCodeDocumentRepository
from dragula.application.use_cases import (
    DeleteSymbolDescriptionsUseCase,
    DescribeSymbolUseCase,
    GetSymbolDetailsUseCase,
    IndexProjectUseCase,
    ListSymbolsUseCase,
    RetrieveContextUseCase,
)
from dragula.config import (
    INIT_CONFIG_INI_TEMPLATE,
    Settings,
    dragula_dir_for,
    load_settings,
)


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


def resolve_settings_and_repository(
    project_root: Path,
    *,
    settings: Settings | None = None,
    repository: SQLiteCodeDocumentRepository | None = None,
) -> tuple[Settings, SQLiteCodeDocumentRepository]:
    resolved_settings = settings or load_settings(project_root)
    resolved_repository = repository or SQLiteCodeDocumentRepository(
        resolved_settings.sqlite_path
    )
    return resolved_settings, resolved_repository


def initialize_project(project_root: Path) -> Settings:
    root = Path(project_root).resolve()
    dragula_dir = dragula_dir_for(root)
    if dragula_dir.exists():
        raise FileExistsError(
            f"{dragula_dir} exists. Remove it to re-run dragula init."
        )

    dragula_dir.mkdir(parents=False)
    config_path = dragula_dir / "config.ini"
    config_path.write_text(INIT_CONFIG_INI_TEMPLATE, encoding="utf-8")

    settings = load_settings(root)
    repository = SQLiteCodeDocumentRepository(settings.sqlite_path)
    repository.close()
    ChromaVectorIndexAdapter(settings.chroma_dir)
    return settings


def build_describe_symbol_use_case(
    settings: Settings,
    repository: SQLiteCodeDocumentRepository,
    *,
    vector_index: ChromaVectorIndexAdapter | None = None,
) -> DescribeSymbolUseCase:
    llm_provider = build_llm_provider(settings)
    resolved_vector_index = vector_index or ChromaVectorIndexAdapter(settings.chroma_dir)
    retriever = RetrieveContextUseCase(
        resolved_vector_index, llm_provider.embedding_client
    )
    return DescribeSymbolUseCase(
        symbol_reader=repository,
        description_cache=repository,
        retriever=retriever,
        chat_client=llm_provider.chat_client,
        top_k=settings.top_k,
    )


def build_application(
    project_root: Path,
    settings: Settings | None = None,
    repository: SQLiteCodeDocumentRepository | None = None,
    describe_symbol: DescribeSymbolUseCase | None = None,
) -> ApplicationContainer:
    resolved_settings, resolved_repository = resolve_settings_and_repository(
        project_root,
        settings=settings,
        repository=repository,
    )
    llm_provider = build_llm_provider(resolved_settings)
    vector_index = ChromaVectorIndexAdapter(resolved_settings.chroma_dir)
    file_source = LocalProjectFileSource(
        resolved_settings.project_root,
        excluded_roots=[resolved_settings.dragula_dir],
    )

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
        or build_describe_symbol_use_case(
            resolved_settings,
            resolved_repository,
            vector_index=vector_index,
        ),
        delete_symbol_descriptions=DeleteSymbolDescriptionsUseCase(
            symbol_reader=resolved_repository,
            description_cache=resolved_repository,
        ),
    )
