import json
from dataclasses import dataclass
from typing import Any
from urllib import request

from dragula.domain import GeneratedDescription


@dataclass(slots=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str | None
    embedding_model: str
    chat_model: str
    timeout_seconds: float = 60.0


class OpenAICompatibleClient:
    provider_name = "openai"

    def __init__(self, config: OpenAICompatibleConfig) -> None:
        if not config.base_url:
            raise ValueError(
                "Missing base_url for openai_compatible provider in current section."
            )
        if not config.embedding_model:
            raise ValueError("Missing model for embedding in current section.")
        if not config.chat_model:
            raise ValueError("Missing model for chat in current section.")
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.embedding_model = config.embedding_model
        self.chat_model = config.chat_model
        self.timeout_seconds = config.timeout_seconds

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method="POST"
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self.embedding_model, "input": texts}
        data = self._post_json("/embeddings", payload)
        rows = data.get("data", [])
        result: list[list[float]] = []
        for item in rows:
            values = item.get("embedding", [])
            result.append([float(v) for v in values])
        return result

    def _coerce_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    def generate_description(
        self, symbol_name: str, context_chunks: list[str]
    ) -> GeneratedDescription:
        context_block = (
            "\n\n".join(context_chunks) if context_chunks else "(no context retrieved)"
        )
        prompt = (
            "You are a code documentation assistant.\n"
            "Use only the provided context. Do not invent facts, files, calls, or usages.\n"
            "Return exactly one JSON object with exactly these keys: purpose, responsibilities, references.\n"
            'The value of "purpose" must be a short, strict description of the target object.\n'
            'The value of "responsibilities" must be an array of short strings describing only the main usage areas of the object.\n'
            'The value of "references" must be an array of short strings names where the object is used, if that is explicitly visible in the context.\n'
            "If the context is insufficient, use an empty string for purpose and empty arrays for list fields.\n"
            "Do not output markdown, comments, explanations, or any extra keys.\n"
            f"Target symbol: {symbol_name}\n"
            "Context:\n" + context_block
        )
        payload = {
            "model": self.chat_model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        data = self._post_json("/chat/completions", payload)
        choices = data.get("choices", [])
        content = ""
        if choices:
            content = str(choices[0].get("message", {}).get("content", "")).strip()
        try:
            parsed = json.loads(content) if content else {}
        except json.JSONDecodeError:
            parsed = {}
        return GeneratedDescription(
            purpose=str(parsed.get("purpose", "")).strip(),
            responsibilities=self._coerce_string_list(
                parsed.get("responsibilities", [])
            ),
            references=self._coerce_string_list(
                parsed.get("references", parsed.get("referencies", []))
            ),
            raw_response=content,
        )
