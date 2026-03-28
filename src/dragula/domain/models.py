from dataclasses import dataclass


@dataclass(slots=True)
class ParsedSymbol:
    symbol_id: str
    parent_symbol_id: str | None
    file_path: str
    name: str
    qualified_name: str
    kind: str
    signature: str | None
    docstring: str | None
    start_line: int
    end_line: int
    source: str
    is_async: bool = False


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    symbol_id: str
    file_path: str
    chunk_index: int
    content: str
    start_line: int
    end_line: int
    kind: str
    embedding_ref: str | None = None


@dataclass(slots=True)
class StoredSymbol:
    id: str
    parent_symbol_id: str | None
    name: str
    qualified_name: str
    kind: str
    file_path: str
    signature: str | None
    docstring: str | None
    start_line: int
    end_line: int
    is_async: bool = False


@dataclass(slots=True)
class CachedDescription:
    purpose: str
    responsibilities: list[str]
    references: list[str]
    raw_response: str


@dataclass(slots=True)
class GeneratedDescription:
    purpose: str
    responsibilities: list[str]
    references: list[str]
    raw_response: str


@dataclass(slots=True)
class FileRecord:
    path: str
    checksum: str
    size_bytes: int
    mtime: float


@dataclass(slots=True)
class ProjectFile:
    relative_path: str
    content: str
    size_bytes: int
    mtime: float
