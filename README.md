English | [简体中文](README_CN.md)

# Steam Achievement Localizer Skill

A Codex skill for safely localizing Steam achievement schema files
(`UserGameStatsSchema_*.bin`) without corrupting Steam Binary KeyValues.

This project is useful when a Steam game has English achievement names and
descriptions in the local appcache schema and you want to add a Steam language
field such as `schinese`, `tchinese`, `japanese`, or `koreana`.

## What It Does

- Parses Steam Binary KeyValues with ordered nodes and repeated keys preserved.
- Verifies byte-identical parse/serialize round trips before making changes.
- Exports the achievement tree to JSON and achievement text to CSV.
- Applies a translation CSV by achievement ID/API name.
- Writes only the requested language nodes under achievement `display/name` and
  `display/desc`.
- Verifies the localized file by parsing and serializing it again.

The skill is designed to avoid unsafe global byte replacement. Unmodified files
must round-trip byte-for-byte.

## Install

### Option 1: Release zip

Download `steam-achievement-localizer.zip` from GitHub Releases and extract it
directly into your Codex skills directory:

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

After extraction, the installed path should look like:

```text
%USERPROFILE%\.codex\skills\steam-achievement-localizer\SKILL.md
```

### Option 2: Copy from the repository

Clone this repository and copy it into your Codex skills directory:

```powershell
git clone https://github.com/GaBoron/steam-achievement-localizer-skill.git
Copy-Item -Recurse steam-achievement-localizer-skill `
  "$env:USERPROFILE\.codex\skills\steam-achievement-localizer"
```

### Option 3: Codex prompt install

Ask Codex:

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

Then ask Codex to use:

```text
Use $steam-achievement-localizer to translate this Steam achievement schema.
```

## Script Usage

Export and verify an original schema:

```bash
python scripts/steam_bkv_tool.py "C:/path/UserGameStatsSchema_123.bin" --out-dir outputs --target-language schinese
```

Apply translations:

```bash
python scripts/steam_bkv_tool.py "C:/path/UserGameStatsSchema_123.bin" \
  --out-dir outputs \
  --target-language schinese \
  --translations outputs/translations.csv \
  --localized-bin outputs/UserGameStatsSchema_123.schinese.bin \
  --strict-no-latin
```

Verify a localized copy:

```bash
python scripts/steam_bkv_tool.py outputs/UserGameStatsSchema_123.schinese.bin --out-dir outputs/verify --target-language schinese
```

## Translation CSV

Accepted ID columns:

- `api_name`
- `id`
- `achievement_id`
- `name`

Accepted translated name columns:

- `<language>_name`
- `target_name`
- `translated_name`
- `name_zh`
- `schinese_name`

Accepted translated description columns:

- `<language>_description`
- `target_description`
- `translated_description`
- `description_zh`
- `schinese_description`

Example:

```csv
api_name,schinese_name,schinese_description
ACH_WIN_ONE_GAME,赢下一局,赢得一整局游戏
ACH_COLLECT_100,收藏家,收集100个物品
```

## Safety Notes

- Back up the original Steam file before replacing it.
- Do not edit the Steam file in place until a localized copy passes verification.
- Use a trusted translation source such as an official localization table, game
  wiki, or reviewed CSV.
- For CJK targets, `--strict-no-latin` helps catch leftover English text.

## Repository Contents

- `SKILL.md`: Codex skill instructions.
- `scripts/steam_bkv_tool.py`: Binary KeyValues parser, exporter, writer, and
  localization tool.
- `README_CN.md`: Chinese documentation.

## License

MIT
