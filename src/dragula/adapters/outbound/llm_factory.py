from dragula.adapters.outbound.gemini_client import GeminiClient
from dragula.adapters.outbound.openai_compatible_client import (
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from dragula.application.ports import ChatClientPort, EmbeddingClientPort, LLMProvider
from dragula.config import ProviderSettings, Settings


def build_llm_provider(settings: Settings) -> LLMProvider:
    chat_client = _build_chat_client(settings.chat)
    embedding_client = _build_embedding_client(settings.embedding)
    return LLMProvider(embedding_client=embedding_client, chat_client=chat_client)


def _build_chat_client(chat: ProviderSettings) -> ChatClientPort:
    provider = chat.provider.strip().lower()
    if provider == "gemini":
        return GeminiClient(
            api_key=chat.options.get("api_key"),
            embedding_model=chat.model,
            chat_model=chat.model,
        )
    if provider in {"openai_compatible", "openai-compatible", "openai"}:
        return OpenAICompatibleClient(
            OpenAICompatibleConfig(
                base_url=chat.options.get("base_url", ""),
                api_key=chat.options.get("api_key"),
                embedding_model=chat.model,
                chat_model=chat.model,
                timeout_seconds=float(chat.options.get("timeout_seconds", "60")),
            )
        )
    raise ValueError(
        f"Unsupported [chat].provider '{chat.provider}'. "
        "Use one of: gemini, openai_compatible."
    )


def _build_embedding_client(embedding: ProviderSettings) -> EmbeddingClientPort:
    provider = embedding.provider.strip().lower()
    if provider == "gemini":
        return GeminiClient(
            api_key=embedding.options.get("api_key"),
            embedding_model=embedding.model,
            chat_model=embedding.model,
        )
    if provider in {"openai_compatible", "openai-compatible", "openai"}:
        return OpenAICompatibleClient(
            OpenAICompatibleConfig(
                base_url=embedding.options.get("base_url", ""),
                api_key=embedding.options.get("api_key"),
                embedding_model=embedding.model,
                chat_model=embedding.model,
                timeout_seconds=float(embedding.options.get("timeout_seconds", "60")),
            )
        )
    raise ValueError(
        f"Unsupported [embedding].provider '{embedding.provider}'. "
        "Use one of: gemini, openai_compatible."
    )
