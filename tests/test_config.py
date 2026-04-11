from pathlib import Path

import pytest

from dragula.config import load_settings
from tests.support import create_project, write_config


def test_load_settings_reads_config_ini(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    dragula = project / ".dragula"
    write_config(
        project,
        "[app]\n"
        "top_k = 8\n"
        "\n"
        "[chat]\n"
        "provider = openai\n"
        "model = model-chat\n"
        "base_url = http://chat.local/v1\n"
        "\n"
        "[embedding]\n"
        "provider = openai\n"
        "model = model-embed\n"
        "base_url = http://localhost:11434/v1\n",
    )

    settings = load_settings(project)

    assert settings.top_k == 8
    assert settings.chat.provider == "openai"
    assert settings.chat.model == "model-chat"
    assert settings.embedding.provider == "openai"
    assert settings.embedding.model == "model-embed"
    assert settings.dragula_dir == dragula
    assert settings.config_path == dragula / "config.ini"
    assert settings.chroma_dir == dragula / "chroma"
    assert settings.sqlite_path == dragula / "symbols.sqlite3"
    assert settings.project_root == project
    assert settings.embedding.options["base_url"] == "http://localhost:11434/v1"


def test_load_settings_resolves_provider_env_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = create_project(tmp_path)
    monkeypatch.setenv("TEST_PROVIDER_KEY", "secret-value")
    write_config(
        project,
        "[app]\n"
        "top_k = 6\n"
        "\n"
        "[chat]\n"
        "provider = gemini\n"
        "model = gemini-2.5-flash\n"
        "api_key = ${TEST_PROVIDER_KEY}\n"
        "\n"
        "[embedding]\n"
        "provider = gemini\n"
        "model = gemini-embedding-001\n"
        "api_key = ${TEST_PROVIDER_KEY}\n",
    )

    settings = load_settings(project)

    assert settings.chat.options["api_key"] == "secret-value"
    assert settings.embedding.options["api_key"] == "secret-value"


def test_load_settings_requires_config_file(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_settings(project)
