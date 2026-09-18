#!/usr/bin/env python3
"""Build and query a compact catalog of Agent Skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+.#/_-]*")
STOPWORDS = {
    "a", "an", "and", "build", "code", "create", "do", "for", "from", "help",
    "in", "it", "make", "my", "of", "on", "please", "review", "test", "the",
    "this", "to", "with",
}


def _default_roots(repo: Path) -> list[Path]:
    home = Path.home()
    roots = list(dict.fromkeys(path.expanduser() for path in (
        repo / ".agents" / "skills", repo / ".codex" / "skills", repo / ".claude" / "skills",
        home / ".agents" / "skills", home / ".codex" / "skills", home / ".claude" / "skills",
    )))
    roots.extend(sorted(home.glob(".codex/skills.catalog-backup-*")))
    roots.extend(sorted(home.glob(".claude/skills.catalog-backup-*")))
    return list(dict.fromkeys(roots))


def _roots(repo: Path, raw: str | None) -> list[Path]:
    raw = raw or os.environ.get("SKILL_CATALOG_ROOTS")
    return [Path(item).expanduser() for item in raw.split(os.pathsep) if item] if raw else _default_roots(repo)


def _cache_path(repo: Path, cache_dir: str | None) -> Path:
    base = Path(cache_dir or os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    key = hashlib.sha256(str(repo).encode("utf-8")).hexdigest()[:16]
    return base.expanduser() / "skill-catalog" / key / "index.json"


def _manifest(roots: list[Path]) -> list[dict[str, int | str]]:
    files: list[dict[str, int | str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append({"path": str(path.resolve()), "mtime_ns": stat.st_mtime_ns, "size": stat.st_size})
    return files


def catalog_for(repo: Path, roots: list[Path], cache_dir: str | None, use_cache: bool) -> list[dict[str, Any]]:
    path = _cache_path(repo, cache_dir)
    manifest = _manifest(roots)
    root_manifest = [str(root.resolve()) for root in roots]
    if use_cache:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("roots") == root_manifest and cached.get("manifest") == manifest:
                return cached["skills"]
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    skills = build_catalog(roots)
    if use_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "roots": root_manifest, "manifest": manifest, "skills": skills}, ensure_ascii=False), encoding="utf-8")
    return skills


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    values: dict[str, Any] = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            values[key] = [item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()]
        else:
            values[key] = value
    return values


def build_catalog(roots: list[Path]) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for skill_file in sorted(root.rglob("SKILL.md")):
            try:
                text = skill_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            meta = _frontmatter(text)
            name = str(meta.get("name") or skill_file.parent.name)
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            entry = {
                "name": name,
                "description": str(meta.get("description") or "").strip(),
                "tags": tags,
                "path": str(skill_file.resolve()),
                "source": str(skill_file.parent),
            }
            # Earlier roots win, matching project/local precedence.
            entries.setdefault(name.lower(), entry)
    return sorted(entries.values(), key=lambda item: item["name"].lower())


def _tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower()))


def search(entries: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    query_tokens = _tokens(query) - STOPWORDS
    query_lower = query.lower()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for entry in entries:
        name = entry["name"].lower()
        tags = " ".join(entry.get("tags", []))
        description = entry.get("description", "")
        haystack = " ".join((name, description, tags, entry.get("source", ""))).lower()
        score = 12 if query_lower in haystack else 0
        for token in query_tokens:
            if token in _tokens(name):
                score += 4
            elif token in _tokens(tags):
                score += 3
            elif token in _tokens(description):
                score += 3
            elif token in _tokens(entry.get("source", "")):
                score += 1
        if score >= 2:
            ranked.append((score, entry))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["name"].lower()))
    return [entry | {"score": score} for score, entry in ranked[:limit]]


def _selection_instruction(entries: list[dict[str, Any]], query: str, limit: int) -> str:
    compact = [{"name": item["name"], "description": item["description"], "tags": item["tags"]} for item in entries]
    return (
        "Select the most relevant skills for the task. Return JSON only as "
        '{"skills":["name"]}. Choose at most %d names and never invent names.\n\n'
        "TASK: %s\n\nCATALOG:\n%s"
    ) % (limit, query, json.dumps(compact, ensure_ascii=False))


def _parse_selection(text: str, entries: list[dict[str, Any]], limit: int, backend: str) -> list[dict[str, Any]]:
    by_name = {item["name"].lower(): item for item in entries}
    candidates = re.findall(r"\{.*?\}", text, re.DOTALL)
    candidates.insert(0, text)
    for candidate in candidates:
        try:
            payload = json.loads(candidate.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            continue
        names = payload.get("skills")
        if isinstance(names, list):
            return [by_name[str(name).lower()] | {"score": 0, "backend": backend} for name in names if str(name).lower() in by_name][:limit]
    return []


def _http_json(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _remote_select(entries: list[dict[str, Any]], query: str, limit: int, backend: str, endpoint: str | None, model: str | None) -> list[dict[str, Any]]:
    instruction = _selection_instruction(entries, query, limit)
    if backend == "opencode":
        try:
            result = subprocess.run(["opencode", "run", instruction, "--format", "json"], text=True, capture_output=True, check=True, timeout=90)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"OpenCode selector failed: {exc}") from exc
        return _parse_selection(result.stdout, entries, limit, backend)
    if backend == "ollama":
        payload = {"model": model or os.environ.get("SKILL_CATALOG_OLLAMA_MODEL", "qwen2.5:3b"), "messages": [{"role": "user", "content": instruction}], "stream": False, "format": "json", "options": {"temperature": 0}}
        url = endpoint or os.environ.get("SKILL_CATALOG_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
        try:
            response = _http_json(url, payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama selector failed: {exc}") from exc
        return _parse_selection(response.get("message", {}).get("content", ""), entries, limit, backend)
    if backend == "llamacpp":
        payload = {"model": model or os.environ.get("SKILL_CATALOG_LLAMACPP_MODEL", "local-model"), "messages": [{"role": "user", "content": instruction}], "temperature": 0, "max_tokens": 256, "response_format": {"type": "json_object"}}
        url = endpoint or os.environ.get("SKILL_CATALOG_LLAMACPP_URL", "http://127.0.0.1:8080/v1/chat/completions")
        try:
            response = _http_json(url, payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"llama.cpp selector failed: {exc}") from exc
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_selection(content, entries, limit, backend)
    raise ValueError(f"Unsupported selector backend: {backend}")


def render_prompt(selected: list[dict[str, Any]], query: str) -> str:
    lines = ["Selected skills for this task:", f"Task: {query}", ""]
    lines.extend(f"- {item['name']}: {item['path']}" for item in selected)
    lines.extend(("", "Read the selected SKILL.md files before acting. Load referenced files only when needed.", "Do not load unrelated skills just because they are present in the catalog."))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Select Agent Skills without loading full instructions.")
    parser.add_argument("command", choices=("index", "search", "prompt"))
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--roots", help="Colon-separated skill roots")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--backend", choices=("local", "opencode", "ollama", "llamacpp"), default="local")
    parser.add_argument("--endpoint", help="Provider endpoint for ollama or llamacpp")
    parser.add_argument("--model", help="Provider model name")
    parser.add_argument("--output", default=".skill-catalog/index.json")
    parser.add_argument("--cache-dir")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    entries = catalog_for(repo, _roots(repo, args.roots), args.cache_dir, not args.no_cache)
    if args.command == "index":
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"version": 1, "skills": entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Indexed {len(entries)} skills into {args.output}")
        return 0
    selected = search(entries, args.query, args.limit) if args.backend == "local" else _remote_select(entries, args.query, args.limit, args.backend, args.endpoint, args.model)
    print(json.dumps(selected, indent=2, ensure_ascii=False) if args.command == "search" else render_prompt(selected, args.query))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
