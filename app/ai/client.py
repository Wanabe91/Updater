from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from app.ai.prompts import ANALYZE_DEPENDENCY_PROMPT, SUGGEST_ALTERNATIVE_PROMPT
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    success: bool = True
    error: str | None = None
    elapsed: float = 0.0
    prompt_chars: int = 0
    prompt_lines: int = 0

    @property
    def total_tokens(self) -> int:
        return int(self.usage.get("total_tokens", 0))


def _measure_prompt(messages: list[dict]) -> tuple[int, int]:
    chars = 0
    lines = 0
    for message in messages:
        content = message.get("content", "") or ""
        chars += len(content)
        lines += content.count("\n") + (1 if content else 0)
    return chars, lines


class AIClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        resolved_key = api_key or settings.openai_api_key
        resolved_model = model or settings.openai_model
        resolved_base_url = base_url or settings.openai_base_url

        self.model = resolved_model
        self._client = OpenAI(
            api_key=resolved_key,
            base_url=resolved_base_url,
        )

    def chat(self, messages: list[dict], temperature: float = 0.2) -> AIResponse:
        prompt_chars, prompt_lines = _measure_prompt(messages)
        started = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            elapsed = time.perf_counter() - started
            choice = response.choices[0]
            content = choice.message.content or ""

            usage: dict[str, Any] = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return AIResponse(
                content=content,
                model=response.model,
                usage=usage,
                success=True,
                elapsed=elapsed,
                prompt_chars=prompt_chars,
                prompt_lines=prompt_lines,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            logger.error("AI chat request failed: %s", exc)
            return AIResponse(
                content="",
                model=self.model,
                success=False,
                error=str(exc),
                elapsed=elapsed,
                prompt_chars=prompt_chars,
                prompt_lines=prompt_lines,
            )

    def analyze_dependency(self, package: str, version: str, ecosystem: str) -> AIResponse:
        prompt = ANALYZE_DEPENDENCY_PROMPT.format(
            package=package,
            version=version,
            ecosystem=ecosystem,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a dependency analysis expert. "
                    "Provide concise, accurate analysis."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return self.chat(messages, temperature=0.1)

    def suggest_alternative(self, package: str, version: str, ecosystem: str) -> AIResponse:
        prompt = SUGGEST_ALTERNATIVE_PROMPT.format(
            package=package,
            version=version,
            ecosystem=ecosystem,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a dependency migration expert. "
                    "Respond only in valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = self.chat(messages, temperature=0.2)
        if response.success:
            try:
                response.content = extract_json(response.content)
            except ValueError:
                logger.warning("Failed to parse JSON from suggest_alternative response")
        return response


def extract_json(text: str) -> str:
    """Return the validated JSON object substring of an AI response."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")
    json_str = text[start:end]
    try:
        json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in response: {exc}") from exc
    return json_str
