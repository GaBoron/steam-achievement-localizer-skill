---
name: steam-achievement-localizer
description: Research, translate, and verify Steam achievements from a real UserGameStatsSchema BIN or publicly accessible App ID. Compare all acquired languages, research achievement context online, consult verified community translations, and produce standalone translation-library JSON. Real BIN projects also retain lossless BIN and contribution ZIP output. Use when preparing, reviewing, applying, or packaging Steam achievement localization.
---

# Steam Achievement Localizer

Translate achievement display text with traceable context and stable API names. Use `scripts/steam_bkv_tool.py` for preparation, validation, and output; keep translation judgment and source evaluation with the agent.

## Choose the Source

- **Real BIN:** preserve the existing `prepare --schema` -> `apply` workflow. It produces a localized BIN, a ZIP containing that BIN, standalone format 2 JSON, and a report. Never replace the original file or install into Steam from this skill.
- **Public App ID:** use `prepare --app-id` without requiring ownership or installation. It reads Steam's structured public achievement page and produces JSON and a report only. Public data does not supply a complete client schema, stats, unlock state, or a verified game build. Never synthesize a BIN or claim BIN roundtrip/client compatibility.

Use [the translation library](https://github.com/GaBoron/steam-achievement-translation-library) for verified existing translations and submissions. Use [SATLI](https://github.com/GaBoron/SATLI) for BIN preview, installation, backup, and restoration; standalone JSON is display text for compatible clients such as [SATLI lite](https://github.com/GaBoron/SATLI-lite) 0.2.0+.

## Project Layout

Keep every task artifact in one project directory:

```text
localization/<app_id>-<target_language>/
|-- input/
|   `-- UserGameStatsSchema_<app_id>.bin  # real BIN route
|       OR public-achievements.json     # public source snapshot and provenance
|-- work/
|   |-- manifest.json
|   |-- sources.json
|   |-- translations.csv
|   `-- references/                     # verified library references, when available
`-- final/                             # deliverables after successful apply
    |-- UserGameStatsSchema_<app_id>.json
    |-- UserGameStatsSchema_<app_id>.bin # real BIN route only
    |-- UserGameStatsSchema_<app_id>.zip # real BIN route only
    `-- report.json
```

## Workflow

1. Establish the target Steam language and either a real schema path or App ID. Run `find-schema` only when the user asks to locate a local schema:

   ```powershell
   python <skill>/scripts/steam_bkv_tool.py find-schema --app-id 123456
   ```

2. Prepare one project using either command:

   ```powershell
   python <skill>/scripts/steam_bkv_tool.py prepare --schema "C:/path/UserGameStatsSchema_123456.bin" --target-language schinese
   python <skill>/scripts/steam_bkv_tool.py prepare --app-id 123456 --target-language schinese
   ```

   Both default to `localization/<app_id>-<language>`; use `--workspace` to choose a new empty directory and `--variant-id` for a library variant other than `default`. Real BIN preparation proves a byte-identical in-memory roundtrip and copies the source into `input/`.

   Public preparation defaults to English. Request other relevant accessible original languages with `--source-languages english,japanese`; discover relevant languages during research instead of assuming English is the only source. Review every language actually acquired. A failed language is recorded with its reason and is not a prerequisite for proceeding with usable source data. Missing or ambiguous App ID/language identity, API names, or public text cannot be invented. If no usable language is available, stop and explain the acquisition failure. Public lists do not prove that hidden/unavailable achievements are complete.

   Preparation queries the current translation-library catalog and verifies downloaded BIN or JSON-only references against catalog size and content integrity metadata. Reference fields appear in `library_*` CSV columns. Lookup failure is recorded; it does not establish that all network research is unavailable. `--offline` is only for real BIN projects when networking is unavailable or explicitly forbidden.

3. Read `work/manifest.json`, `work/sources.json`, and every source-language CSV column, including partial fields and library references. Compare terminology, tone, ambiguity, proper nouns, and omitted context across languages. Do not mechanically translate one language. Check the source kind, acquired/unavailable languages, public-data limitations, and submission blockers. Different public language ID sets, partial field coverage, or conflicts with the selected library variant block a formal public-data JSON export; obtain consistent source data and prepare a new project.

4. Research achievement-specific context online before settling wording. When network tools are available, online research is mandatory and carries substantial weight. Search the game title with exact achievement text or API name, then follow relevant characters, items, locations, quests, mechanics, story, wordplay, and franchise terms. Prefer:

   - official in-game localization, developer material, and first-party terminology;
   - verified existing translations for the same game/achievement, including matching library references;
   - trusted wikis, guides, databases, and consistent community usage;
   - cross-language source wording and general linguistic inference.

   Verify existing translations against current IDs, source meaning, field structure, placeholders, game/version evidence, and target-language terminology. Record every source actually used in `work/sources.json` with URL, kind, and a note explaining its contribution. Acquisition URLs alone need not resolve terminology or wordplay. Explain conflicting sources and significant wording choices in `translation_notes`. Mark network access unavailable only when network tools are absent or fail, with the reason in notes.

5. Set `consulted_schema_languages` to every acquired source language, including public-data languages; the existing key also applies to public projects. Fill `target_name` and `target_description` in `work/translations.csv`. Each achievement's name and description are checked independently: a field must be populated in every declared language or empty in all. Do not invent an unused description or copy the original into a new target language and call it translated. Existing target-language references are drafts requiring review. Preserve placeholders (including printf, Valve `%s1`, and `{name}`/`{0}` tokens), intentional punctuation, and stable API names. Keep target text single-line, without NUL, tabs, line breaks, or control characters.

6. Apply after research and translation are complete:

   ```powershell
   python <skill>/scripts/steam_bkv_tool.py apply --workspace "localization/123456-schinese"
   ```

   Both routes validate research, all acquired languages, exact achievement IDs, placeholders, independent name/description coverage, and source integrity before writing final translations. Public source conflicts produce a blocking report. Real BIN output additionally preserves non-target text, achievement count, and lossless source/output roundtrips.

7. Review `final/report.json` and deliverables. The standalone JSON follows the library's [format 2 contract](https://github.com/GaBoron/steam-achievement-translation-library/blob/main/docs/translation-json.md): exactly `version`, `app_id`, `variant_id`, sorted `languages`, and `achievements`, with UTF-8, LF, a final newline, and stable API-name sorting. It contains no `source_sha256`, provenance, or draft flags. Source notes stay in the report and research files and should accompany submission remarks. Only real BIN projects record source BIN hashes; public snapshot integrity uses a separate content field.

   A real BIN ZIP contains exactly one root-level `UserGameStatsSchema_<app_id>.bin`. BIN/ZIP and JSON target text must agree. Standalone JSON can be attached directly to the library's JSON submission form without a BIN/ZIP. Passing structural checks means the file is eligible for review; it does not prove translation accuracy, game-build alignment, or real Steam display behavior.

## Binary Safety

Preserve node order, repeated keys, numeric bytes, tokens, icons, hidden flags, stats, and every non-target-language field. Match by achievement API name, never row number or English text. Add/update only `display/name/<target_language>` and `display/desc/<target_language>` strings. Require byte-identical parse/serialize roundtrips for source and localized data, reject duplicate language nodes, and never overwrite the original source.

## Completion Report

Report source kind, source path or public URLs, project directory, acquired languages reviewed, online research and library match, achievement count, target coverage, submission eligibility/blockers, and final output paths. For real BINs confirm the original was untouched and roundtrips/ZIP validation passed. For public data state retrieval times and remaining limitations; make no BIN safety or installation claim. Distinguish structural validation from translation review and real client acceptance.
