# Contributing to Steam Achievement Localizer Skill

[简体中文](CONTRIBUTING.md) | English

This repository maintains the Codex skill, local runtime script, and installation documentation. 

## What Belongs Here

- Usage flow, constraints, or version-check rules in `SKILL.md`.
- Binary KeyValues parsing, export, write, verification, lookup, or install-back logic in `scripts/steam_bkv_tool.py`.
- README text, installation docs, release packaging notes, or skill bug templates.
- Test fixtures or regression cases that do not contain concrete game translation data.

## Development Checks

After changing scripts, run at least the quick check:

```powershell
python scripts/steam_bkv_tool.py version-check --warn-only
```

If a change affects parsing, export, or writing, verify roundtrip behavior on a copied real or test schema and confirm the original Steam file is not overwritten.

## Safety Boundaries

- By default, work only on user-provided schema copies or files in an output directory.
- Do not write back to Steam `appcache/stats` without explicit confirmation.
- Do not commit secrets, tokens, personal paths, Steam account data, or private local configuration.
