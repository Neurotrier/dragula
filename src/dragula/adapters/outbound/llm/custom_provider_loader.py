import importlib.util
import inspect
from pathlib import Path
from typing import cast

from dragula.application.ports import ChatClientPort, EmbeddingClientPort
from dragula.config import ProviderSettings


def load_custom_provider_instance(section: str, settings: ProviderSettings) -> object:
    class_path_raw = settings.options.get("class_path", "").strip()
    class_name = settings.options.get("class_name", "").strip()
    if not class_path_raw:
        raise ValueError(
            f"Missing required [{section}].class_path for custom provider."
        )
    if not class_name:
        raise ValueError(
            f"Missing required [{section}].class_name for custom provider."
        )

    class_path = Path(class_path_raw)
    if not class_path.is_absolute():
        raise ValueError(
            f"[{section}].class_path must be an absolute path, got: {class_path_raw}"
        )
    if not class_path.is_file():
        raise ValueError(
            f"[{section}].class_path does not exist or is not a file: {class_path_raw}"
        )

    module_name = f"dragula_custom_{section}_{abs(hash(class_path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, class_path)
    if spec is None or spec.loader is None:
        raise ValueError(
            f"Failed to load module from [{section}].class_path: {class_path}"
        )

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ValueError(
            f"Failed to execute custom provider module for [{section}]: {class_path}"
        ) from exc

    provider_class = getattr(module, class_name, None)
    if provider_class is None:
        raise ValueError(
            f"Class '{class_name}' was not found in custom provider module: {class_path}"
        )
    if not inspect.isclass(provider_class):
        raise ValueError(
            f"[{section}].class_name must refer to a class, got: {class_name}"
        )

    try:
        return provider_class(settings)
    except Exception as exc:
        raise ValueError(
            f"Failed to instantiate custom provider '{class_name}' for [{section}]."
        ) from exc


def validate_custom_chat_client(section: str, client: object) -> ChatClientPort:
    errors = _collect_missing_members(
        client,
        required_attributes=("provider_name", "chat_model"),
        required_methods=("generate_description",),
    )
    if errors:
        raise ValueError(
            f"Custom provider for [{section}] does not satisfy ChatClientPort: "
            f"{', '.join(errors)}."
        )
    return cast(ChatClientPort, client)


def validate_custom_embedding_client(
    section: str, client: object
) -> EmbeddingClientPort:
    errors = _collect_missing_members(
        client,
        required_attributes=("provider_name", "embedding_model"),
        required_methods=("embed_texts",),
    )
    if errors:
        raise ValueError(
            f"Custom provider for [{section}] does not satisfy EmbeddingClientPort: "
            f"{', '.join(errors)}."
        )
    return cast(EmbeddingClientPort, client)


def _collect_missing_members(
    client: object,
    *,
    required_attributes: tuple[str, ...],
    required_methods: tuple[str, ...],
) -> list[str]:
    missing: list[str] = []
    for name in required_attributes:
        if not hasattr(client, name):
            missing.append(f"missing attribute '{name}'")
    for name in required_methods:
        value = getattr(client, name, None)
        if not callable(value):
            missing.append(f"missing method '{name}'")
    return missing
