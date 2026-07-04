# Contributing Shared Achievement Translations

English | [简体中文](CONTRIBUTING_CN.md)

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
- add the `translation-contribution` label if GitHub did not apply it, then freeze the issue title and body so submitted fields cannot be changed afterward;
- create a pull request after first review passes;
- congratulate the contributor and close the issue after the review PR is ready.

The generated pull request contains only the submitted schema file plus a review table listing every achievement ID with each submitted language's achievement name and description. After the pull request is merged, the bot updates `achievement-library/index.json` and regenerates both Markdown library indexes from that JSON. A maintainer still performs final review before merge.

The pull request is opened by GitHub Actions so contributors cannot directly change the generated branch, submitted file, or PR description. The PR body and bot PR comments mention the original contributor so they can follow the PR without receiving duplicate issue comments.

If the bot finds a ZIP name, schema file name, or schema file content problem, it leaves the issue open and explains what failed. Translation contribution issue titles and bodies are frozen after submission, so contributors cannot edit submitted fields, but comments remain open. Attach the corrected ZIP in a new comment and write:

```text
/update <attachment link>
```

The bot will rerun the file checks from that replacement ZIP link. If a non-maintainer tries to change the issue title or body, the bot reverts the edit. If the problem is not file-fixable, such as a duplicate submission or mismatched Steam app metadata, the bot comments with the reason and closes the issue.

After a review PR exists, the original contributor or a maintainer can also comment the same `/update <attachment link>` command on the PR. If validation passes, the bot refreshes the PR branch and regenerates the PR description automatically.

Admins can comment:

```text
/rerun-checks
```

This command reruns the normal issue guard and submission review from the current issue contents. It is useful when an earlier automation run was missed or failed because of workflow infrastructure. It does not ignore duplicate-submission warnings or any hard validation failure. If a non-admin uses this command, the bot rejects it and leaves the normal review flow unchanged.

Admins can also comment:

```text
/force-review
```

This command lets the submission continue when a maintainer has manually accepted review warnings, such as another open submission mentioning the same app ID or selected language fields that are incomplete and should be inspected in the PR. It does not skip hard failures such as a game already accepted into the library, mismatched Steam app metadata, wrong file names, unsafe ZIP structure, or Steam Binary KeyValues parse failures. If a non-admin uses this command, the bot rejects it and leaves the normal review flow unchanged.

After a maintainer approves the generated review PR, the bot thanks the contributor, squashes and merges the PR, and deletes the contribution branch.

## Labels

- Translation library submissions use `translation-contribution`. Only this label is reviewed by the submission bot.
- Skill bug reports use `skill-bug`. These issues do not trigger translation-file review.

If GitHub does not apply the issue-template label automatically, Actions creates and applies the matching label from the issue contents.

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
