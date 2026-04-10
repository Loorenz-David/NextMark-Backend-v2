from __future__ import annotations
from openai import OpenAI
import logging
from Delivery_app_BK.ai.telemetry import record_ai_token_usage

logger = logging.getLogger(__name__)


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str = "gpt-4.1-mini"):
        self._client = OpenAI()
        self._model = model

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        if response.usage:
            record_ai_token_usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            logger.info(
                "OpenAI usage | model=%s | prompt_tokens=%d | completion_tokens=%d | total_tokens=%d",
                self._model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
            )
        return response.choices[0].message.content or ""
