[简体中文](README.md) | English

# Steam Achievement Localizer Skill

Current version: `v0.1.2`

Steam Achievement Localizer is a Codex skill for localizing Steam achievement names and descriptions. It reads `UserGameStatsSchema_*.bin`, parses Steam Binary KeyValues losslessly, exports achievement text for review, and writes confirmed translations only to the selected language field.

This repository also maintains a community achievement translation library. Skill runtime scripts and repository maintenance scripts are separated: `scripts/` contains only the script shipped with the skill, while `workflow-scripts/` contains GitHub Actions helpers for submission review and library maintenance.

## Quick Links

- **Install the skill**: ask Codex to install from `https://github.com/GaBoron/steam-achievement-localizer-skill`, or download `steam-achievement-localizer.zip` from GitHub Releases.
- **Find existing translations**: open the [community achievement translation library](achievement-library/README_EN.md) and search by game name, Steam app ID, contributor, or language code.
- **Submit a translated file**: create a [translation contribution issue](https://github.com/GaBoron/steam-achievement-localizer-skill/issues/new?template=translation_contribution_en.yml) and upload `UserGameStatsSchema_<game_id>.zip`.
- **Report a skill bug**: create a [skill bug issue](https://github.com/GaBoron/steam-achievement-localizer-skill/issues/new?template=skill_bug_en.yml).

## Repository Layout

```text
.
├── SKILL.md
├── VERSION
├── scripts/
│   └── steam_bkv_tool.py
├── workflow-scripts/
│   ├── github_issue_guard.py
│   ├── library_submission_bot.py
│   └── translation_pr_maintenance.py
├── achievement-library/
│   ├── README.md
│   ├── README_EN.md
│   ├── index.json
│   └── files/
├── README.md
├── README_EN.md
├── CONTRIBUTING_CN.md
└── CONTRIBUTING.md
```

`scripts/steam_bkv_tool.py` is the only skill runtime entry point. It handles version checks, schema lookup, export, translation application, verification, and optional install-back. `workflow-scripts/` is for repository maintenance only: GitHub issue guarding, PR refreshes, index generation, and post-merge maintenance.

## Install

Ask Codex to install it:

```text
Install the skill from https://github.com/GaBoron/steam-achievement-localizer-skill
```

Then use it like this:

```text
Use $steam-achievement-localizer to translate this Steam achievement schema.
```

For manual installation, download `steam-achievement-localizer.zip` from GitHub Releases and extract it to your Codex skills folder:

```powershell
Expand-Archive .\steam-achievement-localizer.zip -DestinationPath "$env:USERPROFILE\.codex\skills" -Force
```

The installed skill directory should contain at least:

```text
steam-achievement-localizer\SKILL.md
steam-achievement-localizer\VERSION
steam-achievement-localizer\scripts\steam_bkv_tool.py
```

## Version Check

Before each localization task, the skill runs a cached version check. It reads the local `VERSION` every time and caches the latest GitHub tag lookup for up to 24 hours to avoid unnecessary network access.

```powershell
python <skill>\scripts\steam_bkv_tool.py version-check --warn-only
```

Use `--force` only after updating the skill, before risky install-back work, while diagnosing version problems, or when you need a fresh remote result immediately.

## Basic Workflow

### 1. Find the Steam app ID

Steam store URLs usually look like this:

```text
https://store.steampowered.com/app/<game_id>/<game_name>/
```

For example, the app ID in `https://store.steampowered.com/app/123456/Game_Name/` is `123456`.

### 2. Find the achievement schema

Steam usually stores achievement schemas at:

```text
<Steam folder>\appcache\stats\UserGameStatsSchema_<game_id>.bin
```

If you explicitly ask Codex to find the file, it can run:

```powershell
python <skill>\scripts\steam_bkv_tool.py find-schema --game-id 123456
```

Automatic lookup is optional. Apart from the version check, the skill should not run file discovery, batch translation, install-back, or full workflow automation unless you ask for it.

### 3. Ask for the translation

Recommended request format:

```text
Use $steam-achievement-localizer to translate this Steam achievement file.

Game ID: 123456
Schema file: <path to UserGameStatsSchema_123456.bin>
Target language: schinese
Workflow: export a CSV first, then apply it after I confirm
Translation notes: keep official item names unchanged and use short, natural Chinese
```

You can also provide glossaries, official localization text, wiki text, existing translation files, community library entries, or style notes. Codex should prefer sources that you provide or explicitly approve.

## Optional Automation

When you explicitly ask to automate the mechanical steps, use the full workflow:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs
```

This command runs the version check, searches for the schema, copies it to the output directory, exports an achievements CSV, exports a missing-language CSV, writes a report, and leaves the original Steam file untouched. `*.missing.csv` lists only achievements without the target language; fill `target_name` and `target_description` only when you ask for a batch translation of missing entries.

Apply a reviewed CSV:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --strict-no-latin
```

Translation text should be clean and single-line, with no tabs, line breaks, raw escape sequences, NUL bytes, or control characters. The script sanitizes unsafe characters before writing and reports `translation_text_sanitized_count`.

Install back into Steam only after you explicitly confirm that the local Steam file should be replaced:

```powershell
python <skill>\scripts\steam_bkv_tool.py workflow --game-id 123456 --target-language schinese --out-dir outputs --translations outputs\translations.csv --install
```

The install flow backs up the original file first, then verifies that the installed file hash matches the localized copy.

## What the Skill Checks

- The original file can be parsed and written back byte-identically.
- The localized copy can also be parsed and written back byte-identically.
- Translations are matched by stable achievement ID, not by row number or English text.
- The target language covers every achievement name and description.
- Missing, extra, empty, or suspicious source-language residue is reported.
- Unsafe characters are sanitized before writing.

## Community Translation Library

The community translation library lives in `achievement-library/`. It contains GitHub-readable indexes, a machine-readable index, and user-submitted schema files. To contribute a translated schema, use the translation contribution issue template and upload a ZIP that contains exactly one `UserGameStatsSchema_<game_id>.bin` file.

The submission bot checks issue fields, Steam store metadata, file names, ZIP structure, Steam Binary KeyValues roundtrip, selected language coverage, and duplicate submissions. After first review passes, the bot opens a PR; after maintainer review and merge, the repository updates `achievement-library/index.json` and both Markdown indexes.

Submission rules and maintainer commands are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgements

This project was built with public references from:

- [achievement_reconstructor](https://github.com/CommitteeOfZero/achievement_reconstructor)
- [SamRewritten](https://github.com/PaulCombal/SamRewritten)
- [SteamAchievementLocalizer](https://github.com/PanVena/SteamAchievementLocalizer)

Thanks to the authors and contributors of those projects for sharing research about Steam achievement files and localization workflows. This project is an independent implementation; please follow each referenced project's license terms when using their work.

## License

MIT
