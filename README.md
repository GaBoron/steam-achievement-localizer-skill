English | [简体中文](README_CN.md)

# Steam Achievement Localizer Skill

Current version: `v0.1.2`

This is a Codex skill for translating Steam achievement names and descriptions in
local `UserGameStatsSchema_*.bin` files.

You only need to provide the game ID or schema file path, the target language,
and your translation preferences. The skill reads the file, exports achievement
text for review, writes the selected language back, and checks the result before
you replace anything in Steam.

## Install

### Ask Codex to install it

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

Then ask Codex to use it:

```text
Use $steam-achievement-localizer to translate this Steam achievement schema.
```

### Install manually

Download `steam-achievement-localizer.zip` from GitHub Releases and extract it
to your Codex skills folder:

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

The installed folder should contain:

```text
steam-achievement-localizer\SKILL.md
```

## Version Check

The skill checks its local version before work starts. It also checks the latest
GitHub tag, but caches that result for 24 hours so it does not contact GitHub on
every run.

```powershell
python <skill>\scripts\steam_bkv_tool.py version-check --warn-only
```

Use `--force` only when you want a fresh GitHub check immediately.

If the versions do not match, update the skill before editing important files.

## Basic Use

### 1. Find the Steam game ID

Open the Steam store page for the game. The URL usually looks like this:

```text
https://store.steampowered.com/app/<game_id>/<game_name>/
```

In this example, the game ID is `123456`:

```text
https://store.steampowered.com/app/123456/Game_Name/
```

### 2. Find the achievement file

Steam usually stores these files in:

```text
<Steam folder>\appcache\stats
```

The file name is:

```text
UserGameStatsSchema_<game_id>.bin
```

For game ID `123456`, the file is:

```text
UserGameStatsSchema_123456.bin
```

If you ask Codex to find the file for you, it can run:

```powershell
python <skill>\scripts\steam_bkv_tool.py find-schema --game-id 123456
```

This lookup is optional. Codex should use it only when you ask for automatic
file lookup.

### 3. Ask for the translation

Example:

```text
Use $steam-achievement-localizer to translate this Steam achievement file.

Game ID: 123456
Schema file: <path to UserGameStatsSchema_123456.bin>
Target language: schinese
Workflow: export a CSV first, then apply it after I confirm
Translation notes: keep official item names unchanged and use short, natural Chinese
```

You can also provide a glossary, official translation text, wiki text, previous
translation files, or style notes.

## Workflow Choices

You can ask Codex to:

- export a CSV for review first;
- apply your edited CSV and create a translated copy;
- translate only achievements that are missing the target language;
- automate file lookup and CSV export;
- install the translated file back into Steam after you explicitly confirm.

Only the version check runs by default. Other automation runs only when you ask
for it.

### Optional automated export

When you explicitly ask for automation, Codex can search for the schema file,
copy it to an output folder, export a CSV, export a missing-language CSV, and
run safety checks:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

The `*.missing.csv` file lists achievements that do not yet have the requested
language. If you ask Codex to batch-translate missing entries, it can fill
`target_name` and `target_description` for each row.

### Apply a reviewed CSV

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --strict-no-latin
```

Keep translation text plain and single-line. Avoid tabs, line breaks, raw escape
sequences, NUL bytes, and control characters. The script removes unsafe
characters before writing and reports how many fields were changed.

### Install back into Steam

Only do this when you are ready to replace the local Steam file:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --install
```

The workflow backs up the original file first and then checks that the installed
file matches the translated copy.

## What the Skill Checks

- The original file can be read and written back without changing its bytes.
- The translated copy can also be read and written back safely.
- Achievement IDs are matched by stable IDs, not by row order.
- Missing, extra, or empty translation rows are reported.
- Unsafe characters in translation text are removed before writing.

## Acknowledgements

This project was built with public references from:

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)

Thanks to the authors and contributors of those projects for sharing research
about Steam achievement files and localization workflows.

This project is an independent implementation. Please follow each referenced
project's license terms when using their work.

## License

MIT
