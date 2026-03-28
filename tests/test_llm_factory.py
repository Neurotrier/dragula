from pathlib import Path

import pytest

from dragula.adapters.outbound.llm_factory import build_llm_provider
from dragula.config import load_settings


def _write_config(project: Path, content: str) -> None:
    dragula = project / ".dragula"
    dragula.mkdir(parents=True)
    (dragula / "config.ini").write_text(content, encoding="utf-8")


def test_factory_builds_gemini_provider(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _write_config(
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


def test_factory_builds_openai_compatible_provider(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = openai_compatible\n"
        "model = gpt-4o-mini\n"
        "base_url = http://localhost:11434/v1\n"
        "api_key = \n"
        "\n"
        "[embedding]\n"
        "provider = openai_compatible\n"
        "model = text-embedding-3-small\n"
        "base_url = http://localhost:11434/v1\n"
        "api_key = \n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "openai_compatible"
    assert provider.embedding_client.provider_name == "openai_compatible"


def test_factory_rejects_unknown_provider(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _write_config(
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
    project = tmp_path / "proj"
    project.mkdir()
    _write_config(
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
        "provider = openai_compatible\n"
        "model = text-embedding-3-small\n"
        "base_url = http://localhost:11434/v1\n"
        "api_key = \n",
    )
    settings = load_settings(project)

    provider = build_llm_provider(settings)

    assert provider.chat_client.provider_name == "gemini"
    assert provider.embedding_client.provider_name == "openai_compatible"
