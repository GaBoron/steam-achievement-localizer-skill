---
name: steam-achievement-localizer
description: Localize Steam UserGameStatsSchema_*.bin achievement schema files by parsing Binary KeyValues losslessly, exporting achievement text, merging translations from a trusted source such as an already-open wiki page or user-provided CSV, writing only the requested Steam language field such as schinese/tchinese/japanese/koreana, and verifying byte-identical round trips. Use when translating Steam achievement names/descriptions, updating Steam achievement localization fields, or replacing an appcache stats schema with a localized copy.
---

# Steam Achievement Localizer

Use this skill to translate Steam achievement schema files such as `UserGameStatsSchema_123456.bin` without corrupting Steam Binary KeyValues.

## Core Rules

- Do not guess the binary format. Treat it as Steam Binary KeyValues with type bytes: `0` object/begin, `1` UTF-8 string, `2` int32, `3` float32, `4` pointer/uint32, `5` widestring unsupported, `6` color/uint32, `7` uint64, `8` end.
- Preserve node order and repeated keys. Do not represent child nodes as a plain dict for parsing or writing.
- Before translating, prove lossless parsing: parse original, serialize without changes, compare SHA-256 and bytes.
- Only create or update the target language string nodes under each achievement display `name` and `desc`. Do not modify `english`, tokens, icons, hidden flags, stats, or unrelated fields.
- Never overwrite the original Steam file until the localized copy has passed roundtrip verification and the user explicitly asks to install it.
- When installing back into Steam, back up the original file first and verify the installed file hash matches the localized copy.

## Script

Use `scripts/steam_bkv_tool.py` for deterministic parsing, exporting, applying translations, and verification.

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

## Workflow

1. **Inspect Git and file scope**
   - Follow the user's AGENTS.md Git rules before edits.
   - Treat Steam install/appcache paths as live external files. Work in the workspace first.

2. **Study references only when needed**
   - For Binary KeyValues details, prefer these implementations:
     - `CommitteeOfZero/achievement_reconstructor`: `lib/dumpers.py`, `reader.py`, `writer.py`, `types.py`
     - `PaulCombal/SamRewritten`: `src/backend/key_value.rs`
   - For achievement localization field heuristics, consult `PanVena/SteamAchievementLocalizer`, but do not copy its byte-search replacement approach for writing.

3. **Parse and export**
   - Run `steam_bkv_tool.py` on the real `.bin` file.
   - Confirm `roundtrip_equal: true` and matching original/roundtrip SHA-256 before touching translations.
   - Use the exported `*.achievements.csv` to inspect IDs, English names, and descriptions.

4. **Collect trusted translations**
   - Prefer a game wiki, official localization table, existing local game resource, or user-provided CSV.
   - If the user has already opened a protected wiki page in Chrome, use the Chrome control skill to claim that tab and extract table rows from the live DOM rather than using external web requests.
   - For wiki tables, export raw rows to JSON before merging. Keep columns such as ID, localized name, localized description text, unlock condition, and reward.

5. **Normalize wiki text**
   - Many wiki cells contain `Chinese + English original` in one cell. Strip the English duplicate before writing the target language.
   - Clean mixed wiki cells that append English tails, for example target-language text followed by You Unlocked "MAGDALENE", "THE BOOK OF REVELATIONS" has appeared in the basement, or "GOLDEN GOD" achieved.
   - Preserve target-language punctuation and quote marks. Do not strip them when removing ASCII quoted English text.
   - Do not consider "contains Chinese" sufficient. Check for remaining Latin words in the target fields unless the target language legitimately uses Latin text.

6. **Merge by achievement ID**
   - Match translation rows to schema rows by achievement ID/API name, not by row order or English name.
   - Require counts to match or report missing/extra IDs.
   - For each achievement, write target language name to `display/name/<language>` and target language description to `display/desc/<language>`.

7. **Verify localized copy**
   - Parse the localized copy and serialize it unchanged.
   - Require localized `roundtrip_equal: true`.
   - Confirm achievement count matches the source.
   - Confirm every achievement has the target language name and description.
   - For CJK targets such as `schinese`, check no Latin-word residue remains in target fields unless intentionally allowed.

8. **Install only on request**
   - If the user asks to put the file back, copy the original Steam file to a workspace/output backup first.
   - Copy the localized file to the original folder with the original filename.
   - Re-read the installed file, compare SHA-256 to the localized copy, and parse it once more.

## Chrome Extraction Pattern

When the user opens a wiki page in Chrome:

1. Load `chrome:control-chrome` and use the browser extension, not separate web requests.
2. Claim the matching tab from `browser.user.openTabs()`.
3. Inspect table headers and sample rows.
4. Extract rows with a single `tab.playwright.evaluate` call, for example returning `{id, nameCell, descriptionCell, unlockCondition, reward}`.
5. Save raw extracted rows to `outputs/wiki_achievements.json` or an equivalent artifact.
6. Merge into the translation CSV, then run the script to apply and verify.

## Completion Report

Report these facts at the end:

- Original file path and whether it was overwritten.
- Backup path if installed.
- Original SHA-256 and localized SHA-256.
- Roundtrip byte equality for original and localized copy.
- Achievement count and target-language coverage count.
- Missing IDs, extra IDs, or text residue counts.
- Paths to localized `.bin`, translation CSV, raw translation source export, and reports.
