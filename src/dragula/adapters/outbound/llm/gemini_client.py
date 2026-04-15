import json
from typing import Any

from google import genai

from dragula.domain import GeneratedDescription


class GeminiClient:
    provider_name = "gemini"

    def __init__(
        self, api_key: str | None, embedding_model: str, chat_model: str
    ) -> None:
        if not api_key:
            raise ValueError("Missing api_key for gemini provider in current section.")
        if not embedding_model:
            raise ValueError("Missing model for embedding in current section.")
        if not chat_model:
            raise ValueError("Missing model for chat in current section.")
        self.client = genai.Client(api_key=api_key)
        self.embedding_model = embedding_model
        self.chat_model = chat_model

    def _extract_embedding_values(self, item: Any) -> list[float]:
        values = getattr(item, "values", None)
        if values is None and isinstance(item, dict):
            values = item.get("values")
        if values is None:
            return []
        return [float(v) for v in values]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.models.embed_content(
            model=self.embedding_model, contents=texts
        )
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings", [])
        if embeddings is None:
            return []
        return [self._extract_embedding_values(item) for item in embeddings]

    def _extract_text_from_response(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if text:
            return str(text)

        candidates = getattr(response, "candidates", None)
        if candidates is None and isinstance(response, dict):
            candidates = response.get("candidates", [])
        if not candidates:
            return "{}"

        first_candidate = candidates[0]
        content = getattr(first_candidate, "content", None)
        if content is None and isinstance(first_candidate, dict):
            content = first_candidate.get("content")
        if content is None:
            return "{}"

        parts = getattr(content, "parts", None)
        if parts is None and isinstance(content, dict):
            parts = content.get("parts", [])
        if not parts:
            return "{}"

        first_part = parts[0]
        part_text = getattr(first_part, "text", None)
        if part_text is None and isinstance(first_part, dict):
            part_text = first_part.get("text")
        return str(part_text or "{}")

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
        response = self.client.models.generate_content(
            model=self.chat_model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        text = self._extract_text_from_response(response)
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        return GeneratedDescription(
            purpose=str(data.get("purpose", "")).strip(),
            responsibilities=self._coerce_string_list(data.get("responsibilities", [])),
            references=self._coerce_string_list(
                data.get("references", data.get("referencies", []))
            ),
            raw_response=text,
        )
