# Contributing Shared Achievement Translations

[简体中文](CONTRIBUTING_CN.md)

This repository accepts community-submitted Steam achievement schema files for the public translation library in `achievement-library/`.

## Before You Submit

Check whether the same Steam app ID is already present:

- Search `achievement-library/README_EN.md` for the numeric Steam app ID or game name.
- Search open pull requests for the same app ID or `UserGameStatsSchema_<game_id>.bin`.
- Search open issues with the `translation-contribution` label for the same app ID.

Please do not submit a duplicate if the same game is already in the library, already in PR review, or already waiting in an open submission issue.

## Submission Rules

- Submit a ZIP named `UserGameStatsSchema_<game_id>.zip` because GitHub issues do not accept `.bin` attachments directly.
- The ZIP must contain exactly one real Steam schema file named `UserGameStatsSchema_<game_id>.bin`.
- The game ID in the issue, store URL, and file name must match.
- Select only languages that are fully present in the uploaded file.
- Every selected language must include both achievement name and description fields for every achievement.
- Keep the schema file as Steam Binary KeyValues. Do not convert it to JSON, CSV, or text before zipping.
- Do not upload files containing private account data, secrets, or unrelated local files.

## How Review Works

Open the English or Chinese translation contribution issue template and attach the `.zip` file. The GitHub Action will:

- download the uploaded file;
- verify that the store URL, game ID, ZIP name, and schema file name match;
- unpack the ZIP and require exactly one schema file inside it;
- parse the file as Steam Binary KeyValues and require byte-identical roundtrip serialization;
- verify that the selected language fields are present for every achievement;
- check whether the game is already in the library or in another open submission;
- create a pull request after first review passes;
- congratulate the contributor and close the issue after the review PR is ready.

The generated pull request contains the updated library index, the submitted schema file, and a review table listing every achievement ID with each submitted language's achievement name and description. A maintainer still performs final review before merge.

If the bot finds a ZIP name, schema file name, or schema file content problem, it leaves the issue open and explains what failed. Attach the corrected ZIP in a new comment and write:

```text
/update <attachment link>
```

The bot will rerun the file checks from that replacement ZIP link. If the problem is not file-fixable, such as a duplicate submission or mismatched Steam app metadata, the bot comments with the reason and closes the issue.

After a maintainer approves the generated review PR, the bot thanks the contributor, squashes and merges the PR, and deletes the contribution branch.

## Labels

- Translation library submissions use `translation-contribution`. Only this label is reviewed by the submission bot.
- Skill bug reports use `skill-bug`. These issues do not trigger translation-file review.

## Library Layout

```text
achievement-library/
├── README.md
├── README_EN.md
├── index.json
└── files/
    └── <game_id>/
        └── UserGameStatsSchema_<game_id>.bin
```

`achievement-library/README_EN.md` is the English user-facing lookup index. `achievement-library/README.md` is the Chinese default. Both are designed for GitHub browsing and browser search by game name, Steam app ID, or language code. `index.json` is the machine-readable index for scripts and automation.
