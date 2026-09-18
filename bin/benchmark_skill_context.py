#!/usr/bin/env python3
"""Measure skill-profile and progressive-loading context sizes."""

from __future__ import annotations

import json
from pathlib import Path

from skill_catalog import build_catalog, search
from skill_profile import CORE_SKILLS


ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
QUERIES = (
    "debug the Python codebase",
    "build a React dashboard and test it in a browser",
    "create a PDF report",
    "configure OpenCode and delegate coding",
)


def chars(path: str) -> int:
    try:
        return Path(path).read_text(encoding="utf-8").__len__()
    except (OSError, UnicodeError):
        return 0


def tokens(count: int) -> int:
    # Conservative planning estimate; exact tokenizer counts vary by model.
    return (count + 3) // 4


def unique(entries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result = []
    for entry in entries:
        if entry["name"].lower() not in seen:
            seen.add(entry["name"].lower())
            result.append(entry)
    return result


def main() -> int:
    full_roots = [
        ROOT / "skill-catalog",
        ROOT / ".agents" / "skills",
        ROOT / ".codex" / "skills",
        ROOT / ".claude" / "skills",
        HOME / ".agents" / "skills",
        HOME / ".codex" / "skills",
        HOME / ".claude" / "skills",
        *sorted(HOME.glob(".codex/skills.catalog-backup-*")),
        *sorted(HOME.glob(".claude/skills.catalog-backup-*")),
    ]
    full = unique(build_catalog(full_roots))
    core_names = {name.lower() for name in CORE_SKILLS}
    # Profile entries are symlinks; build_catalog intentionally does not walk
    # through symlinked directories, so derive their body sizes from the full
    # catalog while preserving the exact profile manifest.
    core = [item for item in full if item["name"].lower() in core_names]
    metadata = [{key: item[key] for key in ("name", "description", "tags")} for item in full]
    core_metadata = [{key: item[key] for key in ("name", "description", "tags")} for item in core]
    full_chars = sum(chars(item["path"]) for item in full)
    core_chars = sum(chars(item["path"]) for item in core)
    metadata_chars = len(json.dumps(metadata, ensure_ascii=False))
    core_metadata_chars = len(json.dumps(core_metadata, ensure_ascii=False))

    print("Skill context benchmark")
    print("=======================")
    print(f"Full catalog:     {len(full):>3} skills, {full_chars:>8,} chars, ~{tokens(full_chars):,} tokens")
    print(f"Core profile:     {len(core):>3} skills, {core_chars:>8,} chars, ~{tokens(core_chars):,} tokens")
    print(f"Metadata index:   {len(metadata):>3} skills, {metadata_chars:>8,} chars, ~{tokens(metadata_chars):,} tokens")
    print(f"Core metadata:    {len(core_metadata):>3} skills, {core_metadata_chars:>8,} chars, ~{tokens(core_metadata_chars):,} tokens")
    print(f"Startup reduction:{max(0, 100 - (core_metadata_chars * 100 // metadata_chars)):>4}% by metadata size")
    print(f"Core reduction:   {max(0, 100 - (core_chars * 100 // full_chars))}% by skill body size")
    print()

    for query in QUERIES:
        selected = search(full, query, 3)
        selected_chars = sum(chars(item["path"]) for item in selected)
        names = ", ".join(item["name"] for item in selected) or "none"
        print(f"{query}")
        print(f"  selected: {names}")
        print(f"  loaded:   {selected_chars:,} chars, ~{tokens(selected_chars):,} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
