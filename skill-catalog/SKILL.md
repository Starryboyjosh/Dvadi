---
name: skill-catalog
description: Select and load only the skills relevant to the current task.
version: 0.1.0
metadata:
  hermes:
    tags: [skills, routing, context, progressive-disclosure, opencode]
---

# Skill Catalog

Use the repository's compact skill catalog before loading specialized skills.

From any project directory, run:

```bash
skill-catalog prompt "<the user's task>"
```

Read only the selected `SKILL.md` files, then load referenced files only when
the selected skill requires them. The local selector is the default because it
is free, private, and fast. For ambiguous tasks, add `--backend opencode`;
OpenCode, Ollama, and llama.cpp receive compact metadata and must return a JSON
list of skill names. Configure local providers with `--endpoint` and `--model`
or their provider-specific environment variables.
