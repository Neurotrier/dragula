from pathlib import Path

from dragula.domain import ProjectFile

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".dragula",
}


class LocalProjectFileSource:
    def __init__(
        self, project_root: Path, excluded_roots: list[Path] | None = None
    ) -> None:
        self.project_root = project_root
        self.excluded_roots = [path.resolve() for path in (excluded_roots or [])]

    def iter_python_files(self) -> list[ProjectFile]:
        files: list[ProjectFile] = []
        for path in self.project_root.rglob("*.py"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            resolved = path.resolve()
            if any(
                excluded_root in resolved.parents
                for excluded_root in self.excluded_roots
            ):
                continue
            stat = path.stat()
            files.append(
                ProjectFile(
                    relative_path=path.relative_to(self.project_root).as_posix(),
                    content=path.read_text(encoding="utf-8", errors="ignore"),
                    size_bytes=stat.st_size,
                    mtime=stat.st_mtime,
                )
            )
        return files
