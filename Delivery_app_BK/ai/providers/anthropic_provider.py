from __future__ import annotations


class AnthropicProvider:
    """Claude/Anthropic provider — stub for V2."""
    name = "anthropic"

    def __init__(self, model: str = "claude-3-5-haiku-20241022"):
        self._model = model

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError("AnthropicProvider is not yet wired. Install anthropic and implement.")
