# Skill Catalog Sorter

A provider-neutral, progressive-disclosure router for Agent Skills.

It keeps only a compact name/description index in the agent's visible context,
selects the most relevant skills for a task, and lets Codex, Claude, Hermes, or
OpenCode load the full `SKILL.md` files only after selection.

## Install

```bash
git clone <this-repository> ~/.local/share/skill-catalog
ln -sfn ~/.local/share/skill-catalog/skill-catalog ~/.codex/skills/skill-catalog
ln -sfn ~/.local/share/skill-catalog/skill-catalog ~/.claude/skills/skill-catalog
```

Then add the routing instruction from `global-instructions/` to your Codex and
Claude global instruction files.

## Use

```bash
~/.local/share/skill-catalog/bin/skill-catalog prompt "review this React dashboard"
~/.local/share/skill-catalog/bin/skill-catalog prompt "review this React dashboard" --backend opencode
```

## Communication model

The sorter uses progressive disclosure:

```text
agent task
    -> skill-catalog
    -> skill metadata: name, description, tags, path
    -> local ranker OR OpenCode selector
    -> validated skill names and absolute SKILL.md paths
    -> agent reads only those SKILL.md files
```

The default `local` backend makes no model call. It tokenizes the task and
scores skill names, descriptions, tags, and source paths locally.

With `--backend opencode`, the sorter runs:

```text
opencode run "<task + compact JSON catalog>" --format json
```

OpenCode receives the task plus compact metadata only, never the full skill
documents. It must return JSON in this shape:

```json
{"skills": ["frontend-quality-review", "web-security-hardening"]}
```

The sorter rejects unknown names and turns the accepted names into paths. The
agent then loads the selected `SKILL.md` files itself.

## Local model configuration

No model is required for the normal local backend. Configure its inputs with
CLI options or environment variables:

```bash
export SKILL_CATALOG_ROOTS="$HOME/.agents/skills:$HOME/.codex/skills"
skill-catalog prompt "review this web app" --backend local --limit 3
skill-catalog prompt "review this web app" --cache-dir "$HOME/.cache/my-sorter"
skill-catalog prompt "review this web app" --no-cache
```

Ollama and llama.cpp are natural local replacements for the OpenCode selector,
but they are not built-in backends yet. An adapter should receive the same
compact request and return the same JSON response, for example:

```json
{
  "task": "review this web app",
  "catalog": [
    {"name": "frontend-quality-review", "description": "...", "tags": []}
  ],
  "output": {"skills": ["name"]}
}
```

An Ollama adapter would POST the request to its local `/api/chat` endpoint; a
llama.cpp adapter would POST an equivalent prompt to its local
`/v1/chat/completions` endpoint. Neither adapter should receive or return full
`SKILL.md` contents. This keeps model traffic local while preserving the same
selector contract.

Catalogs are cached per project under `~/.cache/skill-catalog/`. The project
path is hashed into the cache directory. The cache stores metadata and a
manifest, not full skill instructions, and is invalidated when roots or any
discovered `SKILL.md` file changes.

## Profile manager

`bin/skill_profile.py` creates a reversible core-skill profile for Codex or
Claude. It stores the previous directory as a timestamped backup and uses
symlinks so one source collection can serve both agents.

## License

MIT
