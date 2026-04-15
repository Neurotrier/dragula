import configparser
import os
import re
from dataclasses import dataclass
from pathlib import Path

DRAGULA_DIR = ".dragula"
ALLOWED_PROVIDERS = ("openai", "gemini", "custom")

INIT_CONFIG_INI_TEMPLATE = """[app]
top_k = 6

[chat]
provider = gemini
model = gemini-2.5-flash
api_key = ${GEMINI_API_KEY}
base_url =
timeout_seconds = 60
# Custom provider:
# provider = custom
# model = custom-chat-model
# class_path = C:/absolute/path/to/custom_chat_provider.py
# class_name = CustomChatProvider

[embedding]
provider = gemini
model = gemini-embedding-001
api_key = ${GEMINI_API_KEY}
base_url =
timeout_seconds = 60
# Custom provider:
# provider = custom
# model = custom-embedding-model
# class_path = C:/absolute/path/to/custom_embedding_provider.py
# class_name = CustomEmbeddingProvider
"""


@dataclass(slots=True)
class ProviderSettings:
    provider: str
    model: str
    options: dict[str, str]


@dataclass(slots=True)
class Settings:
    project_root: Path
    dragula_dir: Path
    config_path: Path
    chroma_dir: Path
    sqlite_path: Path
    chat: ProviderSettings
    embedding: ProviderSettings
    top_k: int


def dragula_dir_for(project_root: Path | str) -> Path:
    return Path(project_root).resolve() / DRAGULA_DIR


def load_settings(project_root: Path | str) -> Settings:
    root = Path(project_root).resolve()
    dragula_dir = root / DRAGULA_DIR
    config_path = dragula_dir / "config.ini"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")

    if not parser.has_section("app"):
        raise ValueError("Missing [app] section in config.ini")
    if not parser.has_section("chat"):
        raise ValueError("Missing [chat] section in config.ini")
    if not parser.has_section("embedding"):
        raise ValueError("Missing [embedding] section in config.ini")

    top_k_raw = parser.get("app", "top_k", fallback="6").strip()
    try:
        top_k = int(top_k_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid [app].top_k value: {top_k_raw}") from exc
    if top_k <= 0:
        raise ValueError("[app].top_k must be > 0")

    chat = _parse_provider_section(parser, "chat")
    embedding = _parse_provider_section(parser, "embedding")

    return Settings(
        project_root=root,
        dragula_dir=dragula_dir,
        config_path=config_path,
        chroma_dir=dragula_dir / "chroma",
        sqlite_path=dragula_dir / "symbols.sqlite3",
        chat=chat,
        embedding=embedding,
        top_k=top_k,
    )


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_env_placeholders(value: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, "")

    return _ENV_PATTERN.sub(_replace, value)


def _parse_provider_section(
    parser: configparser.ConfigParser, section: str
) -> ProviderSettings:
    provider = parser.get(section, "provider", fallback="").strip()
    if not provider:
        raise ValueError(f"Missing required [{section}].provider in config.ini")
    model = parser.get(section, "model", fallback="").strip()
    if not model:
        raise ValueError(f"Missing required [{section}].model in config.ini")
    options: dict[str, str] = {}
    for key, value in parser.items(section):
        if key in {"provider", "model"}:
            continue
        options[key] = _resolve_env_placeholders(value.strip())
    return ProviderSettings(provider=provider, model=model, options=options)
