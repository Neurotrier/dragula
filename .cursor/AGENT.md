# AGENT PROMPT: Разработка Dragula с нуля

Ты — автономный инженер-разработчик. Твоя задача: реализовать систему Dragula с нуля как production-ready локальный инструмент для индексации Python-кода, retrieval-контекста и AI-описаний символов.

Ниже дан полный рабочий протокол. Следуй ему строго, в указанной последовательности.

## 1) Миссия и границы

### Что нужно построить
- Python-пакет с CLI командами `init`, `index`, `serve`.
- Локальное хранение структуры кода в SQLite.
- Локальное векторное хранение чанков в ChromaDB.
- Web UI + HTTP API для просмотра символов и генерации AI-описаний.
- Поддержка LLM провайдеров `gemini` и `openai_compatible` (возможны mixed-конфигурации chat/embedding).

### Что не нужно делать
- Не добавляй удаленные БД/облачные хранилища как обязательные.
- Не реализуй глобальный state вне `<project_root>/.dragula/`.
- Не усложняй дизайн, если это не требуется контрактами.

## 2) Обязательные архитектурные принципы

- Используй Hexagonal архитектуру (Ports & Adapters)
- Use-cases не должны зависеть от конкретных адаптеров напрямую.
- Все I/O должно идти через порты.
- Каждая операция должна быть покрываема unit-тестом через fake/mock реализацию портов.

## 3) Также:
- `pyproject.toml`
- `README.md`
- `config.ini.example`
- `tests/` с покрытием ключевых сценариев

## 4) Норматив хранения состояния

Используй только локальный путь:
- `<project_root>/.dragula/config.ini`
- `<project_root>/.dragula/symbols.sqlite3`
- `<project_root>/.dragula/chroma/`

`init` обязан:
- создать `.dragula/`,
- записать `config.ini` из шаблона,
- инициализировать SQLite schema,
- подготовить каталог Chroma.

Повторный `init` при существующей `.dragula/` — ошибка (ненулевой exit code).

## 5) Контракты конфигурации

`config.ini` должен содержать:
- `[app]` с `top_k` (int > 0),
- `[chat]` с `provider`, `model`,
- `[embedding]` с `provider`, `model`.

Требования:
- Поддержи `${ENV_VAR}` interpolation для дополнительных опций секций.
- Если env не найден, подставляй пустую строку.
- Отсутствие обязательных секций/полей — `ValueError`.
- Отсутствие файла конфигурации — `FileNotFoundError`.

## 6) Доменная модель (обязательные сущности)

Определи dataclass-модели минимум для:
- `ProjectFile` (path/content/size/mtime),
- `ParsedSymbol` (id, name, qualified_name, kind, file_path, line ranges, source),
- `Chunk` (id, symbol_id, file_path, content, order),
- `StoredSymbol` (репозиторная версия символа),
- `GeneratedDescription` (purpose, responsibilities, references, raw_response),
- `CachedDescription` (данные кеша для возврата).


## 7) Пошаговый план реализации (строго по этапам)

### Этап 1: Foundation
- Настрой packaging (`pyproject.toml`, entrypoint `dragula = ...cli:main`).
- Добавь runtime deps: `chromadb`, `fastapi`, `google-genai`, `jinja2`, `pydantic`, `rich`, `uvicorn`.
- Добавь dev deps: `pytest`.
- Подготовь модульную структуру пакета.

### Этап 2: Config + Init
- Добавь `INIT_CONFIG_INI_TEMPLATE`.
- Реализуй CLI `dragula init <path>`:
  - create `.dragula`,
  - write `config.ini`,
  - init SQLite schema,
  - init Chroma directory.

### Этап 3: Domain + AST processing
- Реализуй AST-парсер Python файлов:
  - извлечение `module/class/function/method`.
- Реализуй chunk builder:
  - разбивка source на chunks для embeddings.
- Гарантируй устойчивость: ошибка одного файла не останавливает весь индекс.

### Этап 4: Outbound adapters
- `filesystem_source`:
  - собрать `*.py` рекурсивно,
  - исключить служебные директории (`.git`, `.venv`, `.dragula`, `node_modules` и т.п.).
- `sqlite_repository`:
  - таблицы `files`, `symbols`, `chunks`, `ai_descriptions`, `index_runs`,
  - методы чтения/записи и кеша,
  - миграция legacy-схемы `ai_descriptions` в актуальную.
- `chroma_vector_index`:
  - replace-by-file стратегию (удалить старые чанки файла, добавить новые).
- `llm_factory`:
  - сборка embedding/chat клиентов по провайдеру,
  - поддержка mixed chat/embedding провайдеров.
- `gemini_client` и `openai_compatible_client`:
  - embedding и/или chat интерфейсы согласно портам.

### Этап 5: Use-cases
- `IndexProjectUseCase`:
  - `start_index_run` -> scan files -> parse symbols -> build chunks -> embed -> save sqlite/vector -> `finish_index_run`.
  - возвращай `IndexStats(files_scanned, symbols_found, chunks_saved, errors)`.
- `RetrieveContextUseCase`:
  - query -> embedding -> vector search(top_k) -> chunks.
- `DescribeSymbolUseCase`:
  - get symbol,
  - retrieve context,
  - compute `prompt_hash` и `context_hash` (sha256),
  - cache lookup по `(symbol_id, model, prompt_hash, context_hash)`,
  - на miss вызвать LLM, сохранить кеш.
- `ListSymbolsUseCase`, `GetSymbolDetailsUseCase`, `DeleteSymbolDescriptionsUseCase`.

### Этап 6: Inbound adapters
- CLI:
  - `init`, `index`, `serve`.
- Web API (FastAPI):
  - `GET /`
  - `GET /api/symbols`
  - `GET /api/symbols/{symbol_id}`
  - `POST /api/symbols/{symbol_id}/describe`
  - `DELETE /api/symbols/{symbol_id}/descriptions`
- Ошибки домена `ValueError` в details/describe/delete мапь в HTTP `404`.

### Этап 7: Composition root
- `build_application(project_root)` должен собрать:
  - settings,
  - sqlite repository,
  - vector index,
  - llm provider,
  - use-cases.
- Весь wiring централизуй в одном месте.

### Этап 8: UI минимум
- Простая HTML-страница + JS:
  - список символов,
  - отображение деталей,
  - кнопки generate description и clear cache.
- UI не должен содержать бизнес-логики, только API-вызовы.

### Этап 9: Тесты и стабилизация
- Обязательно покрыть тестами:
  - config parsing/validation/env interpolation,
  - `init`,
  - indexing pipeline,
  - retrieval,
  - describe cache hit/miss + context hash invalidation,
  - web API success/error paths,
  - llm_factory provider routing,
  - sqlite migration legacy `ai_descriptions`.


## 8) Контракты надежности и качества

- Индексация должна аккумулировать file-level ошибки в `errors`, а не падать полностью.
- Завершающий статус index run:
  - `success`, если ошибок нет,
  - `partial`, если ошибки есть.
- При ошибках провайдера добавляй диагностические hints (quota/model/auth).
- Кеш описаний должен быть детерминированным (sha256).
- API чтения должен стабильно работать под конкурентными запросами.
- Любые изменения схемы БД должны проходить через безопасную миграцию.

## 9) Требования к LLM output

Ожидай от chat-модели структуру:
- `purpose: string`
- `responsibilities: list[string]`
- `references: list[string]`

Если провайдер вернул невалидный JSON:
- не падай в необработанное исключение,
- применяй деградацию до пустых/безопасных значений,
- сохраняй `raw_response` для диагностики.

## 10) Команды smoke-проверки

После реализации агент обязан выполнить:
- `dragula init .`
- `dragula index .`
- `dragula serve .`
- `pytest`

Минимальные API-smoke:
- `GET /api/symbols` -> `200`
- `GET /api/symbols/{valid_id}` -> `200`
- `POST /api/symbols/{valid_id}/describe` -> `200`
- `DELETE /api/symbols/{valid_id}/descriptions` -> `200`
- `POST /api/symbols/{invalid_id}/describe` -> `404`

## 11) Definition of Done

Считай задачу завершенной только если одновременно выполнены условия:
- Проект собирается и запускается локально.
- Все обязательные команды CLI работают.
- Все API endpoints реализованы и соответствуют контрактам.
- Индексация пишет в SQLite и Chroma согласованно на уровне бизнес-логики.
- Кеш описаний работает по модели и hash-парам.
- Тесты проходят (`pytest` зеленый).
- README содержит инструкции запуска и конфигурации.

## 12) Формат работы агента (операционный протокол)

Работай итеративно:
1. Сформируй короткий план этапа.
2. Внеси изменения небольшими логическими блоками.
3. После каждого этапа прогоняй релевантные тесты.
4. Фиксируй принятые решения и ограничения.
5. Переходи к следующему этапу только после passing checks.

При неоднозначности:
- выбирай вариант, который проще тестировать,
- сохраняй совместимость контрактов,
- не ломай публичные команды и API.

Главный приоритет: корректность контрактов, воспроизводимость, тестируемость и прозрачная диагностика ошибок.
