# Promotion Checklist

The repository is ready for its first public release. GitHub account-level
actions still need to be completed once while signed in.

## Repository metadata

Rename the repository to `skill-catalog-sorter`, set this description:

> Local context router for AI coding agents. Select skills from compact metadata before loading full instructions.

Add these topics:

```text
agent-skills, ai-agents, llm, token-optimization, context-window,
ollama, llama-cpp, opencode, claude-code, openai-codex, developer-tools
```

Pin the repository on the GitHub profile. GitHub permits up to six pinned
repositories.

## Release

```bash
gh auth login
gh repo rename skill-catalog-sorter --repo Starryboyjosh/Dvadi --yes
git remote set-url origin git@github.com:Starryboyjosh/skill-catalog-sorter.git
gh repo edit Starryboyjosh/skill-catalog-sorter \
  --description "Local context router for AI coding agents" \
  --add-topic agent-skills --add-topic ai-agents --add-topic llm \
  --add-topic token-optimization --add-topic context-window \
  --add-topic ollama --add-topic llama-cpp --add-topic opencode \
  --add-topic claude-code --add-topic openai-codex --add-topic developer-tools
gh release create v0.1.0 --repo Starryboyjosh/skill-catalog-sorter \
  --title "Skill Catalog Sorter v0.1.0" --generate-notes
```

## Launch copy

> I built a local context router for AI coding agents. Skill Catalog Sorter
> scans compact skill metadata first, loads only the relevant `SKILL.md` files,
> caches catalogs per project, and supports local ranking, Ollama, llama.cpp,
> and OpenCode. The current benchmark shows 72.6% less startup metadata and
> 96% less average task context.
