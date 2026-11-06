[简体中文](README.md) | English

# Steam Achievement Localizer Skill

Current version: `v1.1.0`

A skill for researching, translating, and verifying Steam achievements from a real `UserGameStatsSchema_*.bin` or a public App ID. Both routes produce standalone translation-library JSON. Real BIN projects also retain lossless BIN and standard ZIP output. Translation compares all acquired languages and uses achievement-specific online research and verified existing translations.

## Related Repository Responsibilities

- [Steam Achievement Translation Library](https://github.com/GaBoron/steam-achievement-translation-library) stores BIN and JSON-only translations and accepts submissions. Preparation checks its current catalog and downloads verified references when available.
- [SATLI](https://github.com/GaBoron/SATLI) handles BIN preview, installation, backup, and restore. [SATLI lite](https://github.com/GaBoron/SATLI-lite) 0.2.0+ can display standalone JSON translations.
- This repository handles multilingual research, translation drafts, validation, and output. Public data is never used to synthesize a BIN.

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

# No BIN or game ownership required: fetch public achievement text
python <skill>\scripts\steam_bkv_tool.py prepare `
  --app-id 123456 --target-language schinese `
  --source-languages english,japanese

# Produce final artifacts after research and translation are complete
python <skill>\scripts\steam_bkv_tool.py apply `
  --workspace "localization\123456-schinese"
```

Choose either `--schema` or `--app-id`. Public source languages default to `english`; `--source-languages` requests additional relevant languages and records those unavailable. Review every language acquired. `--variant-id` selects the library variant, defaulting to `default`. Use `prepare --offline` only with a real BIN when networking is unavailable or explicitly forbidden.

Public acquisition uses Steam’s structured achievement page without an API key. If no usable original data is accessible, preparation fails with a reason. Mismatched language ID sets, inconsistent fields, or conflicts with the selected library variant block formal export. Public records do not establish a game build or complete hidden-achievement/schema coverage.

## File Layout

Each game and target language uses one project directory:

```text
localization/123456-schinese/
├── input/
│   └── UserGameStatsSchema_123456.bin  # or public-achievements.json
├── work/
│   ├── manifest.json
│   ├── sources.json
│   ├── translations.csv
│   └── references/
└── final/
    ├── UserGameStatsSchema_123456.json
    ├── UserGameStatsSchema_123456.bin  # real BIN route only
    ├── UserGameStatsSchema_123456.zip  # real BIN route only
    └── report.json
```

- `input/` contains the real BIN copy or public-text snapshot with acquisition provenance.
- `work/` contains translation drafts, research provenance, and verified references.
- `final/` contains standalone JSON and the report; real BIN projects also include BIN and contribution ZIP.

Both routes export [format 2 JSON](https://github.com/GaBoron/steam-achievement-translation-library/blob/main/docs/translation-json.md), with stable API-name ordering, sorted languages, UTF-8/LF, and a final newline. It has exactly five top-level fields and no `source_sha256`. Real BIN integrity stays in the project report; public snapshot integrity is identified separately. Provenance and limitations stay in research/report files. Attach the JSON directly to the library’s JSON submission form and include sources in submission notes. JSON contains display text and cannot be installed as a BIN.

## Translation Requirements

`work/translations.csv` includes `<language>_name` and `<language>_description` columns for every acquired source language, including public data. Review and compare every one; never rely on English alone. When networking is available, online research is a high-weight translation input: search with the game title and exact achievement text or API ID, then check relevant characters, items, locations, quests, mechanics, story context, wordplay, and franchise terminology.

Use evidence in this order: official in-game localization and first-party developer/store material; a verified existing translation for the same game and achievement, including a matching translation-library schema; trusted wikis, guides, databases, and stable community usage; and finally cross-language schema wording and general linguistic inference. Existing translations are strong references, but verify the achievement ID, game version, source meaning, field structure, placeholders, and target-language terminology rather than copying them mechanically. Record every URL actually used in `work/sources.json` and state what context or wording it supported; explain conflicting-source decisions in `translation_notes`.

Match names and descriptions independently for each achievement. If an achievement's name is nonempty in any language, it must be nonempty in every language; the same rule applies separately to its description. When a field is empty in every language, leave it empty in the target language. A schema may therefore have nine achievements with both fields and one with only a name; the translation must preserve that per-achievement field pattern rather than fill every blank field.

`apply` verifies that:

- every acquired source language was reviewed through `consulted_schema_languages`;
- online sources were recorded when networking was available;
- achievement API IDs are complete with no extras;
- each achievement name and description is independently either nonempty in every language or empty in every language, with nonempty text kept single-line and control-character free;
- target placeholders match their source fields and JSON IDs, languages, structure, and limits are valid;
- real BIN projects change only target-language fields and preserve byte-identical source/output roundtrips; and
- the BIN route’s ZIP contains exactly one canonical root-level BIN.

The report identifies `BIN-derived` or `public-data-derived` and formal JSON eligibility. Eligibility means structural and source checks passed; translation quality and real client behavior still require review. Public projects make no BIN roundtrip or installation claim.

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
