---
name: steam-achievement-localizer
description: Research, translate, and verify Steam UserGameStatsSchema_*.bin achievement names and descriptions through lossless Binary KeyValues parsing, comparison of every language present in the source schema, high-priority online context research whenever network tools are available, prioritized verified existing translations such as GaBoron/steam-achievement-translation-library, and organized work/final artifacts compatible with the translation library and installer. Use when preparing, reviewing, applying, or packaging Steam achievement localization for any Steam language.
---

# Steam Achievement Localizer

Translate achievement text without corrupting Steam Binary KeyValues or treating English as the only source of meaning.

## Scope

Use `scripts/steam_bkv_tool.py` for deterministic schema parsing, project preparation, translation application, verification, packaging, and optional local schema discovery. Keep language judgment and source evaluation with the agent.

Do not replace the live Steam file. Produce a verified canonical BIN and ZIP, then direct ordinary installation and restoration work to [GaBoron/steam-achievement-translation-installer](https://github.com/GaBoron/steam-achievement-translation-installer). Use [GaBoron/steam-achievement-translation-library](https://github.com/GaBoron/steam-achievement-translation-library) as the shared translation-data source and submission target.

## Project Layout

Keep every task inside one project directory:

```text
localization/<app_id>-<target_language>/
|-- input/
|   `-- UserGameStatsSchema_<app_id>.bin
|-- work/
|   |-- manifest.json
|   |-- sources.json
|   |-- translations.csv
|   `-- references/                  # created only when a verified reference exists
`-- final/                           # created only after apply succeeds
    |-- UserGameStatsSchema_<app_id>.bin
    |-- UserGameStatsSchema_<app_id>.zip
    `-- report.json
```

Keep every task artifact inside this project.

## Workflow

1. Establish the schema path and target Steam language. Run `find-schema` only when the user asks to locate a local schema:

   ```powershell
   python <skill>\scripts\steam_bkv_tool.py find-schema --app-id 123456
   ```

2. Prepare one project. Omit `--workspace` to use `localization/<app_id>-<language>`. Use `--offline` only when network access is genuinely unavailable or the user explicitly forbids it:

   ```powershell
   python <skill>\scripts\steam_bkv_tool.py prepare --schema "C:\path\UserGameStatsSchema_123456.bin" --target-language schinese
   ```

   Preparation proves byte-identical roundtrip in memory, copies the source into `input/`, exports one editable `work/translations.csv`, creates the research manifest, and checks the connected translation library. When a matching primary schema exists, it is downloaded with size and SHA-256 verification under `work/references/translation-library/` and exposed in `library_*` CSV columns.

3. Read `work/manifest.json` and every language column in `work/translations.csv`. Compare every language present in the source schema, including partial fields. Never translate from English alone when other language fields exist. Treat differences between languages as evidence about terminology, tone, ambiguity, proper nouns, and omitted context; do not mechanically translate any one language. Schema wording is linguistic evidence, but reliable game-specific context and verified existing translations should outweigh an unsupported literal reading.

4. Research external context before settling the translation. When web, browser, connector, or other network access is available, online research is mandatory and carries substantial weight in the wording decision. Search by game title together with the exact achievement text or API ID, then follow relevant character, item, location, quest, mechanic, story, wordplay, and franchise terminology. Use evidence in this order:

   - official in-game localization, developer material, store pages, and other first-party terminology;
   - a verified existing translation for the same game and achievement, including a matching schema from the connected translation library;
   - trusted wikis, guides, databases, and consistent community usage;
   - cross-language schema wording and general linguistic inference.

   Treat a verified existing translation as a strong reference, especially when it matches the same achievement ID and game version, but check it against current source meaning, field structure, placeholders, and established target-language terminology instead of copying it blindly. When sources conflict, prefer the source closest to the game and achievement context and explain the choice in `translation_notes`. Record every source actually used in `work/sources.json` with its URL, kind, and a concise note stating what context or wording it supported. Set `network_access` to `unavailable` only after network tools are unavailable or fail; never use it merely to skip research.

5. Record every source-schema language actually reviewed in `consulted_schema_languages`. For each achievement, fill the target fields that the corresponding source achievement uses. Treat name and description independently: in the final schema, each field must be nonempty in every language or empty in every language. A row may therefore require both fields, only a name, only a description, or neither, and different rows may use different combinations. Do not add target text to a field that is empty in every other language. Use `translation_notes` for ambiguity, terminology choices, source conflicts, wordplay, proper nouns, or any decision materially guided by an existing translation or contextual source. Preserve placeholders and intentional punctuation. Keep nonempty text single-line and free of NUL, tabs, line breaks, and control characters. Correct invalid cells before applying the translation.

6. Apply only after the translation and research files are complete:

   ```powershell
   python <skill>\scripts\steam_bkv_tool.py apply --workspace "localization\123456-schinese"
   ```

   Application refuses missing or extra achievement IDs, field coverage that is inconsistent across languages for an achievement, unreviewed schema languages, absent online sources when network access is marked available, changed source hashes, duplicate language nodes, non-target-language modifications, failed roundtrips, or changed achievement counts.

7. Review `final/report.json` and the canonical outputs. The ZIP must contain exactly one root-level `UserGameStatsSchema_<app_id>.bin`, matching the translation-library contribution contract. The canonical BIN is suitable for preview or installation through the companion installer.

## Binary Safety Rules

- Preserve node order, repeated keys, numeric bytes, tokens, icons, hidden flags, stats, and every non-target language field.
- Match translations by stable achievement API ID, never by row number or English text.
- Add or update only `display/name/<target_language>` and `display/desc/<target_language>` string nodes.
- Require byte-identical parse/serialize roundtrips for both source and localized data.
- Never overwrite the original schema or install back into Steam from this skill.

## Completion Report

Report the source path and confirm it was not modified; project directory; source and localized SHA-256; roundtrip result; achievement count; source languages reviewed; online sources used or why network was unavailable; translation-library match; target-language coverage; and the three paths under `final/`.
