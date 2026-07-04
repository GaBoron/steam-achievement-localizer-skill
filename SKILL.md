---
name: steam-achievement-localizer
description: Localize Steam UserGameStatsSchema_*.bin achievement schema files by parsing Binary KeyValues losslessly, exporting achievement text, preparing or merging translations from user-provided CSVs, official localization, glossaries, community references, or AI-assisted translation, writing only the requested Steam language field such as schinese/tchinese/japanese/koreana, and verifying byte-identical round trips. Use when translating Steam achievement names/descriptions, updating Steam achievement localization fields, or preparing a verified localized replacement for a Steam appcache stats schema.
---

# Steam Achievement Localizer

Use this skill to translate Steam achievement schema files such as `UserGameStatsSchema_123456.bin` without corrupting Steam Binary KeyValues.

## Version Preflight

Before every localization task, run the version preflight, but use its cache so repeated skill calls do not waste time:

```bash
python <skill>/scripts/steam_bkv_tool.py version-check --warn-only
```

The default cache window is 24 hours. It still reads the local `VERSION` every time, but reuses a recent successful GitHub tag result unless the cache is stale. Use `--force` before risky installs, after an update, when diagnosing version-related bugs, or when the user explicitly asks for a fresh check.

Report the local version, latest GitHub tag, whether the result came from cache, and whether they match. If the versions do not match, tell the user before continuing and prefer updating the skill unless the user asks to proceed with the local copy.

## Core Rules

- Do not guess the binary format. Treat it as Steam Binary KeyValues with type bytes: `0` object/begin, `1` UTF-8 string, `2` int32, `3` float32, `4` pointer/uint32, `5` widestring unsupported, `6` color/uint32, `7` uint64, `8` end.
- Preserve node order and repeated keys. Do not represent child nodes as a plain dict for parsing or writing.
- Before translating, prove lossless parsing: parse original, serialize without changes, compare SHA-256 and bytes.
- Only create or update the target language string nodes under each achievement display `name` and `desc`. Do not modify `english`, tokens, icons, hidden flags, stats, or unrelated fields.
- Never overwrite the original Steam file until the localized copy has passed roundtrip verification and the user explicitly asks to install it.
- When installing back into Steam, back up the original file first and verify the installed file hash matches the localized copy.

## Script

Use `scripts/steam_bkv_tool.py` for deterministic parsing, exporting, applying translations, version checks, and verification.

Do not run optional automation such as Steam install discovery, schema lookup, batch missing-language translation, direct localized output, or install-back unless the user explicitly asks for that automation. Version preflight is the only automation to run by default.

Optional schema lookup when the user asks Codex to find the local file:

```bash
python <skill>/scripts/steam_bkv_tool.py find-schema --game-id 123456
```

Optional local schema inventory when the user asks Codex to list available schema files:

```bash
python <skill>/scripts/steam_bkv_tool.py find-schema
```

Optional automated workflow when the user asks Codex to automate the mechanical steps:

```bash
python <skill>/scripts/steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

This runs the cached skill version preflight, searches common Steam install locations for `UserGameStatsSchema_123456.bin`, copies the live file into the output directory, exports the CSV, exports `*.missing.csv` for achievements missing the target language, writes a report, and leaves the original Steam file untouched. Use it only after the user asks for this level of automation.

Apply a reviewed translation CSV:

```bash
python <skill>/scripts/steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs/translations.csv --strict-no-latin
```

Install the verified localized copy only when the user explicitly asks:

```bash
python <skill>/scripts/steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs/translations.csv --install
```

Basic export and roundtrip check:

```bash
python <skill>/scripts/steam_bkv_tool.py "C:/path/UserGameStatsSchema_123.bin" --out-dir outputs --target-language schinese
```

Apply translations and create a localized copy:

```bash
python <skill>/scripts/steam_bkv_tool.py "C:/path/UserGameStatsSchema_123.bin" --out-dir outputs --target-language schinese --translations outputs/translations.csv --localized-bin outputs/UserGameStatsSchema_123.schinese.bin --strict-no-latin
```

Verify an already localized copy:

```bash
python <skill>/scripts/steam_bkv_tool.py outputs/UserGameStatsSchema_123.schinese.bin --out-dir outputs/verify --target-language schinese
```

Translation CSV accepted columns:

- ID: `api_name`, `id`, `achievement_id`, or `name`
- Name: `<language>_name`, `target_name`, `translated_name`, `name_zh`, or `schinese_name`
- Description: `<language>_description`, `target_description`, `translated_description`, `description_zh`, or `schinese_description`

The generated `*.missing.csv` file uses `target_name` and `target_description` columns. Batch-fill every row in that file only when the user asks to translate all achievements missing the requested language at once.

## Workflow

1. **Establish file scope**
   - Start with the cached version preflight. If using `workflow`, keep its built-in version check enabled unless the user explicitly accepts skipping it.
   - Use `find-schema --game-id <id>` or `workflow --game-id <id>` only if the user asks Codex to locate files or automate the mechanical workflow. Otherwise, work from the game ID, schema path, target language, and workflow choices the user provides.
   - Identify the source `.bin`, target Steam language code, output directory, and whether the user wants review-first CSV output or direct localized binary output.
   - Treat Steam install/appcache paths as live external files. Work on copies in a workspace or output directory first.
   - If the source file is inside a Git repository, protect unrelated user changes and manage only artifacts created for the localization task.

2. **Consult format references only when needed**
   - For Binary KeyValues details, prefer these implementations:
     - `CommitteeOfZero/achievement_reconstructor`: `lib/dumpers.py`, `reader.py`, `writer.py`, `types.py`
     - `PaulCombal/SamRewritten`: `src/backend/key_value.rs`
   - For achievement localization field heuristics, consult `PanVena/SteamAchievementLocalizer`, but do not copy its byte-search replacement approach for writing.

3. **Parse and export**
   - Use the lower-level export command when the schema file is already scoped. Use `steam_bkv_tool.py workflow` only when the user requests automated lookup/copy/export behavior.
   - Confirm `roundtrip_equal: true` and matching original/roundtrip SHA-256 before touching translations.
   - Use the exported `*.achievements.csv` to inspect IDs, English names, and descriptions.

4. **Collect trusted translations**
   - For batch missing-language work, use the generated `*.missing.csv`, translate every row that lacks the target language, and write the result to a CSV accepted by the script only when the user asks for batch translation.
   - Prefer user-provided CSVs, official localization resources, existing local game files, developer-provided text, community-maintained references, or a user-approved AI translation pass.
   - If the repository checkout includes `achievement-library/index.json`, use it as an optional community translation reference when the user asks to search or reuse shared submissions.
   - Preserve source provenance in a note, intermediate file, or report when translations come from external references.
   - If translating from scratch, follow the user's glossary, tone, title-casing, item-name, character-name, and terminology preferences.

5. **Normalize target text**
   - Keep one clean target-language name and description per achievement.
   - Keep translated text plain and single-line. Do not include NUL bytes, ASCII control characters, raw escape sequences, tabs, or line breaks. The script sanitizes these before writing and reports `translation_text_sanitized_count`; investigate any nonzero count.
   - Remove duplicated source-language text only when it is clearly appended or repeated beside the target translation.
   - Preserve intentional names, acronyms, numbers, placeholders, punctuation, and quotation marks.
   - Flag mixed-language residue for review unless the target language normally uses that text or the user requested it.

6. **Merge by stable achievement ID**
   - Match translation rows to schema rows by achievement ID/API name, not by row order or English name.
   - Require counts to match or report missing/extra IDs.
   - For each achievement, write target language name to `display/name/<language>` and target language description to `display/desc/<language>`.

7. **Verify localized copy**
   - Parse the localized copy and serialize it unchanged.
   - Require localized `roundtrip_equal: true`.
   - Confirm achievement count matches the source.
   - Confirm every achievement has the target language name and description.
   - Check for suspicious source-language residue, empty target fields, missing IDs, and unexpected extra IDs.

8. **Install only on request**
   - Use `workflow --install` only if the user asks to put the file back.
   - Confirm the report shows a backup path and `installed_matches_localized: true`.
   - Re-read or verify the installed file if the user needs an extra installation check.

## Completion Report

Report these facts at the end:

- Original file path and whether it was overwritten.
- Version preflight result: local version, latest GitHub tag, cache status, and whether they match.
- Backup path if installed.
- Original SHA-256 and localized SHA-256.
- Roundtrip byte equality for original and localized copy.
- Achievement count and target-language coverage count.
- Missing IDs, extra IDs, empty target fields, or text residue counts.
- Missing-language CSV path and translation text sanitization count.
- Paths to localized `.bin`, translation CSV, translation source notes or exports, and reports.
