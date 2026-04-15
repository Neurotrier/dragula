import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from dragula.adapters.outbound.storage.sqlite import SQLiteCodeDocumentRepository
from dragula.application.use_cases import (
    DeleteSymbolDescriptionsUseCase,
    DescribeSymbolUseCase,
    GetSymbolDetailsUseCase,
    ListSymbolsUseCase,
)
from dragula.composition import (
    build_describe_symbol_use_case,
    resolve_settings_and_repository,
)
from dragula.config import Settings

logger = logging.getLogger(__name__)


def create_app(
    project_root: Path,
    settings: Settings | None = None,
    repository: SQLiteCodeDocumentRepository | None = None,
    describe_symbol: DescribeSymbolUseCase | None = None,
) -> FastAPI:
    resolved_settings, resolved_repository = resolve_settings_and_repository(
        project_root,
        settings=settings,
        repository=repository,
    )
    list_symbols_use_case = ListSymbolsUseCase(resolved_repository)
    get_symbol_details = GetSymbolDetailsUseCase(resolved_repository)
    delete_symbol_descriptions_use_case = DeleteSymbolDescriptionsUseCase(
        symbol_reader=resolved_repository,
        description_cache=resolved_repository,
    )
    resolved_describe_symbol = describe_symbol
    if resolved_describe_symbol is None:
        resolved_describe_symbol = build_describe_symbol_use_case(
            resolved_settings,
            resolved_repository,
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
            res = resolved_describe_symbol.generate_for_symbol(symbol_id)
            return _serialize(res)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception:
            logger.exception("Failed to describe symbol %s", symbol_id)
            raise

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
