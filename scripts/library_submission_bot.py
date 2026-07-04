#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from steam_bkv_tool import achievement_rows, load_schema, serialize, sha256  # noqa: E402

INDEX_PATH = REPO_ROOT / "achievement-library" / "index.json"
HUMAN_INDEX_PATH = REPO_ROOT / "achievement-library" / "README.md"
HUMAN_INDEX_EN_PATH = REPO_ROOT / "achievement-library" / "README_EN.md"
FILES_ROOT = REPO_ROOT / "achievement-library" / "files"
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
MAX_SCHEMA_BYTES = 32 * 1024 * 1024
LANGUAGE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SCHEMA_NAME_RE = re.compile(r"^UserGameStatsSchema_(\d+)\.bin$", re.IGNORECASE)
ZIP_NAME_RE = re.compile(r"^UserGameStatsSchema_(\d+)\.zip$", re.IGNORECASE)
ATTACHMENT_RE = re.compile(r"\[([^\]]+)\]\((https://github\.com/user-attachments/[^\s)]+)\)|(?<!\()(?P<url>https://github\.com/user-attachments/[^\s)]+)")


@dataclass
class Attachment:
    filename: str
    url: str
    filename_from_url: bool = False


@dataclass
class ReviewProblem:
    message: str
    retryable: bool = False


def parse_issue_form(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current: str | None = None
    chunks: list[str] = []
    for line in body.splitlines():
        if line.startswith("### "):
            if current is not None:
                fields[current] = "\n".join(chunks).strip()
            current = line.removeprefix("### ").strip()
            chunks = []
        elif current is not None:
            chunks.append(line)
    if current is not None:
        fields[current] = "\n".join(chunks).strip()
    return fields


def first_line(value: str) -> str:
    for line in value.splitlines():
        text = line.strip()
        if text and text != "_No response_":
            return text
    return ""


def field_value(fields: dict[str, str], names: list[str]) -> str:
    for name in names:
        if name in fields:
            return fields[name]
    return ""


def parse_checked_languages(value: str) -> list[str]:
    languages: list[str] = []
    for line in value.splitlines():
        match = re.match(r"- \[[xX]\]\s*([a-z][a-z0-9_]*)\b", line.strip())
        if match:
            languages.append(match.group(1).lower())
    return languages


def parse_extra_languages(value: str) -> list[str]:
    text = first_line(value).lower()
    if not text or text in {"none", "n/a", "na", "no"}:
        return []
    return [part.strip() for part in re.split(r"[,;\s]+", text) if part.strip()]


def extract_attachment(value: str) -> Attachment | None:
    matches = list(ATTACHMENT_RE.finditer(value))
    if len(matches) != 1:
        return None
    match = matches[0]
    url = match.group(2) or match.group("url")
    filename_from_url = not bool(match.group(1))
    filename = match.group(1) or Path(urllib.parse.urlparse(url).path).name
    filename = urllib.parse.unquote(filename.strip())
    return Attachment(filename=filename, url=url, filename_from_url=filename_from_url)


def extract_update_attachment(body: str) -> Attachment | None:
    text = body.strip()
    if not text.lower().startswith("/update"):
        return None
    return extract_attachment(text[len("/update"):].strip())


def download_attachment(attachment: Attachment, token: str | None, destination: Path) -> None:
    request = urllib.request.Request(attachment.url, headers={"User-Agent": "steam-achievement-localizer-submission-bot"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=45) as response:
        total = 0
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("uploaded file is larger than the 32 MiB review limit")
                handle.write(chunk)


def safe_archive_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    for member in archive.infolist():
        normalized = member.filename.replace("\\", "/")
        if member.is_dir() or normalized.endswith("/"):
            continue
        parts = [part for part in normalized.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            raise ValueError("ZIP archive contains an unsafe file path")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            raise ValueError("ZIP archive contains an absolute file path")
        members.append(member)
    return members


def resolve_schema_upload(downloaded: Path, attachment: Attachment, game_id: str, output_dir: Path) -> Path:
    expected_name = f"UserGameStatsSchema_{game_id}.bin"
    if zipfile.is_zipfile(downloaded):
        with zipfile.ZipFile(downloaded) as archive:
            members = safe_archive_members(archive)
            if len(members) != 1:
                raise ValueError("ZIP upload must contain exactly one schema file")
            member = members[0]
            member_name = Path(member.filename.replace("\\", "/")).name
            if member_name != expected_name:
                raise ValueError(f"ZIP upload must contain {expected_name}; got {member_name}")
            if member.file_size > MAX_SCHEMA_BYTES:
                raise ValueError("schema file inside ZIP is larger than the 32 MiB review limit")
            output_path = output_dir / expected_name
            output_path.write_bytes(archive.read(member))
            return output_path
    if attachment.filename_from_url:
        return downloaded
    if attachment.filename != expected_name:
        raise ValueError(f"uploaded file name must be {expected_name}; got {attachment.filename}")
    return downloaded


def load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return {"version": 1, "description": "Community-submitted Steam achievement schema translations.", "entries": []}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def write_index(index: dict[str, Any]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_human_index(index: dict[str, Any]) -> None:
    entries = sorted(index.get("entries", []), key=lambda item: int(item.get("game_id", 0)))
    zh_lines = [
        "# 社区成就翻译库",
        "",
        "简体中文 | [English](README_EN.md)",
        "",
        "查询某个游戏是否已经投稿时，优先查看本页。你可以直接用浏览器搜索 Steam app ID、游戏名或语言代码。",
        "",
        "## 游戏列表",
        "",
    ]
    en_lines = [
        "# Community Achievement Translation Library",
        "",
        "[简体中文](README.md) | English",
        "",
        "Browse this page first when checking whether a game has already been submitted. Use your browser search on this page for the Steam app ID, game name, or language code.",
        "",
        "## Games",
        "",
    ]
    if entries:
        zh_lines.extend([
            "| Steam app ID | 游戏 | 支持语言 | 成就数 | 成就文件 | 商店 |",
            "| --- | --- | --- | ---: | --- | --- |",
        ])
        en_lines.extend([
            "| Steam app ID | Game | Languages | Achievements | Schema file | Store |",
            "| --- | --- | --- | ---: | --- | --- |",
        ])
        for entry in entries:
            game_id = str(entry.get("game_id", ""))
            game_name = escape_table(str(entry.get("game_name", "")))
            languages = escape_table(", ".join(entry.get("languages", [])))
            count = str(entry.get("achievement_count", ""))
            schema_file = str(entry.get("schema_file", ""))
            schema_link = schema_file.removeprefix("achievement-library/")
            store_url = str(entry.get("store_url", ""))
            row = f"| `{game_id}` | {game_name} | {languages} | {count} | [`{schema_file}`]({schema_link}) | [Steam]({store_url}) |"
            zh_lines.append(row)
            en_lines.append(row)
    else:
        zh_lines.append("暂无已收录游戏。")
        en_lines.append("No games have been accepted yet.")
    zh_lines.extend([
        "",
        "## 搜索建议",
        "",
        "- 搜索 Steam app ID，例如 `123456`。",
        "- 不知道 app ID 时，搜索游戏名。",
        "- 搜索 Steam 语言代码，例如 `schinese`、`tchinese`、`japanese` 或 `koreana`。",
        "",
        "## 机器索引",
        "",
        "自动化脚本读取 `index.json`。普通用户应优先使用这个 Markdown 索引快速查找。",
    ])
    en_lines.extend([
        "",
        "## Search Tips",
        "",
        "- Search this page for a Steam app ID such as `123456`.",
        "- Search by game name if you do not know the app ID.",
        "- Search by Steam language code such as `schinese`, `tchinese`, `japanese`, or `koreana`.",
        "",
        "## Machine Index",
        "",
        "Automation reads `index.json`. Users should prefer this Markdown index for quick lookup.",
    ])
    HUMAN_INDEX_PATH.write_text("\n".join(zh_lines) + "\n", encoding="utf-8")
    HUMAN_INDEX_EN_PATH.write_text("\n".join(en_lines) + "\n", encoding="utf-8")


def existing_entry(index: dict[str, Any], game_id: str) -> dict[str, Any] | None:
    for entry in index.get("entries", []):
        if str(entry.get("game_id")) == game_id:
            return entry
    return None


def steam_store_id(url: str) -> str | None:
    match = re.search(r"store\.steampowered\.com/app/(\d+)(?:/|$)", url)
    return match.group(1) if match else None


def github_api_json(url: str, token: str | None) -> dict[str, Any] | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "steam-achievement-localizer-submission-bot",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def open_duplicate_warnings(repo: str, token: str | None, game_id: str, issue_number: int) -> list[str]:
    query = urllib.parse.quote(f"repo:{repo} is:open {game_id}")
    data = github_api_json(f"https://api.github.com/search/issues?q={query}", token)
    if not data:
        return ["Could not query open issues and pull requests for duplicates; please check manually."]
    warnings: list[str] = []
    for item in data.get("items", []):
        number = int(item.get("number", 0))
        if number == issue_number:
            continue
        if item.get("pull_request"):
            warnings.append(f"Open pull request #{number} also mentions Steam app ID {game_id}: {item.get('html_url')}")
            continue
        labels = {label.get("name") for label in item.get("labels", []) if isinstance(label, dict)}
        if "translation-contribution" in labels:
            warnings.append(f"Open translation contribution issue #{number} also mentions Steam app ID {game_id}: {item.get('html_url')}")
    return warnings


def split_problems(problems: list[ReviewProblem]) -> tuple[list[str], bool]:
    return [problem.message for problem in problems], all(problem.retryable for problem in problems)


def language_coverage(nodes: list[Any], languages: list[str]) -> tuple[dict[str, int], dict[str, list[str]], list[dict[str, Any]]]:
    coverage: dict[str, int] = {}
    missing: dict[str, list[str]] = {}
    rows_by_language: dict[str, list[dict[str, Any]]] = {language: achievement_rows(nodes, language) for language in languages}
    base_rows = rows_by_language[languages[0]] if languages else achievement_rows(nodes, "english")
    for language, rows in rows_by_language.items():
        present = [
            row
            for row in rows
            if str(row.get(f"{language}_name", "")).strip() and str(row.get(f"{language}_description", "")).strip()
        ]
        coverage[language] = len(present)
        missing[language] = [
            str(row.get("api_name", ""))
            for row in rows
            if not str(row.get(f"{language}_name", "")).strip() or not str(row.get(f"{language}_description", "")).strip()
        ]
    return coverage, missing, base_rows


def build_review_table(nodes: list[Any], languages: list[str]) -> str:
    per_language = {language: achievement_rows(nodes, language) for language in languages}
    base_rows = per_language[languages[0]]
    header = ["Achievement ID"]
    for language in languages:
        header.extend([f"{language} name", f"{language} description"])
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for index, row in enumerate(base_rows):
        cells = [escape_table(str(row.get("api_name", "")))]
        for language in languages:
            language_row = per_language[language][index]
            cells.append(escape_table(str(language_row.get(f"{language}_name", ""))))
            cells.append(escape_table(str(language_row.get(f"{language}_description", ""))))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def sanitize_branch_part(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
    return value[:80] or "submission"


def event_update_attachment(event: dict[str, Any]) -> Attachment | None:
    comment = event.get("comment") or {}
    return extract_update_attachment(comment.get("body") or "")


def is_comment_command(body: str, command: str) -> bool:
    text = body.strip().lower()
    normalized = command.lower()
    return text == normalized or text.startswith(normalized + " ")


def event_force_review(event: dict[str, Any]) -> bool:
    comment = event.get("comment") or {}
    return is_comment_command(str(comment.get("body") or ""), "/force-review")


def validate_and_update(event: dict[str, Any], repo: str, token: str | None) -> dict[str, Any]:
    issue = event["issue"]
    issue_number = int(issue["number"])
    fields = parse_issue_form(issue.get("body") or "")
    problems: list[ReviewProblem] = []
    warnings: list[str] = []
    force_review = event_force_review(event)

    game_name = first_line(field_value(fields, ["Game name", "游戏名"]))
    game_id = first_line(field_value(fields, ["Steam app ID"]))
    store_url = first_line(field_value(fields, ["Steam store URL", "Steam 商店地址"]))
    languages = sorted(set(
        parse_checked_languages(field_value(fields, ["Languages included in the uploaded file", "上传文件包含的语言"]))
        + parse_extra_languages(field_value(fields, ["Additional Steam language codes", "其他 Steam 语言代码"]))
    ))
    update_attachment = event_update_attachment(event)
    attachment = update_attachment or extract_attachment(field_value(fields, [
        "Achievement schema ZIP",
        "Achievement schema file",
        "成就 schema ZIP",
        "成就 schema 文件",
    ]))

    if not game_name:
        problems.append(ReviewProblem("Game name is required."))
    if not re.fullmatch(r"\d+", game_id):
        problems.append(ReviewProblem("Steam app ID must be numeric."))
    store_id = steam_store_id(store_url)
    if not store_id:
        problems.append(ReviewProblem("Steam store URL must be a store.steampowered.com/app/<id>/ URL."))
    elif game_id and store_id != game_id:
        problems.append(ReviewProblem(f"Steam store URL app ID {store_id} does not match submitted app ID {game_id}."))
    invalid_languages = [language for language in languages if not LANGUAGE_RE.fullmatch(language)]
    if not languages:
        problems.append(ReviewProblem("Select or enter at least one Steam language code."))
    if invalid_languages:
        problems.append(ReviewProblem("Invalid Steam language code(s): " + ", ".join(invalid_languages)))
    if not attachment:
        problems.append(ReviewProblem("Attach exactly one UserGameStatsSchema_<game_id>.zip file containing UserGameStatsSchema_<game_id>.bin, or comment `/update <attachment link>` with a replacement ZIP.", retryable=True))

    index = load_index()
    existing = existing_entry(index, game_id) if game_id else None
    if existing and existing.get("source_issue") != issue.get("html_url"):
        problems.append(ReviewProblem(f"Steam app ID {game_id} already exists in achievement-library/README.md and achievement-library/index.json."))
    if game_id and repo:
        duplicate_warnings = open_duplicate_warnings(repo, token, game_id, issue_number)
        blocking_duplicates = [item for item in duplicate_warnings if item.startswith("Open ")]
        if blocking_duplicates and not force_review:
            problems.extend(ReviewProblem(item) for item in blocking_duplicates)
        elif blocking_duplicates:
            warnings.extend(f"Maintainer override accepted with /force-review: {item}" for item in blocking_duplicates)
        else:
            warnings.extend(duplicate_warnings)

    if attachment and game_id and not attachment.filename_from_url:
        schema_name_match = SCHEMA_NAME_RE.fullmatch(attachment.filename)
        zip_name_match = ZIP_NAME_RE.fullmatch(attachment.filename)
        if not schema_name_match and not zip_name_match:
            problems.append(ReviewProblem(f"Uploaded file must be UserGameStatsSchema_{game_id}.zip containing UserGameStatsSchema_{game_id}.bin; got {attachment.filename}. Comment `/update <attachment link>` with a correctly named ZIP replacement.", retryable=True))
        elif schema_name_match and schema_name_match.group(1) != game_id:
            problems.append(ReviewProblem(f"Uploaded file name app ID {schema_name_match.group(1)} does not match submitted app ID {game_id}. Comment `/update <attachment link>` with a replacement ZIP whose name matches the submitted app ID.", retryable=True))
        elif zip_name_match and zip_name_match.group(1) != game_id:
            problems.append(ReviewProblem(f"Uploaded ZIP name app ID {zip_name_match.group(1)} does not match submitted app ID {game_id}. Comment `/update <attachment link>` with a replacement ZIP whose name matches the submitted app ID.", retryable=True))

    if problems:
        errors, retry_allowed = split_problems(problems)
        return write_failure(errors, warnings, retry_allowed)

    assert attachment is not None
    with tempfile.TemporaryDirectory() as tmp:
        downloaded = Path(tmp) / attachment.filename
        try:
            download_attachment(attachment, token, downloaded)
            schema_path = resolve_schema_upload(downloaded, attachment, game_id, Path(tmp))
            data, nodes = load_schema(schema_path)
            rebuilt = serialize(nodes)
        except Exception as exc:  # noqa: BLE001 - user-facing validation report.
            return write_failure([f"Could not download or parse the uploaded schema ZIP: {exc}. Comment `/update <attachment link>` with a replacement ZIP containing exactly one UserGameStatsSchema_{game_id}.bin file."], warnings, True)

        if data != rebuilt:
            problems.append(ReviewProblem("Uploaded schema does not roundtrip byte-identically through the Steam Binary KeyValues parser. Comment `/update <attachment link>` with a replacement ZIP.", retryable=True))
        rows = achievement_rows(nodes, languages[0])
        achievement_ids = [str(row.get("api_name", "")) for row in rows]
        if not rows:
            problems.append(ReviewProblem("Uploaded schema does not contain any Steam achievement display name/description records. Comment `/update <attachment link>` with a replacement ZIP.", retryable=True))
        if any(not achievement_id for achievement_id in achievement_ids):
            problems.append(ReviewProblem("Every achievement must have a non-empty API name. Comment `/update <attachment link>` with a replacement ZIP.", retryable=True))
        if len(set(achievement_ids)) != len(achievement_ids):
            problems.append(ReviewProblem("Achievement API names must be unique. Comment `/update <attachment link>` with a replacement ZIP.", retryable=True))

        coverage, missing, _ = language_coverage(nodes, languages)
        for language, missing_ids in missing.items():
            if missing_ids:
                preview = ", ".join(missing_ids[:10])
                suffix = " ..." if len(missing_ids) > 10 else ""
                problems.append(ReviewProblem(f"Language {language} is missing name or description fields for {len(missing_ids)} achievement(s): {preview}{suffix}. Comment `/update <attachment link>` with a replacement ZIP.", retryable=True))

        if problems:
            errors, retry_allowed = split_problems(problems)
            return write_failure(errors, warnings, retry_allowed)

        target_dir = FILES_ROOT / game_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"UserGameStatsSchema_{game_id}.bin"
        shutil.copy2(schema_path, target_file)

    entry = {
        "game_name": game_name,
        "game_id": game_id,
        "store_url": store_url,
        "languages": languages,
        "schema_file": str(target_file.relative_to(REPO_ROOT)).replace("\\", "/"),
        "achievement_count": len(rows),
        "sha256": sha256(data),
        "source_issue": issue.get("html_url"),
    }
    entries = [item for item in index.get("entries", []) if str(item.get("game_id")) != game_id]
    entries.append(entry)
    index["entries"] = sorted(entries, key=lambda item: int(item.get("game_id", 0)))
    write_index(index)
    write_human_index(index)

    branch = f"translation-library/issue-{issue_number}"
    pr_title = f"Add achievement translations for {game_name} ({game_id})"
    pr_body = build_pr_body(entry, coverage, nodes, languages, issue.get("html_url", ""), warnings, force_review)
    Path("pr_title.txt").write_text(pr_title + "\n", encoding="utf-8")
    Path("pr_body.md").write_text(pr_body, encoding="utf-8")
    result = {
        "ok": True,
        "branch": branch,
        "pr_title": pr_title,
        "game_id": game_id,
        "game_name": game_name,
        "languages": languages,
        "achievement_count": len(rows),
        "warnings": warnings,
        "force_review": force_review,
        "issue_number": issue_number,
    }
    Path("submission_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def write_failure(errors: list[str], warnings: list[str], retry_allowed: bool) -> dict[str, Any]:
    result = {
        "ok": False,
        "errors": errors,
        "warnings": warnings,
        "retry_allowed": retry_allowed,
        "close_issue": not retry_allowed,
    }
    Path("submission_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(1)


def build_pr_body(
    entry: dict[str, Any],
    coverage: dict[str, int],
    nodes: list[Any],
    languages: list[str],
    issue_url: str,
    warnings: list[str],
    force_review: bool,
) -> str:
    language_summary = ", ".join(languages)
    coverage_lines = "\n".join(f"- `{language}`: {count}/{entry['achievement_count']} achievements" for language, count in coverage.items())
    table = build_review_table(nodes, languages)
    warning_section = ""
    if warnings or force_review:
        warning_lines = "\n".join(f"- {escape_table(item)}" for item in warnings) if warnings else "- No warning details were recorded."
        override_line = "- Maintainer override: `/force-review` was used." if force_review else "- Maintainer override: not used."
        warning_section = f"""
## Warnings

{override_line}
{warning_lines}
"""
    return f"""## Translation Library Submission

- Game name: {entry['game_name']}
- Steam app ID: `{entry['game_id']}`
- Steam store URL: {entry['store_url']}
- Supported languages: {language_summary}
- Achievement count: {entry['achievement_count']}
- Schema file: `{entry['schema_file']}`
- SHA-256: `{entry['sha256']}`
- Source issue: {issue_url}

## Language Coverage

{coverage_lines}
{warning_section}

## Achievement Text

{table}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a translation-contribution issue and prepare a library PR.")
    parser.add_argument("--event", type=Path, required=True, help="GitHub event JSON path")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/repo for duplicate checks")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token for downloads and duplicate checks")
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    validate_and_update(event, args.repo, args.token)


if __name__ == "__main__":
    main()
