#!/usr/bin/env python3
"""Validate every skill in the repo. Run from anywhere; exits non-zero on failure.

Checks, per skill under plugins/*/skills/*:
  - SKILL.md exists with YAML frontmatter containing `name` and `description`
  - `name` matches the skill directory, is lowercase-hyphen, and fits the
    64-char limit; `description` fits the 1024-char limit
  - every references/..., assets/... and scripts/... path mentioned in the
    skill's Markdown files exists on disk
  - assets|scripts/*.py parse (syntax check), assets|scripts/*.sh pass
    `bash -n`, assets|scripts/*.json parse

Repo-level: marketplace.json and plugin.json parse, and every plugin
`source` in the marketplace catalog exists.
"""

import json
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH_RE = re.compile(r"\b((?:references|assets|scripts)/[\w./-]+\w)")

errors = []


def err(msg):
    errors.append(msg)
    print(f"FAIL: {msg}")


def check_manifests():
    marketplace = ROOT / ".claude-plugin" / "marketplace.json"
    try:
        catalog = json.loads(marketplace.read_text())
    except (OSError, ValueError) as e:
        err(f"{marketplace.relative_to(ROOT)}: {e}")
        return
    for plugin in catalog.get("plugins", []):
        source = ROOT / plugin.get("source", "")
        if not source.is_dir():
            err(f"marketplace.json: plugin source {plugin.get('source')} missing")
            continue
        manifest = source / ".claude-plugin" / "plugin.json"
        try:
            json.loads(manifest.read_text())
        except (OSError, ValueError) as e:
            err(f"{manifest.relative_to(ROOT)}: {e}")


def frontmatter(skill_md):
    text = skill_md.read_text()
    m = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        raise ValueError("no YAML frontmatter block")
    data = yaml.safe_load(m.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def check_skill(skill_dir):
    rel = skill_dir.relative_to(ROOT)
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        err(f"{rel}: SKILL.md missing")
        return

    try:
        meta = frontmatter(skill_md)
    except ValueError as e:
        err(f"{rel}/SKILL.md: {e}")
        meta = {}
    name, description = meta.get("name"), meta.get("description")
    if not name:
        err(f"{rel}/SKILL.md: frontmatter missing `name`")
    elif name != skill_dir.name:
        err(f"{rel}/SKILL.md: name {name!r} != directory {skill_dir.name!r}")
    elif not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        err(f"{rel}/SKILL.md: name {name!r} not lowercase-hyphen or over 64 chars")
    if not description:
        err(f"{rel}/SKILL.md: frontmatter missing `description`")
    elif len(description) > 1024:
        err(f"{rel}/SKILL.md: description is {len(description)} chars (limit 1024)")

    for md in [skill_md, *sorted(skill_dir.glob("references/*.md"))]:
        for path in PATH_RE.findall(md.read_text()):
            if not (skill_dir / path).is_file() and not (md.parent / path).is_file():
                err(f"{md.relative_to(ROOT)}: references missing file {path}")

    for asset in sorted([*skill_dir.glob("assets/*"), *skill_dir.glob("scripts/*")]):
        arel = asset.relative_to(ROOT)
        if asset.suffix == ".py":
            try:
                compile(asset.read_text(), str(asset), "exec")
            except SyntaxError as e:
                err(f"{arel}: {e}")
        elif asset.suffix == ".sh":
            run = subprocess.run(
                ["bash", "-n", str(asset)], capture_output=True, text=True
            )
            if run.returncode != 0:
                err(f"{arel}: bash -n failed: {run.stderr.strip()}")
        elif asset.suffix == ".json":
            try:
                json.loads(asset.read_text())
            except ValueError as e:
                err(f"{arel}: invalid JSON: {e}")


def main():
    check_manifests()
    skills = sorted(ROOT.glob("plugins/*/skills/*/"))
    if not skills:
        err("no skills found under plugins/*/skills/")
    for skill_dir in skills:
        check_skill(skill_dir)
        print(f"checked {skill_dir.relative_to(ROOT)}")
    if errors:
        print(f"\n{len(errors)} error(s)")
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
