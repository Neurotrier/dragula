from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from dragula.adapters.inbound.web.app import create_app
from dragula.adapters.outbound.storage.sqlite import SQLiteCodeDocumentRepository
from dragula.config import load_settings
from dragula.domain import ParsedSymbol
from tests.support import create_project, write_default_test_config


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate_for_symbol(self, symbol_id: str) -> dict[str, str | list[str]]:
        self.calls += 1
        return {
            "symbol_id": symbol_id,
            "symbol_name": "sample.mod.Service",
            "purpose": "Testing",
            "responsibilities": ["Do test work"],
            "references": ["sample.mod.run_service"],
        }

def test_web_api_lists_symbols(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_default_test_config(project)
    settings = load_settings(project)
    sqlite_store = SQLiteCodeDocumentRepository(settings.sqlite_path)
    sqlite_store.replace_symbols_for_file(
        "sample.py",
        [
            ParsedSymbol(
                symbol_id="class:123",
                parent_symbol_id=None,
                file_path="sample.py",
                name="Service",
                qualified_name="sample.Service",
                kind="class",
                signature=None,
                docstring="doc",
                start_line=1,
                end_line=10,
                source="class Service: ...",
            )
        ],
    )

    app = create_app(
        project,
        settings=settings,
        repository=sqlite_store,
        describe_symbol=FakeGenerator(),
    )
    client = TestClient(app)
    response = client.get("/api/symbols")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["qualified_name"] == "sample.Service"

    describe_response = client.post("/api/symbols/class:123/describe")
    assert describe_response.status_code == 200
    assert describe_response.json()["purpose"] == "Testing"
    assert describe_response.json()["references"] == ["sample.mod.run_service"]


def test_web_api_lists_symbols_concurrently(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_default_test_config(project)
    settings = load_settings(project)
    sqlite_store = SQLiteCodeDocumentRepository(settings.sqlite_path)
    sqlite_store.replace_symbols_for_file(
        "sample.py",
        [
            ParsedSymbol(
                symbol_id="class:123",
                parent_symbol_id=None,
                file_path="sample.py",
                name="Service",
                qualified_name="sample.Service",
                kind="class",
                signature=None,
                docstring="doc",
                start_line=1,
                end_line=10,
                source="class Service: ...",
            )
        ],
    )
    app = create_app(
        project,
        settings=settings,
        repository=sqlite_store,
        describe_symbol=FakeGenerator(),
    )

    def _fetch_once() -> int:
        with TestClient(app) as client:
            response = client.get("/api/symbols")
            assert response.status_code == 200
            payload = response.json()
            assert payload and payload[0]["qualified_name"] == "sample.Service"
            return response.status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: _fetch_once(), range(20)))
    assert all(status == 200 for status in results)


def test_web_api_deletes_ai_descriptions_by_symbol_id(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_default_test_config(project)
    settings = load_settings(project)
    sqlite_store = SQLiteCodeDocumentRepository(settings.sqlite_path)
    sqlite_store.replace_symbols_for_file(
        "sample.py",
        [
            ParsedSymbol(
                symbol_id="class:123",
                parent_symbol_id=None,
                file_path="sample.py",
                name="Service",
                qualified_name="sample.Service",
                kind="class",
                signature=None,
                docstring="doc",
                start_line=1,
                end_line=10,
                source="class Service: ...",
            )
        ],
    )
    sqlite_store.save_description(
        symbol_id="class:123",
        model="test-model",
        prompt_hash="prompt-hash",
        context_hash="context-hash",
        purpose="old-purpose",
        responsibilities=["one"],
        references=["two"],
        raw_response="raw",
    )

    generator = FakeGenerator()
    app = create_app(
        project, settings=settings, repository=sqlite_store, describe_symbol=generator
    )
    client = TestClient(app)

    delete_response = client.delete("/api/symbols/class:123/descriptions")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"symbol_id": "class:123", "deleted": 1}

    describe_response = client.post("/api/symbols/class:123/describe")
    assert describe_response.status_code == 200
    assert generator.calls == 1


def test_web_api_delete_descriptions_returns_404_for_missing_symbol(
    tmp_path: Path,
) -> None:
    project = create_project(tmp_path)
    write_default_test_config(project)
    settings = load_settings(project)
    sqlite_store = SQLiteCodeDocumentRepository(settings.sqlite_path)
    app = create_app(
        project,
        settings=settings,
        repository=sqlite_store,
        describe_symbol=FakeGenerator(),
    )
    client = TestClient(app)

    delete_response = client.delete("/api/symbols/class:missing/descriptions")
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Symbol not found: class:missing"
