#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

LABELS = {
    "translation-contribution": {
        "color": "2da44e",
        "description": "Community achievement translation library submission",
    },
    "skill-bug": {
        "color": "d73a4a",
        "description": "Bug report for the Steam Achievement Localizer skill",
    },
}

MAINTAINER_PERMISSIONS = {"admin", "maintain"}
ADMIN_PERMISSIONS = {"admin"}
BOT_USERS = {"github-actions[bot]"}


def github_request(
    method: str,
    repo: str,
    token: str,
    path: str,
    payload: dict[str, Any] | None = None,
    allow_404: bool = False,
    allow_422: bool = False,
) -> dict[str, Any] | None:
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "steam-achievement-localizer-issue-guard",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        if allow_422 and exc.code == 422:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed with HTTP {exc.code}: {detail}") from exc


def issue_labels(issue: dict[str, Any]) -> set[str]:
    return {label.get("name", "") for label in issue.get("labels", []) if isinstance(label, dict)}


def issue_text(issue: dict[str, Any]) -> str:
    return f"{issue.get('title') or ''}\n{issue.get('body') or ''}"


def is_translation_issue(issue: dict[str, Any]) -> bool:
    labels = issue_labels(issue)
    text = issue_text(issue)
    return (
        "translation-contribution" in labels
        or str(issue.get("title") or "").startswith("[Translation contribution]")
        or (
            "### Steam app ID" in text
            and (
                "### Achievement schema ZIP" in text
                or "### 成就 schema ZIP" in text
                or "### 上传文件包含的语言" in text
            )
        )
    )


def was_translation_issue_before_edit(event: dict[str, Any]) -> bool:
    issue = event.get("issue") or {}
    changes = event.get("changes") or {}
    previous = {
        "title": issue.get("title") or "",
        "body": issue.get("body") or "",
        "labels": issue.get("labels") or [],
    }
    if isinstance(changes.get("title"), dict) and "from" in changes["title"]:
        previous["title"] = changes["title"]["from"]
    if isinstance(changes.get("body"), dict) and "from" in changes["body"]:
        previous["body"] = changes["body"]["from"]
    return is_translation_issue(previous)


def is_skill_bug_issue(issue: dict[str, Any]) -> bool:
    labels = issue_labels(issue)
    text = issue_text(issue)
    return (
        "skill-bug" in labels
        or str(issue.get("title") or "").startswith("[Skill bug]")
        or "### Bug summary" in text
        or "### 问题概述" in text
    )


def ensure_label(repo: str, token: str, name: str) -> None:
    encoded = urllib.parse.quote(name, safe="")
    if github_request("GET", repo, token, f"/labels/{encoded}", allow_404=True) is not None:
        return
    config = LABELS[name]
    github_request(
        "POST",
        repo,
        token,
        "/labels",
        {"name": name, "color": config["color"], "description": config["description"]},
        allow_422=True,
    )


def add_issue_labels(repo: str, token: str, issue_number: int, labels: list[str]) -> None:
    for label in labels:
        ensure_label(repo, token, label)
    github_request("POST", repo, token, f"/issues/{issue_number}/labels", {"labels": labels})


def permission_for(repo: str, token: str, actor: str) -> str:
    encoded = urllib.parse.quote(actor, safe="")
    data = github_request("GET", repo, token, f"/collaborators/{encoded}/permission", allow_404=True)
    if not data:
        return "none"
    return str(data.get("permission") or "none")


def is_maintainer(repo: str, token: str, actor: str) -> bool:
    if actor in BOT_USERS:
        return True
    return permission_for(repo, token, actor) in MAINTAINER_PERMISSIONS


def is_admin(repo: str, token: str, actor: str) -> bool:
    if actor in BOT_USERS:
        return True
    return permission_for(repo, token, actor) in ADMIN_PERMISSIONS


def is_comment_command(body: str, command: str) -> bool:
    text = body.strip().lower()
    normalized = command.lower()
    return text == normalized or text.startswith(normalized + " ")


def comment_issue(repo: str, token: str, issue_number: int, body: str) -> None:
    github_request("POST", repo, token, f"/issues/{issue_number}/comments", {"body": body})


def patch_issue(repo: str, token: str, issue_number: int, payload: dict[str, Any]) -> None:
    if payload:
        github_request("PATCH", repo, token, f"/issues/{issue_number}", payload)


def guard_issue(event: dict[str, Any], repo: str, token: str) -> None:
    issue = event.get("issue") or {}
    if issue.get("pull_request"):
        return
    issue_number = int(issue["number"])
    action = str(event.get("action") or "")
    actor = str((event.get("sender") or {}).get("login") or "")
    comment = event.get("comment") or {}
    if comment and is_comment_command(str(comment.get("body") or ""), "/rerun-checks") and not is_admin(repo, token, actor):
        return

    labels_to_add: list[str] = []
    translation_issue = is_translation_issue(issue) or was_translation_issue_before_edit(event)
    if translation_issue:
        labels_to_add.append("translation-contribution")
    if is_skill_bug_issue(issue):
        labels_to_add.append("skill-bug")
    if labels_to_add:
        existing_labels = issue_labels(issue)
        missing_labels = [label for label in labels_to_add if label not in existing_labels]
        if missing_labels:
            add_issue_labels(repo, token, issue_number, missing_labels)

    if not translation_issue:
        return

    if action == "edited" and not is_maintainer(repo, token, actor):
        changes = event.get("changes") or {}
        patch: dict[str, Any] = {}
        if isinstance(changes.get("title"), dict) and "from" in changes["title"]:
            patch["title"] = changes["title"]["from"]
        if isinstance(changes.get("body"), dict) and "from" in changes["body"]:
            patch["body"] = changes["body"]["from"]
        patch_issue(repo, token, issue_number, patch)
        if patch:
            comment_issue(
                repo,
                token,
                issue_number,
                "此翻译投稿 issue 提交后已冻结。只有维护者可以修改标题或正文；评论仍保持开放，"
                "投稿人可以继续评论 `/update` 并附上替换 ZIP。非维护者的编辑已被还原。\n\n"
                "This translation contribution issue is frozen after submission. "
                "Only maintainers can change the submitted title or body. "
                "Comments remain open, including `/update` with an attached replacement ZIP. "
                "The non-maintainer edit was reverted.",
            )


def require_maintainer_command(event: dict[str, Any], repo: str, token: str, command: str) -> None:
    comment = event.get("comment") or {}
    body = str(comment.get("body") or "").strip()
    output_path = os.environ.get("GITHUB_OUTPUT")
    authorized = True
    if is_comment_command(body, command):
        actor = str((comment.get("user") or {}).get("login") or "")
        authorized = is_admin(repo, token, actor)
        if not authorized:
            issue = event.get("issue") or {}
            comment_issue(
                repo,
                token,
                int(issue["number"]),
                f"`{command}` 仅管理员可用。普通审核流程未被更改。\n\n"
                f"`{command}` is admin-only. The normal review flow was not changed.",
            )
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            handle.write(f"authorized={str(authorized).lower()}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Label and freeze GitHub issue-form submissions.")
    parser.add_argument("--event", type=Path, required=True, help="GitHub event JSON path")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/repo")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token")
    parser.add_argument("--mode", choices=["guard", "require-maintainer-command"], default="guard")
    parser.add_argument("--command", default="/force-review", help="comment command checked by require-maintainer-command")
    args = parser.parse_args()

    if not args.repo or not args.token:
        raise SystemExit("Both --repo and --token are required.")
    event = json.loads(args.event.read_text(encoding="utf-8"))
    if args.mode == "guard":
        guard_issue(event, args.repo, args.token)
    else:
        require_maintainer_command(event, args.repo, args.token, args.command)


if __name__ == "__main__":
    main()
