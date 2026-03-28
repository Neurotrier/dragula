<img src="https://raw.githubusercontent.com/Neurotrier/dragula/dev/docs/dragula.png" width="228" />

## Description

`Dragula` (D-RAG-ula) is a Python library that indexes a Python codebase and serves a local web UI for AI-generated object documentation over pluggable LLM providers.

## Features

- CLI commands: `init`, `index`, `serve`
- AST-based symbol extraction (module/class/function/method)
- SQLite storage for structured symbol data
- ChromaDB storage for semantic chunk vectors
- FastAPI web UI to browse symbols and request AI descriptions (also available via HTTP API)

## Install

Requires **Python 3.11+**.

```bash
pip install dragula
```

## Configuration

Dragula keeps its config and local databases under `<project_root>/.dragula/` (fixed location, similar in spirit to an Alembic env directory).

Initialize once in the target project (creates `.dragula/`, a template `config.ini`, SQLite tables, and the Chroma data directory):

```bash
dragula init .
```

Edit `.dragula/config.ini` for your LLM providers.

### Minimal Gemini config

```ini
[app]
top_k = 6

[chat]
provider = gemini
model = gemini-2.5-flash
api_key = ${GEMINI_API_KEY}
base_url =
timeout_seconds = 60

[embedding]
provider = gemini
model = gemini-embedding-001
api_key = ${GEMINI_API_KEY}
base_url =
timeout_seconds = 60
```

### Mixed providers (chat remote, embedding local)

```ini
[app]
top_k = 6

[chat]
provider = gemini
model = gemini-2.5-flash
api_key = ${GEMINI_API_KEY}
base_url =
timeout_seconds = 60

[embedding]
provider = openai_compatible
model = text-embedding-3-small
base_url = http://localhost:11434/v1
api_key =
timeout_seconds = 60
```

## Usage

Initialize (first time only):

```bash
dragula init .
```

Build index:

```bash
dragula index .
```

Run web UI (default `http://127.0.0.1:8000`):

```bash
dragula serve .
```

Optional server binding:

```bash
dragula serve . --host 0.0.0.0 --port 8080
```

## HTTP API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Web UI |
| `GET` | `/api/symbols` | List symbols |
| `GET` | `/api/symbols/{symbol_id}` | Symbol details and chunks |
| `POST` | `/api/symbols/{symbol_id}/describe` | Generate AI description |
| `DELETE` | `/api/symbols/{symbol_id}/descriptions` | Clear cached descriptions for a symbol |

## Data layout

Under the project root:

- `.dragula/config.ini` — configuration
- `.dragula/symbols.sqlite3` — structured symbol/chunk/description tables
- `.dragula/chroma/` — Chroma persistent vector store
