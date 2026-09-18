#!/usr/bin/env python3
"""Measure skill-profile and progressive-loading context sizes."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from skill_catalog import build_catalog, catalog_for, search
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


def percent(saved: int, total: int) -> float:
    return 0.0 if total <= 0 else max(0.0, min(100.0, saved * 100 / total))


def bar(value: float, width: int = 32) -> str:
    filled = round(width * value / 100)
    return "[" + "#" * filled + "." * (width - filled) + "]"


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
    selector_payload_chars = len(json.dumps({"task": QUERIES[0], "catalog": metadata}, ensure_ascii=False))

    with tempfile.TemporaryDirectory(prefix="skill-catalog-benchmark-") as cache:
        started = time.perf_counter()
        catalog_for(ROOT, full_roots, cache, True)
        cold_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        catalog_for(ROOT, full_roots, cache, True)
        warm_ms = (time.perf_counter() - started) * 1000

    print("Skill context benchmark")
    print("=======================")
    print(f"Full catalog:     {len(full):>3} skills, {full_chars:>8,} chars, ~{tokens(full_chars):,} tokens")
    print(f"Core profile:     {len(core):>3} skills, {core_chars:>8,} chars, ~{tokens(core_chars):,} tokens")
    print(f"Metadata index:   {len(metadata):>3} skills, {metadata_chars:>8,} chars, ~{tokens(metadata_chars):,} tokens")
    print(f"Core metadata:    {len(core_metadata):>3} skills, {core_metadata_chars:>8,} chars, ~{tokens(core_metadata_chars):,} tokens")
    startup_reduction = percent(metadata_chars - core_metadata_chars, metadata_chars)
    core_reduction = percent(full_chars - core_chars, full_chars)
    print()
    print("CONTEXT SAVINGS")
    print(f"Startup metadata  {bar(startup_reduction)} {startup_reduction:5.1f}% saved")
    print(f"Core skill bodies {bar(core_reduction)} {core_reduction:5.1f}% saved")
    print()
    print("ROUTER AND CACHE")
    print(f"Selector payload:  {selector_payload_chars:>8,} chars, ~{tokens(selector_payload_chars):,} tokens")
    print(f"Cold index build:  {cold_ms:>8.2f} ms")
    print(f"Warm cache read:   {warm_ms:>8.2f} ms")
    print(f"Cache speedup:     {cold_ms / warm_ms:>8.1f}x" if warm_ms else "Cache speedup:          n/a")
    print()

    selected_total = 0
    for query in QUERIES:
        selected = search(full, query, 3)
        selected_chars = sum(chars(item["path"]) for item in selected)
        selected_total += selected_chars
        names = ", ".join(item["name"] for item in selected) or "none"
        print(f"{query}")
        print(f"  selected: {names}")
        print(f"  loaded:   {selected_chars:,} chars, ~{tokens(selected_chars):,} tokens")
    average_selected = selected_total // len(QUERIES) if QUERIES else 0
    print()
    print("TASK LOAD")
    print(f"Average selected load: {average_selected:,} chars, ~{tokens(average_selected):,} tokens")
    print(f"Versus full catalog:   {bar(percent(full_chars - average_selected, full_chars))} {percent(full_chars - average_selected, full_chars):5.1f}% saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
