#!/usr/bin/env python3
"""Create a small, reversible global skill profile from the catalog."""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

CORE_SKILLS = (
    "skill-catalog", "graphify", "openai-docs", "skill-installer",
    "skill-supply-chain-audit", "opencode", "claude-code", "cavecrew",
    "systematic-debugging", "test-driven-development", "simplify-code",
    "app-security-review", "auth-access-control", "web-security-hardening",
    "frontend-quality-review", "html-app-production", "impeccable",
    "saas-product-ui", "dogfood", "computer-use",
)


def locate_skill(name: str, roots: list[Path]) -> Path | None:
    for root in roots:
        candidate = root / name
        if (candidate / "SKILL.md").is_file():
            return candidate
        if name == "skill-catalog" and (root / "SKILL.md").is_file() and root.name in {".skill-catalog", "skill-catalog"}:
            return root
    return None


def plan(source_roots: list[Path], target: Path) -> list[tuple[str, Path | None]]:
    return [(name, locate_skill(name, source_roots)) for name in CORE_SKILLS]


def print_plan(items: list[tuple[str, Path | None]], target: Path) -> None:
    print(f"Target: {target}")
    for name, source in items:
        status = str(source) if source else "MISSING"
        print(f"{name:28} <- {status}")
    print(f"\nSelected: {sum(source is not None for _, source in items)}/{len(items)}")


def apply_profile(items: list[tuple[str, Path | None]], target: Path) -> None:
    if target.exists() and not target.is_dir():
        raise RuntimeError(f"target exists but is not a directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    original_target = target
    backup = target.with_name(f"{target.name}.catalog-backup-{int(time.time())}")
    if target.exists():
        target.rename(backup)
        print(f"Backed up existing skills to {backup}")
    target.mkdir()
    for name, source in items:
        if source:
            # Sources inside the old profile moved with it. Remap them to the
            # backup so the new profile never contains broken symlinks.
            try:
                relative = source.relative_to(original_target)
            except ValueError:
                relative = None
            if relative is not None:
                source = backup / relative
            (target / name).symlink_to(source, target_is_directory=True)
    print(f"Installed {sum(source is not None for _, source in items)} core skills into {target}")
    print(f"Restore with: python3 tools/skill_profile.py restore --target {target} --backup {backup}")


def restore(target: Path, backup: Path) -> None:
    if not backup.is_dir():
        raise RuntimeError(f"backup directory not found: {backup}")
    if target.exists():
        shutil.rmtree(target)
    backup.rename(target)
    print(f"Restored {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage a small global Agent Skills profile.")
    parser.add_argument("command", choices=("plan", "apply", "restore"))
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--source-roots", type=Path, nargs="*", default=None)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    roots = args.source_roots or [
        repo / "skill-catalog",
        repo / ".agents" / "skills",
        Path.home() / ".agents" / "skills",
        Path.home() / ".codex" / "skills",
        Path.home() / ".codex" / "skills" / ".system",
        Path.home() / ".claude" / "skills",
    ]
    roots.extend(sorted(Path.home().glob(".codex/skills.catalog-backup-*")))
    roots.extend(sorted(Path.home().glob(".claude/skills.catalog-backup-*")))
    if args.command == "restore":
        if not args.backup:
            parser.error("restore requires --backup")
        restore(args.target.expanduser(), args.backup.expanduser())
        return 0
    items = plan(roots, args.target.expanduser())
    print_plan(items, args.target.expanduser())
    if args.command == "apply":
        apply_profile(items, args.target.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
