import hashlib
from pathlib import Path

from dragula.adapters.outbound.sqlite_repository import SQLiteCodeDocumentRepository
from dragula.application.use_cases import DescribeSymbolUseCase
from dragula.domain import GeneratedDescription, ParsedSymbol


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_symbol(store: SQLiteCodeDocumentRepository) -> None:
    store.replace_symbols_for_file(
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


class FakeRetriever:
    def __init__(self, context: list[str]) -> None:
        self.context = context

    def retrieve(self, query: str, top_k: int) -> list[str]:
        _ = (query, top_k)
        return list(self.context)


class FakeLLMClient:
    def __init__(self, response: GeneratedDescription) -> None:
        self.chat_model = "gemini-test"
        self.response = response
        self.calls: list[tuple[str, list[str]]] = []

    def generate_description(
        self, symbol_name: str, context_chunks: list[str]
    ) -> GeneratedDescription:
        self.calls.append((symbol_name, list(context_chunks)))
        return self.response


def test_generator_uses_cached_description_from_db(tmp_path: Path) -> None:
    store = SQLiteCodeDocumentRepository(tmp_path / "symbols.sqlite3")
    _seed_symbol(store)
    context = ["class Service:", "run_service() uses Service"]
    store.save_description(
        symbol_id="class:123",
        model="gemini-test",
        prompt_hash=_hash_text("sample.Service"),
        context_hash=_hash_text("\n".join(context)),
        purpose="Cached purpose",
        responsibilities=["Handle service work"],
        references=["sample.run_service"],
        raw_response='{"purpose":"Cached purpose"}',
    )
    llm = FakeLLMClient(
        GeneratedDescription(
            purpose="Fresh purpose",
            responsibilities=["Fresh responsibility"],
            references=["fresh.reference"],
            raw_response='{"purpose":"Fresh purpose"}',
        )
    )
    generator = DescribeSymbolUseCase(
        symbol_reader=store,
        description_cache=store,
        retriever=FakeRetriever(context),
        chat_client=llm,
        top_k=3,
    )

    result = generator.generate_for_symbol("class:123")

    assert result.purpose == "Cached purpose"
    assert result.responsibilities == ["Handle service work"]
    assert result.references == ["sample.run_service"]
    assert llm.calls == []


def test_generator_saves_description_on_cache_miss(tmp_path: Path) -> None:
    store = SQLiteCodeDocumentRepository(tmp_path / "symbols.sqlite3")
    _seed_symbol(store)
    context = ["class Service:", "run_service() uses Service"]
    llm = FakeLLMClient(
        GeneratedDescription(
            purpose="Fresh purpose",
            responsibilities=["Handle service work"],
            references=["sample.run_service"],
            raw_response='{"purpose":"Fresh purpose"}',
        )
    )
    generator = DescribeSymbolUseCase(
        symbol_reader=store,
        description_cache=store,
        retriever=FakeRetriever(context),
        chat_client=llm,
        top_k=3,
    )

    result = generator.generate_for_symbol("class:123")
    cached = store.get_cached_description(
        symbol_id="class:123",
        model="gemini-test",
        prompt_hash=_hash_text("sample.Service"),
        context_hash=_hash_text("\n".join(context)),
    )

    assert result.purpose == "Fresh purpose"
    assert result.references == ["sample.run_service"]
    assert llm.calls == [("sample.Service", context)]
    assert cached is not None
    assert cached.purpose == "Fresh purpose"
    assert cached.responsibilities == ["Handle service work"]
    assert cached.references == ["sample.run_service"]


def test_generator_invalidates_cache_when_context_changes(tmp_path: Path) -> None:
    store = SQLiteCodeDocumentRepository(tmp_path / "symbols.sqlite3")
    _seed_symbol(store)
    old_context = ["class Service:", "old usage"]
    new_context = ["class Service:", "new usage"]
    store.save_description(
        symbol_id="class:123",
        model="gemini-test",
        prompt_hash=_hash_text("sample.Service"),
        context_hash=_hash_text("\n".join(old_context)),
        purpose="Old purpose",
        responsibilities=["Old responsibility"],
        references=["old.reference"],
        raw_response='{"purpose":"Old purpose"}',
    )
    llm = FakeLLMClient(
        GeneratedDescription(
            purpose="New purpose",
            responsibilities=["New responsibility"],
            references=["new.reference"],
            raw_response='{"purpose":"New purpose"}',
        )
    )
    generator = DescribeSymbolUseCase(
        symbol_reader=store,
        description_cache=store,
        retriever=FakeRetriever(new_context),
        chat_client=llm,
        top_k=3,
    )

    result = generator.generate_for_symbol("class:123")
    new_cached = store.get_cached_description(
        symbol_id="class:123",
        model="gemini-test",
        prompt_hash=_hash_text("sample.Service"),
        context_hash=_hash_text("\n".join(new_context)),
    )
    old_cached = store.get_cached_description(
        symbol_id="class:123",
        model="gemini-test",
        prompt_hash=_hash_text("sample.Service"),
        context_hash=_hash_text("\n".join(old_context)),
    )

    assert result.purpose == "New purpose"
    assert llm.calls == [("sample.Service", new_context)]
    assert new_cached is not None
    assert new_cached.references == ["new.reference"]
    assert old_cached is not None
    assert old_cached.references == ["old.reference"]
