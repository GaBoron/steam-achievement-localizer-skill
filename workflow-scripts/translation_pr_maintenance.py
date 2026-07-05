#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from library_submission_bot import (
    achievement_rows,
    load_schema,
    sha256,
    upsert_index_entry,
    validate_and_update,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSION_PATHS = [
    "achievement-library/files",
]
INDEX_PATHS = [
    "achievement-library/README.md",
    "achievement-library/README_EN.md",
    "achievement-library/index.json",
]
THANKS_MARKER = "<!-- sal-merged-thanks -->"
REFRESH_MARKER = "<!-- sal-pr-refreshed -->"
UPDATE_MARKER = "<!-- sal-pr-update -->"
WAIT_FOR_UPDATE_LABEL = "wait-for-update"
BOT_USERS = {"github-actions[bot]"}
MAINTAINER_PERMISSIONS = {"admin", "maintain"}
ADMIN_PERMISSIONS = {"admin"}


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=REPO_ROOT, check=check, text=True, capture_output=True)


def github_request(
    method: str,
    repo: str,
    token: str,
    path: str,
    payload: dict[str, Any] | None = None,
    allow_404: bool = False,
    allow_422: bool = False,
) -> Any:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "steam-achievement-localizer-pr-maintenance",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body.decode("utf-8")) if body else None
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        if allow_422 and exc.code == 422:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed with HTTP {exc.code}: {detail}") from exc


def permission_for(repo: str, token: str, actor: str) -> str:
    encoded = urllib.parse.quote(actor, safe="")
    data = github_request("GET", repo, token, f"/collaborators/{encoded}/permission", allow_404=True)
    if not data:
        return "none"
    return str(data.get("permission") or "none")


def is_bot_actor(actor: str) -> bool:
    return actor in BOT_USERS or actor.endswith("[bot]")


def is_maintainer(repo: str, token: str, actor: str) -> bool:
    if is_bot_actor(actor):
        return True
    return permission_for(repo, token, actor) in MAINTAINER_PERMISSIONS


def is_admin(repo: str, token: str, actor: str) -> bool:
    if is_bot_actor(actor):
        return True
    return permission_for(repo, token, actor) in ADMIN_PERMISSIONS


def is_update_allowed(repo: str, token: str, issue: dict[str, Any], actor: str) -> bool:
    contributor = str((issue.get("user") or {}).get("login") or "")
    return actor == contributor or is_maintainer(repo, token, actor)


def issue_labels(issue: dict[str, Any]) -> set[str]:
    return {label.get("name", "") for label in issue.get("labels", []) if isinstance(label, dict)}


def issue_comment_exists(repo: str, token: str, issue_number: int, marker: str) -> bool:
    comments = github_request("GET", repo, token, f"/issues/{issue_number}/comments?per_page=100")
    return any(marker in str(comment.get("body") or "") for comment in comments or [])


def comment_issue(repo: str, token: str, issue_number: int, body: str, marker: str | None = None) -> None:
    if marker and issue_comment_exists(repo, token, issue_number, marker):
        return
    github_request("POST", repo, token, f"/issues/{issue_number}/comments", {"body": body})


def remove_issue_label(repo: str, token: str, issue_number: int, label: str) -> None:
    encoded = urllib.parse.quote(label, safe="")
    github_request("DELETE", repo, token, f"/issues/{issue_number}/labels/{encoded}", allow_404=True)


def source_issue_number(pr: dict[str, Any]) -> int | None:
    body = str(pr.get("body") or "")
    match = re.search(r"/issues/(\d+)", body)
    if match:
        return int(match.group(1))
    ref = str((pr.get("head") or {}).get("ref") or "")
    match = re.fullmatch(r"translation-library/issue-(\d+)", ref)
    return int(match.group(1)) if match else None


def issue_number_from_url(url: str) -> int | None:
    match = re.search(r"/issues/(\d+)(?:$|[?#])", url)
    return int(match.group(1)) if match else None


def source_issue_for_pr(repo: str, token: str, pr: dict[str, Any]) -> dict[str, Any] | None:
    issue_number = source_issue_number(pr)
    if not issue_number:
        return None
    return github_request("GET", repo, token, f"/issues/{issue_number}", allow_404=True)


def contributor_from_source_issue(repo: str, token: str, source_issue: str) -> str:
    issue_number = issue_number_from_url(source_issue)
    if not issue_number:
        return ""
    issue = github_request("GET", repo, token, f"/issues/{issue_number}", allow_404=True)
    if not issue:
        return ""
    return str((issue.get("user") or {}).get("login") or "")


def commit_and_push_submission(branch: str, issue_number: int) -> bool:
    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run(["git", "add", *SUBMISSION_PATHS])
    if run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        return False
    run(["git", "commit", "-m", f"data: refresh achievement translations from issue {issue_number}"])
    run(["git", "fetch", "origin", branch], check=False)
    push = run(["git", "push", "--force-with-lease", "--set-upstream", "origin", branch], check=False)
    if push.returncode != 0:
        run(["git", "fetch", "origin", branch], check=False)
        run(["git", "push", "--force-with-lease", "--set-upstream", "origin", branch])
    return True


def commit_and_push_main_index(merged_pr_number: int) -> bool:
    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run(["git", "add", *INDEX_PATHS])
    if run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        return False
    run(["git", "commit", "-m", f"data: update library index after PR #{merged_pr_number}"])
    run(["git", "push", "origin", "main"])
    return True


def update_pr_title_and_body(repo: str, token: str, pr_number: int) -> None:
    title = Path("pr_title.txt").read_text(encoding="utf-8").strip()
    body = Path("pr_body.md").read_text(encoding="utf-8")
    github_request("PATCH", repo, token, f"/pulls/{pr_number}", {"title": title, "body": body})


def strip_inline_code(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        return text[1:-1].strip()
    return text


def pr_body_field(body: str, label: str) -> str:
    pattern = re.compile(rf"^- {re.escape(label)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(body)
    return strip_inline_code(match.group(1)) if match else ""


def pr_body_field_any(body: str, labels: list[str]) -> str:
    for label in labels:
        value = pr_body_field(body, label)
        if value:
            return value
    return ""


def entry_from_merged_pr(repo: str, token: str, pr: dict[str, Any]) -> dict[str, Any]:
    body = str(pr.get("body") or "")
    game_id = pr_body_field(body, "Steam app ID")
    languages = [item.strip() for item in pr_body_field(body, "Supported languages").split(",") if item.strip()]
    schema_file = pr_body_field(body, "Schema file")
    schema_path = REPO_ROOT / schema_file
    if not schema_file or not schema_path.is_file():
        raise RuntimeError(f"merged PR schema file is missing from main: {schema_file or '<empty>'}")
    data, nodes = load_schema(schema_path)
    rows = achievement_rows(nodes, languages[0] if languages else "english")
    source_issue = pr_body_field(body, "Source issue")
    contributor = contributor_from_source_issue(repo, token, source_issue) or pr_body_field_any(body, ["Contributor / 贡献者", "Contributor"]).lstrip("@")
    entry = {
        "game_name": pr_body_field(body, "Game name"),
        "game_id": game_id,
        "store_url": pr_body_field(body, "Steam store URL"),
        "languages": languages,
        "schema_file": schema_file,
        "achievement_count": len(rows),
        "sha256": sha256(data),
        "source_issue": source_issue,
        "contributor_id": contributor,
    }
    missing = [key for key in ("game_name", "game_id", "store_url", "schema_file", "source_issue") if not entry[key]]
    if missing:
        raise RuntimeError("merged PR body is missing required index field(s): " + ", ".join(missing))
    if not languages:
        raise RuntimeError("merged PR body is missing supported languages")
    return entry


def update_main_index_from_merged_pr(repo: str, token: str, merged_pr_number: int) -> bool:
    pr = github_request("GET", repo, token, f"/pulls/{merged_pr_number}")
    if not pr.get("merged") or str((pr.get("base") or {}).get("ref") or "") != "main":
        return False
    run(["git", "fetch", "origin", "main"])
    run(["git", "checkout", "-B", "main", "origin/main"])
    entry = entry_from_merged_pr(repo, token, pr)
    upsert_index_entry(entry)
    return commit_and_push_main_index(merged_pr_number)


def open_translation_prs(repo: str, token: str) -> list[dict[str, Any]]:
    prs = github_request("GET", repo, token, "/pulls?state=open&per_page=100")
    return [
        pr
        for pr in prs or []
        if str((pr.get("head") or {}).get("ref") or "").startswith("translation-library/issue-")
        and str((pr.get("head") or {}).get("repo", {}).get("full_name") or "") == repo
        and str((pr.get("base") or {}).get("ref") or "") == "main"
    ]


def thank_contributor(repo: str, token: str, merged_pr_number: int) -> None:
    pr = github_request("GET", repo, token, f"/pulls/{merged_pr_number}")
    issue_number = source_issue_number(pr)
    contributor = "contributor"
    if issue_number:
        issue = github_request("GET", repo, token, f"/issues/{issue_number}", allow_404=True)
        if issue:
            contributor = str((issue.get("user") or {}).get("login") or contributor)
    body = (
        f"{THANKS_MARKER}\n"
        f"感谢 @{contributor} 为成就翻译库做出贡献。此 PR 已合并，投稿已经进入库中。\n\n"
        f"Thank you @{contributor} for contributing to the achievement translation library. "
        "This PR has been merged, and the submission is now in the library.\n"
    )
    comment_issue(repo, token, merged_pr_number, body, THANKS_MARKER)


def delete_merged_pr_branch(repo: str, token: str, merged_pr_number: int) -> None:
    pr = github_request("GET", repo, token, f"/pulls/{merged_pr_number}")
    head = pr.get("head") or {}
    if not pr.get("merged") or str((pr.get("base") or {}).get("ref") or "") != "main":
        return
    if str((head.get("repo") or {}).get("full_name") or "") != repo:
        return
    branch = str(head.get("ref") or "")
    if not branch.startswith("translation-library/issue-"):
        return
    encoded_ref = urllib.parse.quote(f"heads/{branch}", safe="/")
    github_request("DELETE", repo, token, f"/git/refs/{encoded_ref}", allow_404=True, allow_422=True)


def refresh_pr(repo: str, token: str, pr: dict[str, Any], merged_pr_number: int) -> None:
    pr_number = int(pr["number"])
    if pr_number == merged_pr_number:
        return
    issue_number = source_issue_number(pr)
    branch = str((pr.get("head") or {}).get("ref") or "")
    if not issue_number or not branch:
        return

    issue = github_request("GET", repo, token, f"/issues/{issue_number}", allow_404=True)
    if not issue:
        return

    run(["git", "fetch", "origin", "main"])
    run(["git", "fetch", "origin", branch], check=False)
    run(["git", "checkout", "-B", branch, "origin/main"])

    result = validate_and_update({"issue": issue}, repo, token)
    if not result.get("ok"):
        return

    if not commit_and_push_submission(branch, issue_number):
        return
    update_pr_title_and_body(repo, token, pr_number)
    comment = (
        f"{REFRESH_MARKER}\n"
        "此投稿 PR 已基于最新 `main` 重新生成，以避免其他翻译 PR 合并后产生索引冲突。\n\n"
        "This translation PR has been regenerated from the latest `main` to avoid index conflicts after another translation PR was merged.\n"
    )
    comment_issue(repo, token, pr_number, comment)


def refresh_open_prs(repo: str, token: str, merged_pr_number: int) -> None:
    run(["git", "fetch", "origin", "main"])
    for pr in open_translation_prs(repo, token):
        refresh_pr(repo, token, pr, merged_pr_number)


def comment_update_failure(repo: str, token: str, pr_number: int, contributor: str, errors: list[str], warnings: list[str], retry_allowed: bool) -> None:
    intro = (
        f"{UPDATE_MARKER}\n"
        f"@{contributor} PR 中的 `/update` 未能通过检查，投稿分支和 PR 描述未更新。\n"
        f"@{contributor}, the PR `/update` did not pass validation, so the submission branch and PR description were not updated.\n\n"
    )
    body = intro + "检查详情 / Review details:\n"
    for error in errors:
        body += f"- {error}\n"
    if warnings:
        body += "\n警告 / Warnings:\n"
        for warning in warnings:
            body += f"- {warning}\n"
    if retry_allowed:
        body += (
            "\n可以继续在 PR 或来源 issue 中评论 `/update` 并附上新的 ZIP。\n"
            "You can comment `/update` again on the PR or source issue and attach a replacement ZIP.\n"
        )
    comment_issue(repo, token, pr_number, body)


def update_pr_from_comment(repo: str, token: str, event: dict[str, Any]) -> None:
    pr_issue = event.get("issue") or {}
    pr_number = int(pr_issue["number"])
    pr = github_request("GET", repo, token, f"/pulls/{pr_number}")
    issue = source_issue_for_pr(repo, token, pr)
    if not issue:
        comment_issue(
            repo,
            token,
            pr_number,
            f"{UPDATE_MARKER}\n无法从 PR 中找到来源投稿 issue，不能处理 `/update`。\n\n"
            "Could not find the source contribution issue from this PR, so `/update` cannot be processed.",
        )
        return
    actor = str(((event.get("comment") or {}).get("user") or {}).get("login") or "")
    contributor = str((issue.get("user") or {}).get("login") or "contributor")
    if not is_update_allowed(repo, token, issue, actor):
        comment_issue(
            repo,
            token,
            pr_number,
            f"{UPDATE_MARKER}\n`/update` 只能由原投稿人 @{contributor} 或维护者使用。\n\n"
            f"`/update` can only be used by the original contributor @{contributor} or a maintainer.",
        )
        return

    branch = str((pr.get("head") or {}).get("ref") or "")
    if not branch.startswith("translation-library/issue-"):
        return
    issue_number = int(issue["number"])
    run(["git", "fetch", "origin", "main"])
    run(["git", "fetch", "origin", branch], check=False)
    run(["git", "checkout", "-B", branch, "origin/main"])
    try:
        result = validate_and_update({"issue": issue, "comment": event.get("comment") or {}}, repo, token)
    except SystemExit:
        data = json.loads(Path("submission_result.json").read_text(encoding="utf-8"))
        comment_update_failure(
            repo,
            token,
            pr_number,
            contributor,
            list(data.get("errors", [])),
            list(data.get("warnings", [])),
            bool(data.get("retry_allowed")),
        )
        return
    if not result.get("ok"):
        return
    changed = commit_and_push_submission(branch, issue_number)
    update_pr_title_and_body(repo, token, pr_number)
    body = (
        f"{UPDATE_MARKER}\n"
        f"@{contributor} PR 中的 `/update` 已通过检查，投稿分支和 PR 描述已自动刷新。\n"
        f"@{contributor}, the PR `/update` passed validation. The submission branch and PR description have been refreshed automatically.\n"
    )
    if not changed:
        body += "\n没有检测到文件内容变化，但 PR 描述已重新生成。\nNo file content changes were detected, but the PR description was regenerated.\n"
    comment_issue(repo, token, pr_number, body)


def clear_wait_for_update_from_comment(repo: str, token: str, event: dict[str, Any]) -> None:
    issue = event.get("issue") or {}
    if not issue.get("pull_request"):
        return
    if WAIT_FOR_UPDATE_LABEL not in issue_labels(issue):
        return
    actor = str(((event.get("comment") or {}).get("user") or {}).get("login") or "")
    if not actor:
        actor = str((event.get("sender") or {}).get("login") or "")
    if not actor:
        return
    if is_admin(repo, token, actor):
        return
    remove_issue_label(repo, token, int(issue["number"]), WAIT_FOR_UPDATE_LABEL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain translation PRs after a library submission merge.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--merged-pr", type=int, default=0)
    parser.add_argument("--event", type=Path)
    parser.add_argument("--thank", action="store_true")
    parser.add_argument("--update-index", action="store_true")
    parser.add_argument("--refresh-open", action="store_true")
    parser.add_argument("--delete-branch", action="store_true")
    parser.add_argument("--pr-update", action="store_true")
    parser.add_argument("--clear-wait-for-update", action="store_true")
    args = parser.parse_args()

    if args.update_index:
        if not args.merged_pr:
            raise SystemExit("--update-index requires --merged-pr")
        update_main_index_from_merged_pr(args.repo, args.token, args.merged_pr)
    if args.thank:
        if not args.merged_pr:
            raise SystemExit("--thank requires --merged-pr")
        thank_contributor(args.repo, args.token, args.merged_pr)
    if args.delete_branch:
        if not args.merged_pr:
            raise SystemExit("--delete-branch requires --merged-pr")
        delete_merged_pr_branch(args.repo, args.token, args.merged_pr)
    if args.refresh_open:
        if not args.merged_pr:
            raise SystemExit("--refresh-open requires --merged-pr")
        refresh_open_prs(args.repo, args.token, args.merged_pr)
    if args.pr_update:
        if not args.event:
            raise SystemExit("--event is required for PR event handling")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        update_pr_from_comment(args.repo, args.token, event)
    if args.clear_wait_for_update:
        if not args.event:
            raise SystemExit("--event is required for PR event handling")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        clear_wait_for_update_from_comment(args.repo, args.token, event)


if __name__ == "__main__":
    main()
