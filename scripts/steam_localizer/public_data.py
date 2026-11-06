"""Read Steam's public structured achievement list; never reconstruct a BIN."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable

from .translation_json import TextDocument, unique_object, validate_app_id
from .translations import validate_language


MAX_PAGE_BYTES = 8 * 1024 * 1024
PUBLIC_LIMITATIONS = [
    "Only publicly exposed achievements were retrieved; hidden/unavailable records are not invented.",
    "Game build/version and complete client schema were not verified.",
    "Languages not requested or not accessible were not reviewed.",
    "Steam's public page is not a stable API; no BIN roundtrip or client installation was tested.",
]


class _StructuredDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.active = dict(attrs).get("id") == "valve-ssr-data"
            if self.active:
                self.scripts.append("")

    def handle_data(self, data: str) -> None:
        if self.active:
            self.scripts[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.active = False


def parse_public_page(html: str, app_id: str, language: str) -> dict[str, tuple[str, str]]:
    parser = _StructuredDataParser()
    parser.feed(html)
    if len(parser.scripts) != 1:
        raise ValueError("Steam page has no unambiguous structured achievement data")
    root = json.loads(parser.scripts[0], object_pairs_hook=unique_object)
    if not isinstance(root, dict):
        raise ValueError("invalid Steam structured data root")
    candidates: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if str(value.get("appid")) == app_id and value.get("language") == language and isinstance(value.get("groups"), list):
                candidates.append(value)
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    loaders = root.get("loaderData", [])
    if not isinstance(loaders, list):
        raise ValueError("invalid Steam loader data")
    context = root.get("renderContext", {})
    if not isinstance(context, dict):
        raise ValueError("invalid Steam render context")
    for embedded in [*loaders, context.get("queryData")]:
        visit(json.loads(embedded, object_pairs_hook=unique_object) if isinstance(embedded, str) else embedded)
    if len(candidates) != 1:
        raise ValueError("Steam public data is unavailable or has ambiguous app/language identity")
    rows = {}
    for group in candidates[0]["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("achievements"), list):
            raise ValueError("incomplete public achievement group")
        for achievement in group["achievements"]:
            if not isinstance(achievement, dict):
                raise ValueError("invalid public achievement record")
            api_name = achievement.get("api_name")
            if not isinstance(api_name, str) or not api_name.strip() or api_name in rows:
                raise ValueError("public data contains missing or duplicate API names")
            name, description = achievement.get("name"), achievement.get("description")
            if not isinstance(name, str) or not isinstance(description, str):
                raise ValueError(f"public text is incomplete for {api_name}")
            rows[api_name] = (name, description)
    if not 1 <= len(rows) <= 10000:
        raise ValueError("Steam did not expose a usable achievement list")
    return rows


class PublicAchievementClient:
    def __init__(self, opener: Callable[..., Any] | None = None) -> None:
        self._opener = opener or urllib.request.urlopen

    def fetch(self, app_id: str, languages: tuple[str, ...]) -> dict[str, Any]:
        validate_app_id(app_id)
        requested = tuple(dict.fromkeys(validate_language(code) for code in languages))
        if not requested or len(requested) > 63:
            raise ValueError("request 1 to 63 public source languages")
        values: dict[str, dict[str, tuple[str, str]]] = {}
        sources = []
        unavailable = []
        blockers = []
        expected_ids: set[str] | None = None
        for code in requested:
            url = f"https://steamcommunity.com/stats/{app_id}/achievements/?l={code}"
            retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "steam-achievement-localizer-skill"})
                with self._opener(request, timeout=25) as response:
                    raw = response.read(MAX_PAGE_BYTES + 1)
                if len(raw) > MAX_PAGE_BYTES:
                    raise ValueError("Steam public page exceeds 8 MiB")
                rows = parse_public_page(raw.decode("utf-8"), app_id, code)
            except (OSError, UnicodeError, ValueError, RecursionError) as exc:
                unavailable.append({"language": code, "url": url, "retrieved_at": retrieved_at, "reason": str(exc)})
                continue
            if expected_ids is not None and set(rows) != expected_ids:
                blockers.append(f"{code}: achievement ID set differs between public language snapshots")
            if expected_ids is None:
                expected_ids = set(rows)
            for api_name, fields in rows.items():
                values.setdefault(api_name, {})[code] = fields
            sources.append({
                "kind": "steam-public-achievements",
                "url": url,
                "language": code,
                "retrieved_at": retrieved_at,
                "achievement_count": len(rows),
                "note": "Original achievement identities and text from Steam structured public data.",
            })
        if not sources:
            details = "; ".join(f"{item['language']}: {item['reason']}" for item in unavailable)
            raise ValueError("cannot obtain public achievements; provide a real schema or retry when data is available: " + details)
        document = TextDocument(values)
        available_languages = document.languages
        # Partial language fields are retained for review, but cannot become a formal submission.
        for api_name, translations in values.items():
            for index, field in enumerate(("name", "description")):
                populated = [code for code in available_languages if translations.get(code, ("", ""))[index].strip()]
                if populated and len(populated) != len(available_languages):
                    blockers.append(f"{api_name}: inconsistent public {field} coverage")
        return {
            "version": 1,
            "app_id": app_id,
            "languages": list(available_languages),
            "achievements": {
                api_name: {
                    code: {"name": text[0], "description": text[1]}
                    for code, text in translations.items()
                }
                for api_name, translations in sorted(values.items())
            },
            "sources": sources,
            "unavailable_languages": unavailable,
            "submission_blockers": blockers,
            "limitations": PUBLIC_LIMITATIONS,
        }


def document_from_snapshot(snapshot: dict[str, Any], app_id: str) -> TextDocument:
    if snapshot.get("version") != 1 or snapshot.get("app_id") != app_id:
        raise ValueError("public snapshot does not match the project")
    values = {
        api_name: {code: (fields["name"], fields["description"]) for code, fields in translations.items()}
        for api_name, translations in snapshot["achievements"].items()
    }
    document = TextDocument(values)
    if list(document.languages) != snapshot.get("languages"):
        raise ValueError("public snapshot language metadata does not match its text")
    return document
