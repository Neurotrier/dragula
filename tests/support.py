from pathlib import Path


def create_project(tmp_path: Path, name: str = "proj") -> Path:
    project = tmp_path / name
    project.mkdir()
    return project


def write_config(project: Path, content: str) -> Path:
    dragula_dir = project / ".dragula"
    dragula_dir.mkdir(parents=True, exist_ok=True)
    config_path = dragula_dir / "config.ini"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def write_default_test_config(
    project: Path,
    *,
    top_k: int = 6,
    chat_provider: str = "gemini",
    chat_model: str = "gemini-1.5-flash",
    chat_api_key: str = "test-key",
    chat_base_url: str = "",
    embedding_provider: str = "gemini",
    embedding_model: str = "gemini-embedding-001",
    embedding_api_key: str = "test-key",
    embedding_base_url: str = "",
) -> Path:
    return write_config(
        project,
        "[app]\n"
        f"top_k = {top_k}\n"
        "\n"
        "[chat]\n"
        f"provider = {chat_provider}\n"
        f"model = {chat_model}\n"
        f"api_key = {chat_api_key}\n"
        f"base_url = {chat_base_url}\n"
        "\n"
        "[embedding]\n"
        f"provider = {embedding_provider}\n"
        f"model = {embedding_model}\n"
        f"api_key = {embedding_api_key}\n"
        f"base_url = {embedding_base_url}\n",
    )
