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

from library_submission_bot import validate_and_update

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_PATHS = [
    "achievement-library/README.md",
    "achievement-library/README_EN.md",
    "achievement-library/index.json",
    "achievement-library/files",
]
THANKS_MARKER = "<!-- sal-merged-thanks -->"
REFRESH_MARKER = "<!-- sal-pr-refreshed -->"


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=REPO_ROOT, check=check, text=True, capture_output=True)


def github_request(
    method: str,
    repo: str,
    token: str,
    path: str,
    payload: dict[str, Any] | None = None,
    allow_404: bool = False,
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
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed with HTTP {exc.code}: {detail}") from exc


def issue_comment_exists(repo: str, token: str, issue_number: int, marker: str) -> bool:
    comments = github_request("GET", repo, token, f"/issues/{issue_number}/comments?per_page=100")
    return any(marker in str(comment.get("body") or "") for comment in comments or [])


def comment_issue(repo: str, token: str, issue_number: int, body: str, marker: str | None = None) -> None:
    if marker and issue_comment_exists(repo, token, issue_number, marker):
        return
    github_request("POST", repo, token, f"/issues/{issue_number}/comments", {"body": body})


def source_issue_number(pr: dict[str, Any]) -> int | None:
    body = str(pr.get("body") or "")
    match = re.search(r"/issues/(\d+)", body)
    if match:
        return int(match.group(1))
    ref = str((pr.get("head") or {}).get("ref") or "")
    match = re.fullmatch(r"translation-library/issue-(\d+)", ref)
    return int(match.group(1)) if match else None


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
    if issue_number:
        comment_issue(repo, token, issue_number, body, THANKS_MARKER)


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

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run(["git", "add", *LIBRARY_PATHS])
    if run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        return
    run(["git", "commit", "-m", f"data: refresh achievement translations from issue {issue_number}"])
    run(["git", "push", "--force-with-lease", "--set-upstream", "origin", branch])

    title = Path("pr_title.txt").read_text(encoding="utf-8").strip()
    body = Path("pr_body.md").read_text(encoding="utf-8")
    github_request("PATCH", repo, token, f"/pulls/{pr_number}", {"title": title, "body": body})
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain translation PRs after a library submission merge.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--merged-pr", type=int, required=True)
    parser.add_argument("--thank", action="store_true")
    parser.add_argument("--refresh-open", action="store_true")
    args = parser.parse_args()

    if args.thank:
        thank_contributor(args.repo, args.token, args.merged_pr)
    if args.refresh_open:
        refresh_open_prs(args.repo, args.token, args.merged_pr)


if __name__ == "__main__":
    main()
