[简体中文](README.md) | English

# Steam Achievement Localizer Skill

Current version: `v1.1.0`

A Codex skill for researching, translating, and verifying Steam `UserGameStatsSchema_*.bin` achievement text. It parses Binary KeyValues losslessly, exposes every source-schema language in one translation sheet, prioritizes achievement-specific online context, references, and verified existing translations when networking is available, and changes only the selected target language.

## Related Repository Responsibilities

- [Steam Achievement Translation Library](https://github.com/GaBoron/steam-achievement-translation-library) stores community BIN files, the catalog, and contribution automation. Project preparation checks this catalog online and downloads a verified primary schema as a reference when available.
- [Steam Achievement Translation Installer](https://github.com/GaBoron/steam-achievement-translation-installer) handles scanning, preview, installation, backup, and restore; this skill produces its standard BIN/ZIP inputs.
- This repository owns multilingual context research, translation drafts, lossless writing, verification, and standard BIN/ZIP outputs compatible with both companion repositories.

## Install

Use `steam-achievement-localizer.zip` from the [Latest Release](https://github.com/GaBoron/steam-achievement-localizer-skill/releases/latest) as the installation source. An AI installer should download that asset and preserve the archive structure exactly:

```text
Install $steam-achievement-localizer from the latest GitHub Release asset at https://github.com/GaBoron/steam-achievement-localizer-skill/releases/latest. Use only the files contained in steam-achievement-localizer.zip and preserve its directory structure.
```

The Release asset contains:

```text
steam-achievement-localizer/
├── SKILL.md
├── VERSION
├── LICENSE
├── agents/
│   └── openai.yaml
└── scripts/
    ├── steam_bkv_tool.py
    └── steam_localizer/
        └── *.py
```

Invoke it with:

```text
Use $steam-achievement-localizer to translate this Steam achievement schema.
```

## Commands

Use these runtime commands:

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

## Translation Requirements

`work/translations.csv` includes `<language>_name` and `<language>_description` columns for every language present in the source schema. Review and compare every one; never rely on English alone. When networking is available, online research is a high-weight translation input: search with the game title and exact achievement text or API ID, then check relevant characters, items, locations, quests, mechanics, story context, wordplay, and franchise terminology.

Use evidence in this order: official in-game localization and first-party developer/store material; a verified existing translation for the same game and achievement, including a matching translation-library schema; trusted wikis, guides, databases, and stable community usage; and finally cross-language schema wording and general linguistic inference. Existing translations are strong references, but verify the achievement ID, game version, source meaning, field structure, placeholders, and target-language terminology rather than copying them mechanically. Record every URL actually used in `work/sources.json` and state what context or wording it supported; explain conflicting-source decisions in `translation_notes`.

Match names and descriptions independently for each achievement. If an achievement's name is nonempty in any language, it must be nonempty in every language; the same rule applies separately to its description. When a field is empty in every language, leave it empty in the target language. A schema may therefore have nine achievements with both fields and one with only a name; the translation must preserve that per-achievement field pattern rather than fill every blank field.

`apply` verifies that:

- every source-schema language was reviewed;
- online sources were recorded when networking was available;
- achievement API IDs are complete with no extras;
- each achievement name and description is independently either nonempty in every language or empty in every language, with nonempty text kept single-line and control-character free;
- only the target language changed;
- source and final data pass byte-identical roundtrips; and
- the final ZIP contains exactly one canonical root-level BIN.

## Development Checks

```powershell
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python C:\Users\<user>\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

## Support

For support, email [SATLI.support@proton.me](mailto:SATLI.support@proton.me).

## Acknowledgements

Binary KeyValues research references:

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)
