from pathlib import Path

import pytest

from dragula.adapters.outbound.llm import build_llm_provider
from dragula.config import load_settings
from tests.support import create_project, write_config


def _write_custom_provider(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_factory_builds_gemini_provider(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = gemini\n"
        "model = gemini-2.5-flash\n"
        "api_key = test-key\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "gemini"
    assert provider.embedding_client.provider_name == "gemini"


def test_factory_builds_openai_provider(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = openai\n"
        "model = gpt-4o-mini\n"
        "base_url = http://localhost:11434/v1\n"
        "api_key = \n"
        "\n"
        "[embedding]\n"
        "provider = openai\n"
        "model = text-embedding-3-small\n"
        "base_url = http://localhost:11434/v1\n"
        "api_key = \n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "openai"
    assert provider.embedding_client.provider_name == "openai"


def test_factory_rejects_unknown_provider(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = unknown_provider\n"
        "model = x\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = y\n"
        "api_key = z\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match="Unsupported \\[chat\\]\\.provider"):
        build_llm_provider(settings)


def test_factory_supports_mixed_providers(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = gemini\n"
        "model = gemini-2.5-flash\n"
        "api_key = test-key\n"
        "\n"
        "[embedding]\n"
        "provider = openai\n"
        "model = text-embedding-3-small\n"
        "base_url = http://localhost:11434/v1\n"
        "api_key = \n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "gemini"
    assert provider.embedding_client.provider_name == "openai"


def test_factory_builds_custom_chat_provider(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    custom_module = tmp_path / "custom_chat_provider.py"
    _write_custom_provider(
        custom_module,
        "from dragula.config import ProviderSettings\n"
        "from dragula.domain import GeneratedDescription\n"
        "\n"
        "\n"
        "class CustomChatProvider:\n"
        "    def __init__(self, settings: ProviderSettings) -> None:\n"
        "        self.received_settings = settings\n"
        "        self.provider_name = 'custom-chat'\n"
        "        self.chat_model = settings.model\n"
        "\n"
        "    def generate_description(self, symbol_name: str, context_chunks: list[str]) -> GeneratedDescription:\n"
        "        return GeneratedDescription(\n"
        "            purpose=f'purpose for {symbol_name}',\n"
        "            responsibilities=context_chunks,\n"
        "            references=['custom'],\n"
        "            raw_response='ok',\n"
        "        )\n",
    )
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = custom\n"
        "model = custom-chat-model\n"
        f"class_path = {custom_module}\n"
        "class_name = CustomChatProvider\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "custom-chat"
    assert provider.chat_client.chat_model == "custom-chat-model"
    assert provider.chat_client.received_settings is settings.chat
    assert provider.embedding_client.provider_name == "gemini"


def test_factory_builds_custom_embedding_provider(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    custom_module = tmp_path / "custom_embedding_provider.py"
    _write_custom_provider(
        custom_module,
        "from dragula.config import ProviderSettings\n"
        "\n"
        "\n"
        "class CustomEmbeddingProvider:\n"
        "    def __init__(self, settings: ProviderSettings) -> None:\n"
        "        self.received_settings = settings\n"
        "        self.provider_name = 'custom-embedding'\n"
        "        self.embedding_model = settings.model\n"
        "\n"
        "    def embed_texts(self, texts: list[str]) -> list[list[float]]:\n"
        "        return [[float(len(text))] for text in texts]\n",
    )
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = gemini\n"
        "model = gemini-2.5-flash\n"
        "api_key = test-key\n"
        "\n"
        "[embedding]\n"
        "provider = custom\n"
        "model = custom-embedding-model\n"
        f"class_path = {custom_module}\n"
        "class_name = CustomEmbeddingProvider\n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "gemini"
    assert provider.embedding_client.provider_name == "custom-embedding"
    assert provider.embedding_client.embedding_model == "custom-embedding-model"
    assert provider.embedding_client.received_settings is settings.embedding


@pytest.mark.parametrize(
    ("config_lines", "error_pattern"),
    [
        ("class_name = CustomChatProvider\n", r"Missing required \[chat\]\.class_path"),
        (
            "class_path = C:\\custom_provider.py\n",
            r"Missing required \[chat\]\.class_name",
        ),
    ],
)
def test_factory_rejects_custom_provider_without_required_keys(
    tmp_path: Path, config_lines: str, error_pattern: str
) -> None:
    project = create_project(tmp_path)
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = custom\n"
        "model = custom-chat-model\n"
        f"{config_lines}"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match=error_pattern):
        build_llm_provider(settings)


def test_factory_rejects_custom_provider_with_relative_path(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = custom\n"
        "model = custom-chat-model\n"
        "class_path = custom_provider.py\n"
        "class_name = CustomChatProvider\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match=r"\[chat\]\.class_path must be an absolute path"):
        build_llm_provider(settings)


def test_factory_rejects_custom_provider_when_file_is_missing(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    missing_module = tmp_path / "missing_custom_provider.py"
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = custom\n"
        "model = custom-chat-model\n"
        f"class_path = {missing_module}\n"
        "class_name = CustomChatProvider\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match=r"\[chat\]\.class_path does not exist or is not a file"):
        build_llm_provider(settings)


def test_factory_rejects_custom_provider_when_class_is_missing(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    custom_module = tmp_path / "custom_provider.py"
    _write_custom_provider(custom_module, "class AnotherProvider:\n    pass\n")
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = custom\n"
        "model = custom-chat-model\n"
        f"class_path = {custom_module}\n"
        "class_name = CustomChatProvider\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match=r"Class 'CustomChatProvider' was not found"):
        build_llm_provider(settings)


def test_factory_rejects_custom_provider_with_wrong_chat_shape(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    custom_module = tmp_path / "broken_chat_provider.py"
    _write_custom_provider(
        custom_module,
        "from dragula.config import ProviderSettings\n"
        "\n"
        "\n"
        "class BrokenChatProvider:\n"
        "    def __init__(self, settings: ProviderSettings) -> None:\n"
        "        self.provider_name = 'broken-chat'\n",
    )
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = custom\n"
        "model = custom-chat-model\n"
        f"class_path = {custom_module}\n"
        "class_name = BrokenChatProvider\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = test-key\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match=r"does not satisfy ChatClientPort"):
        build_llm_provider(settings)


def test_factory_rejects_custom_provider_with_wrong_embedding_shape(
    tmp_path: Path,
) -> None:
    project = create_project(tmp_path)
    custom_module = tmp_path / "broken_embedding_provider.py"
    _write_custom_provider(
        custom_module,
        "from dragula.config import ProviderSettings\n"
        "\n"
        "\n"
        "class BrokenEmbeddingProvider:\n"
        "    def __init__(self, settings: ProviderSettings) -> None:\n"
        "        self.provider_name = 'broken-embedding'\n",
    )
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = gemini\n"
        "model = gemini-2.5-flash\n"
        "api_key = test-key\n"
        "\n"
        "[embedding]\n"
        "provider = custom\n"
        "model = custom-embedding-model\n"
        f"class_path = {custom_module}\n"
        "class_name = BrokenEmbeddingProvider\n",
    )
    settings = load_settings(project)

    with pytest.raises(ValueError, match=r"does not satisfy EmbeddingClientPort"):
        build_llm_provider(settings)
