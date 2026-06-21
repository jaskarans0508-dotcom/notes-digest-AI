"""Builds markdown digests from cached note summaries."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional


def build_digest_markdown(
    root: Path,
    entries: list[dict],
    overview: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Render a digest of note summaries (and an optional tag index) as markdown."""
    title = title or f"Notes Digest — {root.name}"
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# {title}", "", f"_Generated {generated} from {len(entries)} note(s)._", ""]

    if overview:
        lines += [overview, ""]

    tag_index: dict[str, list[str]] = {}
    for entry in entries:
        for tag in entry["tags"]:
            tag_index.setdefault(tag, []).append(entry["file"])

    if tag_index:
        tag_line = ", ".join(f"`{t}` ({len(files)})" for t, files in sorted(tag_index.items()))
        lines += [f"**Tags:** {tag_line}", ""]

    lines.append("## Notes")
    lines.append("")
    for entry in sorted(entries, key=lambda e: e["file"]):
        tag_str = ", ".join(entry["tags"]) if entry["tags"] else "untagged"
        lines.append(f"### {entry['file']}")
        lines.append(f"*Tags: {tag_str}*")
        lines.append("")
        lines.append(entry["summary"])
        lines.append("")

    return "\n".join(lines)
