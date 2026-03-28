import time
from dataclasses import asdict, is_dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from dragula.adapters.outbound.sqlite_repository import SQLiteCodeDocumentRepository
from dragula.adapters.outbound.chroma_vector_index import ChromaVectorIndexAdapter
from dragula.adapters.outbound.llm_factory import build_llm_provider
from dragula.application.use_cases import (
    DeleteSymbolDescriptionsUseCase,
    DescribeSymbolUseCase,
    GetSymbolDetailsUseCase,
    ListSymbolsUseCase,
    RetrieveContextUseCase,
)
from dragula.config import Settings


def create_app(
    project_root: Path,
    settings: Settings | None = None,
    repository: SQLiteCodeDocumentRepository | None = None,
    describe_symbol: DescribeSymbolUseCase | None = None,
) -> FastAPI:
    resolved_settings = settings
    if resolved_settings is None:
        from dragula.config import load_settings

        resolved_settings = load_settings(project_root)

    resolved_repository = repository or SQLiteCodeDocumentRepository(
        resolved_settings.sqlite_path
    )
    list_symbols_use_case = ListSymbolsUseCase(resolved_repository)
    get_symbol_details = GetSymbolDetailsUseCase(resolved_repository)
    delete_symbol_descriptions_use_case = DeleteSymbolDescriptionsUseCase(
        symbol_reader=resolved_repository,
        description_cache=resolved_repository,
    )
    resolved_describe_symbol = describe_symbol
    if resolved_describe_symbol is None:
        llm_provider = build_llm_provider(resolved_settings)
        vector_index = ChromaVectorIndexAdapter(resolved_settings.chroma_dir)
        retriever = RetrieveContextUseCase(vector_index, llm_provider.embedding_client)
        resolved_describe_symbol = DescribeSymbolUseCase(
            symbol_reader=resolved_repository,
            description_cache=resolved_repository,
            retriever=retriever,
            chat_client=llm_provider.chat_client,
            top_k=resolved_settings.top_k,
        )

    app = FastAPI(title="AI Code Docs")
    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    templates = Jinja2Templates(directory=str(template_dir))
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", {"request": request})

    @app.get("/api/symbols")
    def list_symbols() -> list[dict[str, object]]:
        rows = list_symbols_use_case.execute()
        return [asdict(row) for row in rows]

    @app.get("/api/symbols/{symbol_id}")
    def get_symbol(symbol_id: str) -> dict[str, object]:
        try:
            details = get_symbol_details.execute(symbol_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "symbol": asdict(details.symbol),
            "chunks": [asdict(chunk) for chunk in details.chunks],
        }

    @app.post("/api/symbols/{symbol_id}/describe")
    def describe_symbol_route(symbol_id: str) -> dict[str, object]:
        try:
            start = time.time()
            res = resolved_describe_symbol.generate_for_symbol(symbol_id)
            end = time.time()
            print(f"describe {symbol_id}: {end-start:.9f}")
            return _serialize(res)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/symbols/{symbol_id}/descriptions")
    def delete_symbol_descriptions(symbol_id: str) -> dict[str, object]:
        try:
            deleted = delete_symbol_descriptions_use_case.execute(symbol_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"symbol_id": symbol_id, "deleted": deleted}

    return app


def _serialize(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Unsupported response value: {type(value).__name__}")
