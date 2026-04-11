import argparse
from pathlib import Path

import uvicorn
from rich.console import Console

from dragula.adapters.inbound.web.app import create_app
from dragula.composition import build_application, initialize_project

console = Console()


def _print_provider_help(exc: Exception) -> None:
    text = str(exc)
    if "429" in text or "insufficient_quota" in text:
        console.print(
            "[yellow]Hint:[/yellow] Provider quota exceeded. Check billing/usage limits."
        )
    if "401" in text or "unauthorized" in text.lower():
        console.print(
            "[yellow]Hint:[/yellow] Invalid credentials. Check [chat]/[embedding] auth settings in .dragula/config.ini."
        )
    if "404" in text or "model" in text.lower():
        console.print(
            "[yellow]Hint:[/yellow] Model not found. Check [chat].model / [embedding].model in .dragula/config.ini."
        )


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        settings = initialize_project(root)
    except FileExistsError:
        dragula_dir = root / ".dragula"
        console.print(
            f"[red]Already initialized:[/red] {dragula_dir} exists. Remove it to re-run [bold]dragula init[/bold]."
        )
        return 1
    except Exception as exc:
        console.print(
            f"[red]Init failed:[/red] {exc.__class__.__name__}: {exc}"
        )
        return 1
    console.print(f"Initialized dragula data at [green]{settings.dragula_dir}[/green]")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        container = build_application(root)
    except Exception as exc:
        console.print(
            f"[red]Failed to initialize LLM provider:[/red] {exc.__class__.__name__}: {exc}"
        )
        _print_provider_help(exc)
        return 1

    stats = container.index_project.run()
    console.print(
        f"Indexed files={stats.files_scanned}, symbols={stats.symbols_found}, chunks={stats.chunks_saved}, errors={len(stats.errors)}"
    )
    if stats.errors:
        console.print("[red]Indexing errors:[/red]")
        for idx, err in enumerate(stats.errors, start=1):
            console.print(f"{idx}. {err}")
        _print_provider_help(RuntimeError(stats.errors[0]))
    container.repository.close()
    return 0 if not stats.errors else 1


def cmd_serve(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    app = create_app(root)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dragula")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init", help="Create .dragula/, config.ini, SQLite schema, and Chroma store"
    )
    p_init.add_argument("path", nargs="?", default=".")
    p_init.set_defaults(func=cmd_init)

    p_index = sub.add_parser("index", help="Index a project")
    p_index.add_argument("path", nargs="?", default=".")
    p_index.set_defaults(func=cmd_index)

    p_serve = sub.add_parser("serve", help="Run documentation web UI")
    p_serve.add_argument("path", nargs="?", default=".")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
