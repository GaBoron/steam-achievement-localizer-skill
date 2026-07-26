[简体中文](README.md) | English

# Steam Achievement Localizer Skill

Current version: `v0.1.2`

A Codex skill for researching, translating, and verifying Steam `UserGameStatsSchema_*.bin` achievement text. It parses Binary KeyValues losslessly, exposes every source-schema language in one translation sheet, requires online research when networking is available, and changes only the selected target language.

## Related Repository Responsibilities

- [Steam Achievement Translation Library](https://github.com/GaBoron/steam-achievement-translation-library) stores community BIN files, the catalog, and contribution automation. Project preparation checks this catalog online and downloads a verified primary schema as a reference when available.
- [Steam Achievement Translation Installer](https://github.com/GaBoron/steam-achievement-translation-installer) handles scanning, preview, installation, backup, and restore. This skill no longer replaces live Steam files.
- This repository owns multilingual context research, translation drafts, lossless writing, verification, and standard BIN/ZIP outputs compatible with both companion repositories.

## Install

Ask Codex to install the repository:

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

Invoke it with:

```text
Use $steam-achievement-localizer to translate this Steam achievement schema.
```

Keep `SKILL.md`, `VERSION`, `agents/`, and the complete `scripts/` directory together in the installed skill.

## Reduced Command Surface

Only three runtime actions remain:

```powershell
# Optional: locate a local schema
python <skill>\scripts\steam_bkv_tool.py find-schema --app-id 123456

# Create one organized translation project and query the library by default
python <skill>\scripts\steam_bkv_tool.py prepare `
  --schema "C:\path\UserGameStatsSchema_123456.bin" `
  --target-language schinese

# Produce final artifacts after research and translation are complete
python <skill>\scripts\steam_bkv_tool.py apply `
  --workspace "localization\123456-schinese"
```

Use `prepare --offline` only when networking is genuinely unavailable or the user explicitly forbids it.

## File Layout

Each game and target language uses one project directory:

```text
localization/123456-schinese/
├── input/
│   └── UserGameStatsSchema_123456.bin
├── work/
│   ├── manifest.json
│   ├── sources.json
│   ├── translations.csv
│   └── references/
└── final/
    ├── UserGameStatsSchema_123456.bin
    ├── UserGameStatsSchema_123456.zip
    └── report.json
```

- `input/` contains only the source copy used by the project.
- `work/` contains translation drafts, research provenance, and verified references.
- `final/` contains only the deliverable BIN, contribution ZIP, and final report.

The workflow no longer emits roundtrip BIN files, full-tree JSON dumps, duplicate CSV exports, version caches, or installation backups by default.

## Translation Requirements

`work/translations.csv` includes `<language>_name` and `<language>_description` columns for every language present in the source schema. Review and compare every one; never rely on English alone. When networking is available, research official localization, developer material, Steam pages, reliable wikis, or useful community references, then record the URLs actually used in `work/sources.json`.

`apply` verifies that:

- every source-schema language was reviewed;
- online sources were recorded when networking was available;
- achievement API IDs are complete with no extras;
- every target name and description is complete, single-line, and control-character free;
- only the target language changed;
- source and final data pass byte-identical roundtrips; and
- the final ZIP contains exactly one canonical root-level BIN.

## Development Checks

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python C:\Users\<user>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

## Acknowledgements

Binary KeyValues research references:

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)
