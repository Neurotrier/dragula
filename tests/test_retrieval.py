from dragula.application.use_cases import RetrieveContextUseCase


class FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3]]


class FakeChroma:
    def search_documents(self, query_embedding: list[float], top_k: int) -> list[str]:
        _ = (query_embedding, top_k)
        return ["class A: pass", "def f(): pass"]


def test_retriever_returns_documents() -> None:
    retriever = RetrieveContextUseCase(FakeChroma(), FakeLLM())
    docs = retriever.retrieve("A", top_k=2)
    assert docs == ["class A: pass", "def f(): pass"]
