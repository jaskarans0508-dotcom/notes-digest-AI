"""Calls the Claude API to summarize and tag note content."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

# Small, inexpensive model -- summarizing/tagging notes doesn't need a big one.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

SUMMARIZE_SYSTEM_PROMPT = (
    "You summarize personal notes. Given the note text, respond with ONLY a "
    'JSON object of the form {"summary": "<one or two sentence summary>", '
    '"tags": ["<lowercase-tag>", ...]}. Use 2-5 short tags. No prose, no '
    "markdown code fences, just the JSON object."
)

OVERVIEW_SYSTEM_PROMPT = (
    "You write a short overview for a digest of personal notes. Given a list "
    "of (filename, summary, tags) entries, write 2-4 sentences highlighting "
    "themes and anything that stands out. Plain text, no markdown headers."
)


class SummarizerError(RuntimeError):
    """Raised when the model can't be called or its response can't be used."""


def _extract_json(text: str) -> dict:
    """Pull the first {...} block out of a model response and parse it."""
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise SummarizerError(f"Could not find JSON in model response: {text!r}")
    return json.loads(match.group(0))


class Summarizer:
    """Thin wrapper around the Anthropic client for note summarization."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None  # created lazily so --dry-run never needs the SDK

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise SummarizerError(
                    "No API key found. Set ANTHROPIC_API_KEY or pass --api-key."
                )
            import anthropic  # imported lazily; only required for real runs

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def _text_of(response) -> str:
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )

    def summarize(self, text: str, max_chars: int = 12000) -> dict:
        """Return {"summary": str, "tags": list[str]} for the given note text."""
        client = self._get_client()
        snippet = text[:max_chars]
        response = client.messages.create(
            model=self.model,
            max_tokens=300,
            system=SUMMARIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": snippet}],
        )
        raw = self._text_of(response)
        try:
            data = _extract_json(raw)
        except (SummarizerError, json.JSONDecodeError) as exc:
            raise SummarizerError(f"Failed to parse model response: {exc}") from exc

        summary = str(data.get("summary", "")).strip()
        tags = [str(t).strip().lower() for t in data.get("tags", []) if str(t).strip()]
        if not summary:
            raise SummarizerError("Model returned an empty summary.")
        return {"summary": summary, "tags": tags}

    def overview(self, entries: list[dict]) -> str:
        """Return a short synthesized overview paragraph for a digest."""
        client = self._get_client()
        listing = "\n".join(
            f"- {e['file']}: {e['summary']} (tags: {', '.join(e['tags']) or 'none'})"
            for e in entries
        )
        response = client.messages.create(
            model=self.model,
            max_tokens=200,
            system=OVERVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": listing}],
        )
        return self._text_of(response).strip()
