import ast
import hashlib

from dragula.domain import Chunk, ParsedSymbol


def build_chunks(symbol: ParsedSymbol, max_chars: int = 1800) -> list[Chunk]:
    text = symbol.source.strip()
    if not text:
        return []
    parts: list[str] = []
    while text:
        parts.append(text[:max_chars])
        text = text[max_chars:]

    chunks: list[Chunk] = []
    for idx, content in enumerate(parts):
        chunk_id = f"{symbol.symbol_id}:{idx}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                symbol_id=symbol.symbol_id,
                file_path=symbol.file_path,
                chunk_index=idx,
                content=content,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                kind=symbol.kind,
                embedding_ref=chunk_id,
            )
        )
    return chunks


def parse_file_symbols(relative_path: str, source: str) -> list[ParsedSymbol]:
    module = ast.parse(source)
    symbols: list[ParsedSymbol] = []

    module_name = relative_path[:-3].replace("/", ".")
    module_id = _build_symbol_id(relative_path, module_name, "module")
    symbols.append(
        ParsedSymbol(
            symbol_id=module_id,
            parent_symbol_id=None,
            file_path=relative_path,
            name=module_name.split(".")[-1],
            qualified_name=module_name,
            kind="module",
            signature=None,
            docstring=ast.get_docstring(module),
            start_line=1,
            end_line=max(len(source.splitlines()), 1),
            source=source,
        )
    )

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[tuple[str, str]] = [(module_id, module_name)]

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            parent_id, parent_qname = self.stack[-1]
            qname = f"{parent_qname}.{node.name}"
            symbol_id = _build_symbol_id(relative_path, qname, "class")
            segment = ast.get_source_segment(source, node) or ""
            symbols.append(
                ParsedSymbol(
                    symbol_id=symbol_id,
                    parent_symbol_id=parent_id,
                    file_path=relative_path,
                    name=node.name,
                    qualified_name=qname,
                    kind="class",
                    signature=None,
                    docstring=ast.get_docstring(node),
                    start_line=getattr(node, "lineno", 1),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    source=segment,
                )
            )
            self.stack.append((symbol_id, qname))
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node, is_async=False)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node, is_async=True)

        def _visit_function(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
        ) -> None:
            parent_id, parent_qname = self.stack[-1]
            kind = (
                "method"
                if parent_qname != module_name
                and parent_qname.count(".") >= module_name.count(".") + 1
                else "function"
            )
            qname = f"{parent_qname}.{node.name}"
            symbol_id = _build_symbol_id(relative_path, qname, kind)
            segment = ast.get_source_segment(source, node) or ""
            symbols.append(
                ParsedSymbol(
                    symbol_id=symbol_id,
                    parent_symbol_id=parent_id,
                    file_path=relative_path,
                    name=node.name,
                    qualified_name=qname,
                    kind=kind,
                    signature=_signature_from_node(node),
                    docstring=ast.get_docstring(node),
                    start_line=getattr(node, "lineno", 1),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    source=segment,
                    is_async=is_async,
                )
            )
            self.stack.append((symbol_id, qname))
            self.generic_visit(node)
            self.stack.pop()

    Visitor().visit(module)
    return symbols


def _build_symbol_id(file_path: str, qualified_name: str, kind: str) -> str:
    raw = f"{file_path}:{qualified_name}:{kind}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:16]
    return f"{kind}:{digest}"


def _signature_from_node(node: ast.AST) -> str | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    args = []
    for arg in node.args.args:
        args.append(arg.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return f"({', '.join(args)})"
