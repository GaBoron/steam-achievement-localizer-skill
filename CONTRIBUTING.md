# Contributing Shared Achievement Translations

This repository accepts community-submitted Steam achievement schema files for the public translation library in `achievement-library/`.

## Before You Submit

Check whether the same Steam app ID is already present:

- Search `achievement-library/index.json` for the numeric Steam app ID.
- Search open pull requests for the same app ID or `UserGameStatsSchema_<game_id>.bin`.
- Search open issues with the `translation-submission` label for the same app ID.

Please do not submit a duplicate if the same game is already in the library, already in PR review, or already waiting in an open submission issue.

## Submission Rules

- Submit the real Steam schema file named `UserGameStatsSchema_<game_id>.bin`.
- The game ID in the issue, store URL, and file name must match.
- Select only languages that are fully present in the uploaded file.
- Every selected language must include both achievement name and description fields for every achievement.
- Keep the file as Steam Binary KeyValues. Do not convert it to JSON, CSV, or text before uploading.
- Do not upload files containing private account data, secrets, or unrelated local files.

## How Review Works

Open a `Share a translated achievement schema` issue and attach the `.bin` file. The GitHub Action will:

- download the uploaded file;
- verify that the store URL, game ID, and file name match;
- parse the file as Steam Binary KeyValues and require byte-identical roundtrip serialization;
- verify that the selected language fields are present for every achievement;
- check whether the game is already in the library or in another open submission;
- create a pull request after first review passes.

The generated pull request contains the updated library index, the submitted schema file, and a review table listing every achievement ID with each submitted language's achievement name and description. A maintainer still performs final review before merge.

## Library Layout

```text
achievement-library/
├── index.json
└── files/
    └── <game_id>/
        └── UserGameStatsSchema_<game_id>.bin
```

`index.json` is the user-facing lookup index. It records the game name, Steam app ID, store URL, supported languages, achievement count, schema file path, and file hash for each accepted submission.
