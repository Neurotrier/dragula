from dragula.adapters.outbound.llm.custom_provider_loader import (
    load_custom_provider_instance,
    validate_custom_chat_client,
    validate_custom_embedding_client,
)
from dragula.adapters.outbound.llm.gemini_client import GeminiClient
from dragula.adapters.outbound.llm.openai_compatible_client import (
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from dragula.application.ports import ChatClientPort, EmbeddingClientPort, LLMProvider
from dragula.config import ALLOWED_PROVIDERS, ProviderSettings, Settings


def build_llm_provider(settings: Settings) -> LLMProvider:
    chat_client = _build_chat_client(settings.chat)
    embedding_client = _build_embedding_client(settings.embedding)
    return LLMProvider(embedding_client=embedding_client, chat_client=chat_client)


def _normalize_and_validate_provider(section: str, provider_raw: str) -> str:
    provider = provider_raw.strip().lower()
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(
            f"Unsupported [{section}].provider '{provider_raw}'. "
            f"Use one of: {', '.join(ALLOWED_PROVIDERS)}."
        )
    return provider


def _build_chat_client(chat: ProviderSettings) -> ChatClientPort:
    provider = _normalize_and_validate_provider("chat", chat.provider)
    match provider:
        case "gemini":
            return GeminiClient(
                api_key=chat.options.get("api_key"),
                embedding_model=chat.model,
                chat_model=chat.model,
            )
        case "openai":
            return OpenAICompatibleClient(
                OpenAICompatibleConfig(
                    base_url=chat.options.get("base_url", ""),
                    api_key=chat.options.get("api_key"),
                    embedding_model=chat.model,
                    chat_model=chat.model,
                    timeout_seconds=float(chat.options.get("timeout_seconds", "60")),
                )
            )
        case "custom":
            client = load_custom_provider_instance("chat", chat)
            return validate_custom_chat_client("chat", client)


def _build_embedding_client(embedding: ProviderSettings) -> EmbeddingClientPort:
    provider = _normalize_and_validate_provider("embedding", embedding.provider)
    match provider:
        case "gemini":
            return GeminiClient(
                api_key=embedding.options.get("api_key"),
                embedding_model=embedding.model,
                chat_model=embedding.model,
            )
        case "openai":
            return OpenAICompatibleClient(
                OpenAICompatibleConfig(
                    base_url=embedding.options.get("base_url", ""),
                    api_key=embedding.options.get("api_key"),
                    embedding_model=embedding.model,
                    chat_model=embedding.model,
                    timeout_seconds=float(embedding.options.get("timeout_seconds", "60")),
                )
            )
        case "custom":
            client = load_custom_provider_instance("embedding", embedding)
            return validate_custom_embedding_client("embedding", client)
