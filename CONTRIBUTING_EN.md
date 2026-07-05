# Contributing Shared Achievement Translations

English | [简体中文](CONTRIBUTING.md)

This repository accepts community-submitted Steam achievement schema files for the public translation library in `achievement-library/`. The contribution flow is handled by GitHub issues, GitHub Actions, and maintainer review; normal local skill usage does not automatically submit anything to the repository.

## Before You Submit

Check whether the same Steam app ID already exists:

- Search `achievement-library/README_EN.md` for the numeric Steam app ID, game name, contributor, or language code.
- Search open pull requests for the same app ID or `UserGameStatsSchema_<game_id>.bin`.
- Search open issues with the `translation-contribution` label.

Please do not submit a duplicate if the same game is already in the library, already in PR review, or already waiting in an open submission issue.

## Submission Rules

- Upload a ZIP named `UserGameStatsSchema_<game_id>.zip` because GitHub issues do not accept `.bin` attachments directly.
- The ZIP must contain exactly one real Steam schema file named `UserGameStatsSchema_<game_id>.bin`.
- The game ID in the issue, Steam store URL, and uploaded file name must match.
- Select only languages that are fully present in the uploaded file.
- Every selected language must include both achievement name and description fields for every achievement.
- Keep the schema file as Steam Binary KeyValues. Do not convert it to JSON, CSV, or text before zipping.
- Do not upload files containing private account data, secrets, tokens, or unrelated local files.

## Review Flow

Open the English or Chinese translation contribution issue template and attach the `.zip` file. GitHub Actions will:

- Download the uploaded file.
- Verify that the Steam store URL, game ID, ZIP name, and schema file name match.
- Unpack the ZIP and require exactly one schema file inside it.
- Parse the file as Steam Binary KeyValues and require byte-identical roundtrip serialization.
- Verify that the selected language fields are present for every achievement.
- Check whether the game is already in the library or in another open submission.
- Add the `translation-contribution` label if needed, then freeze the issue title and body so submitted fields cannot be changed afterward.
- Create a pull request after first review passes.
- Thank the contributor and close the source issue after the PR is ready.

The generated pull request contains only the submitted schema file plus a review table listing every achievement ID with each submitted language's achievement name and description. After the pull request is merged, maintenance scripts update `achievement-library/index.json` and regenerate both Markdown indexes from that JSON. A maintainer still performs final review before merge.

The pull request is opened by GitHub Actions, so contributors cannot directly change the generated branch, submitted file, or PR description. The PR body and bot comments mention the original contributor so they can follow the review without receiving duplicate issue comments.

## Fixing a Submitted File

If the bot finds a ZIP name, schema file name, or schema content problem, it leaves the issue open and explains what failed. Translation contribution issue titles and bodies are frozen after submission, but comments remain open. Write `/update` in a new comment and attach the corrected ZIP to that comment. A link after `/update` is not required; if you include both a link and an attachment, the bot uses the attached ZIP.

```text
/update
```

The bot reruns file checks from the replacement ZIP attachment. If a non-maintainer tries to change the issue title or body, the bot reverts the edit. If the problem is not file-fixable, such as a duplicate submission or mismatched Steam app metadata, the bot comments with the reason and closes the issue.

After a review PR exists, the original contributor or a maintainer can also comment `/update` on the PR and attach the replacement ZIP. If validation passes, the bot refreshes the PR branch and regenerates the PR description.

## Maintainer Commands

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

- Translation library submissions use `translation-contribution`. Only this label triggers submission review.
- Skill bug reports use `skill-bug`. These issues do not trigger translation-file review.

If GitHub does not apply the issue-template label automatically, Actions creates and applies the matching label from the issue contents.

## Script Boundaries

`scripts/steam_bkv_tool.py` is the normal skill runtime script for local schema parsing, export, translation application, and verification. Scripts in `workflow-scripts/` are repository-level GitHub Actions helpers only: `github_issue_guard.py` handles issue labeling and freezing, `library_submission_bot.py` reviews submitted files and prepares PR content, and `translation_pr_maintenance.py` maintains submission PRs, indexes, and post-merge notifications.

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

`achievement-library/README_EN.md` is the English user-facing lookup index. `achievement-library/README.md` is the Chinese default. Both are designed for GitHub browsing and browser search by game name, Steam app ID, contributor, or language code. `index.json` is the machine-readable index for scripts and automation.
