from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


@dataclass
class AIResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class AIClient:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4") -> None:
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def chat(self, messages: list[dict], temperature: float = 0.2) -> AIResponse:
        raise NotImplementedError

    def analyze_dependency(self, package: str, version: str, ecosystem: str) -> AIResponse:
        raise NotImplementedError

    def suggest_alternative(self, package: str, version: str, ecosystem: str) -> AIResponse:
        raise NotImplementedError