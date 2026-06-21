"""Command-line interface for notes-digest."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .digest import build_digest_markdown
from .scanner import Cache, file_hash, find_notes
from .summarizer import DEFAULT_MODEL, Summarizer, SummarizerError


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"error: path not found: {root}", file=sys.stderr)
        return 1

    notes = find_notes(root, extensions=args.ext)
    if not notes:
        print(f"No notes found under {root} with extensions {args.ext}.")
        return 0

    cache = Cache.load(root)
    summarizer = None if args.dry_run else Summarizer(api_key=args.api_key, model=args.model)

    processed, skipped, failed = 0, 0, 0
    for note in notes:
        rel = _relative(note, root)
        content_hash = file_hash(note)

        if not args.force and cache.get(rel, content_hash):
            skipped += 1
            continue

        if args.dry_run:
            cache.set(rel, content_hash, summary="[dry-run] no summary generated", tags=[])
            processed += 1
            print(f"  dry-run: {rel}")
            continue

        try:
            text = note.read_text(errors="ignore")
            result = summarizer.summarize(text)
        except SummarizerError as exc:
            print(f"  failed:  {rel} ({exc})", file=sys.stderr)
            failed += 1
            continue

        cache.set(rel, content_hash, summary=result["summary"], tags=result["tags"])
        processed += 1
        print(f"  done:    {rel}")

    cache.save()
    print(
        f"\nScanned {len(notes)} note(s): "
        f"{processed} processed, {skipped} unchanged, {failed} failed."
    )
    return 1 if failed else 0


def cmd_digest(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    cache = Cache.load(root)
    all_entries = cache.all_entries()
    if not all_entries:
        print("No cached summaries found. Run `notes-digest scan <path>` first.", file=sys.stderr)
        return 1

    entries = [
        {"file": rel, "summary": data["summary"], "tags": data.get("tags", [])}
        for rel, data in all_entries.items()
    ]

    overview: Optional[str] = None
    if args.overview:
        try:
            summarizer = Summarizer(api_key=args.api_key, model=args.model)
            overview = summarizer.overview(entries)
        except SummarizerError as exc:
            print(f"warning: could not generate overview ({exc})", file=sys.stderr)

    markdown = build_digest_markdown(root, entries, overview=overview, title=args.title)
    output_path = Path(args.output) if args.output else root / "DIGEST.md"
    output_path.write_text(markdown)
    print(f"Wrote digest for {len(entries)} note(s) to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notes-digest",
        description="AI-powered CLI that summarizes, tags, and digests a folder of notes.",
    )
    parser.add_argument(
        "--api-key", help="Anthropic API key (defaults to the ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Summarize and tag notes in a folder, caching results.")
    scan.add_argument("path", help="Folder containing notes")
    scan.add_argument("--ext", nargs="+", default=[".md", ".txt"], help="File extensions to include")
    scan.add_argument("--force", action="store_true", help="Reprocess notes even if unchanged")
    scan.add_argument(
        "--dry-run", action="store_true", help="Skip API calls entirely; useful without a key"
    )
    scan.set_defaults(func=cmd_scan)

    digest = sub.add_parser("digest", help="Build a markdown digest from cached summaries.")
    digest.add_argument("path", help="Folder containing notes (must have been scanned first)")
    digest.add_argument("-o", "--output", help="Output markdown file (default: DIGEST.md in folder)")
    digest.add_argument("--title", help="Custom digest title")
    digest.add_argument(
        "--overview", action="store_true", help="Add a synthesized overview (one extra API call)"
    )
    digest.set_defaults(func=cmd_digest)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
