from __future__ import annotations


class GeminiProvider:
    """Google Gemini provider — stub for V2."""
    name = "gemini"

    def __init__(self, model: str = "gemini-1.5-flash"):
        self._model = model

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError("GeminiProvider is not yet wired. Install google-generativeai and implement.")
