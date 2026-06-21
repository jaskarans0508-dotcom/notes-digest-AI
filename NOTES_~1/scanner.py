"""File discovery and content-hash caching for notes-digest.

The cache lets `scan` skip files whose content hasn't changed since the last
run, which keeps repeated runs fast and avoids paying for redundant API calls.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_EXTENSIONS = (".md", ".txt")
CACHE_FILENAME = ".notes_digest_cache.json"


def find_notes(root: Path, extensions: Iterable[str] = DEFAULT_EXTENSIONS) -> list[Path]:
    """Recursively find note files under `root` matching `extensions`."""
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in exts and p.name != CACHE_FILENAME
    )


def file_hash(path: Path) -> str:
    """Return a stable sha256 hash of a file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


@dataclass
class Cache:
    """JSON-backed cache mapping relative file path -> {hash, summary, tags}."""

    path: Path
    _data: dict = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> "Cache":
        cache_path = root / CACHE_FILENAME
        data: dict = {}
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
            except json.JSONDecodeError:
                data = {}
        return cls(path=cache_path, _data=data)

    def get(self, rel_path: str, content_hash: str) -> Optional[dict]:
        entry = self._data.get(rel_path)
        if entry and entry.get("hash") == content_hash:
            return entry
        return None

    def set(self, rel_path: str, content_hash: str, summary: str, tags: list[str]) -> None:
        self._data[rel_path] = {"hash": content_hash, "summary": summary, "tags": tags}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))

    def all_entries(self) -> dict:
        return dict(self._data)
