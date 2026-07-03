English | [简体中文](README_CN.md)

# Steam Achievement Localizer Skill

A Codex skill for translating Steam achievement names and descriptions in local
`UserGameStatsSchema_*.bin` files. It helps an AI assistant read the Steam
achievement schema, prepare translations, and write them back safely without
breaking the Binary KeyValues file structure.

You do not need to understand Steam's binary format to use it. In most cases,
you only need to provide the game ID, the schema file path, the target language,
and any translation preferences or reference material.

## Install

### Option 1: Ask Codex to install it

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

Then ask Codex to use it:

```text
Use $steam-achievement-localizer to translate this Steam achievement schema.
```

### Option 2: Install manually

Download `steam-achievement-localizer.zip` from GitHub Releases and extract it
to your Codex skills directory:

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

The installed path should look like:

```text
%USERPROFILE%\.codex\skills\steam-achievement-localizer\SKILL.md
```

## Version Check

The skill includes a local `VERSION` file. At the start of each run, ask Codex
to run the version preflight. It checks the local version every time, but reuses
a successful GitHub tag result for 24 hours by default:

```text
Use $steam-achievement-localizer and check the skill version first.
```

The underlying command is:

```powershell
python <skill>\scripts\steam_bkv_tool.py version-check --warn-only
```

Use `--force` when you want to refresh the GitHub tag check immediately.

If the versions do not match, update the skill from the latest GitHub Release
before localizing important files.

## How to Translate Achievements with This Skill

### 1. Find the Steam game ID

Open the Steam store page for the game you want to translate. The address usually
looks like this:

```text
https://store.steampowered.com/app/<game_id>/<game_name>/
```

For example, in a URL like `https://store.steampowered.com/app/123456/Game_Name/`,
the game ID is `123456`.

You can also tell the AI assistant the game name and ask it to look up the ID,
but checking the store URL yourself is safer because game names can be ambiguous.

### 2. Find the local achievement schema file

Steam normally stores local achievement schema files here on Windows:

```text
C:\Program Files (x86)\Steam\appcache\stats
```

If Steam is installed somewhere else, use this folder instead:

```text
<your Steam install folder>\appcache\stats
```

Inside that folder, find the file named:

```text
UserGameStatsSchema_<game_id>.bin
```

For example, if the game ID is `123456`, look for:

```text
UserGameStatsSchema_123456.bin
```

Codex can also automate this lookup:

```powershell
python <skill>\scripts\steam_bkv_tool.py find-schema --game-id 123456
```

To list every local Steam achievement schema file it can find:

```powershell
python <skill>\scripts\steam_bkv_tool.py find-schema
```

### 3. Give the file path and translation request to the AI assistant

You can paste the full file path and describe what you want. Example:

```text
Use $steam-achievement-localizer to translate this file into Simplified Chinese:
C:\Program Files (x86)\Steam\appcache\stats\UserGameStatsSchema_123456.bin

Please keep official item names unchanged, use natural achievement-style Chinese,
and make the descriptions concise.
```

You may also provide reference material, such as official translations, glossary
terms, wiki text, previous localization files, or a preferred tone/style.

### 4. Choose a workflow

You can ask the AI assistant to:

- translate and directly create a localized replacement file;
- first generate a CSV translation table for your review, then apply it after you
  confirm it is correct;
- use your own edited CSV as the final translation source.

For important files, the review-first CSV workflow is recommended.

The mechanical parts of this flow can be automated. For example, when you know
the game ID, Codex can search common Steam install locations, copy the live
schema into the output folder, export the CSV, export a missing-language CSV,
and run the safety checks:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

The generated `*.missing.csv` file contains only achievements missing the
requested target language. Ask Codex to batch-translate every row in that file,
filling `target_name` and `target_description`, then apply the reviewed CSV.

After reviewing or editing the CSV, Codex can apply it and create a verified
localized binary:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --strict-no-latin
```

Translation text should be plain single-line text. Do not include NUL bytes,
ASCII control characters, raw escape sequences, tabs, or line breaks. The script
sanitizes these before writing and reports how many fields were changed.

If you explicitly ask to install the result back into Steam, the workflow can
back up the original file first and then replace it:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --install
```

### 5. Replace the Steam file carefully

Before replacing anything, back up the original
`UserGameStatsSchema_<game_id>.bin` file. After the localized file is generated
and verified, you can replace the original file with the localized copy if that
is the workflow you requested.

## Useful Prompt Template

```text
Use $steam-achievement-localizer to translate Steam achievements.

Game ID: <game_id>
Schema file: <full path to UserGameStatsSchema_<game_id>.bin>
Target language: <schinese / tchinese / japanese / koreana / etc.>
Workflow: first export a CSV for review, then apply it after I confirm
Translation notes: <glossary, style, official names, references, or special rules>
```

## What the Skill Does Behind the Scenes

- Reads the Steam Binary KeyValues schema without changing unrelated data.
- Exports achievement names and descriptions for translation.
- Applies translations to the requested Steam language field, such as
  `schinese`, `tchinese`, `japanese`, or `koreana`.
- Verifies the file after writing so the localized schema can still be parsed.

## Acknowledgements

This project was developed with reference to the following open-source projects
and their research or implementations related to Steam achievement schemas,
Binary KeyValues, and localization workflows:

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
  Provided important reference material for parsing, rebuilding, and editing
  Steam `UserGameStatsSchema_*.bin` files.

- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
  Its Binary KeyValues parsing implementation helped confirm data type IDs,
  recursive structure handling, and string encoding behavior.

- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)
  Provided reference material for identifying multilingual Steam achievement
  fields, import/export behavior, and localization workflow design.

Thanks to the authors and contributors of these projects for researching Steam
data formats and sharing their work publicly. This project was completed as an
independent implementation built on existing community knowledge.

This project does not claim ownership of the code or research results of the
projects listed above. Copyrights and licenses for those projects belong to their
respective authors. Please follow each repository's license terms when using
those projects.

## License

MIT
