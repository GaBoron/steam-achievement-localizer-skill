from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .bkv import SchemaDocument


LANGUAGE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
UNSAFE_TEXT_RE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class TranslationEntry:
    name: str
    description: str


@dataclass(frozen=True)
class ReferenceDocument:
    label: str
    document: SchemaDocument


def validate_language(value: str) -> str:
    language = str(value or "").strip().casefold()
    if language in {"token", "tokens"} or not LANGUAGE_RE.fullmatch(language):
        raise ValueError(f"invalid Steam language code: {value!r}")
    return language


def _validate_text(value: str, api_name: str, field: str) -> str:
    if UNSAFE_TEXT_RE.search(value):
        raise ValueError(
            f"{api_name} {field} contains a NUL, line break, tab, or control character"
        )
    return value.strip()


def _reference_prefix(label: str) -> str:
    prefix = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_")
    if not prefix:
        raise ValueError("reference label must contain letters or digits")
    return prefix


def write_translation_draft(
    source: SchemaDocument,
    target_language: str,
    path: Path,
    references: tuple[ReferenceDocument, ...] = (),
) -> None:
    language = validate_language(target_language)
    fieldnames = ["api_name"]
    for source_language in source.languages:
        fieldnames.extend(
            [f"{source_language}_name", f"{source_language}_description"]
        )
    reference_maps: list[
        tuple[str, SchemaDocument, dict[str, dict[str, tuple[str, str]]]]
    ] = []
    reference_prefixes: set[str] = set()
    for reference in references:
        prefix = _reference_prefix(reference.label)
        if prefix in reference_prefixes:
            raise ValueError(f"duplicate reference label: {reference.label!r}")
        reference_prefixes.add(prefix)
        reference_maps.append(
            (prefix, reference.document, reference.document.translations_by_id())
        )
        for source_language in reference.document.languages:
            fieldnames.extend(
                [
                    f"{prefix}_{source_language}_name",
                    f"{prefix}_{source_language}_description",
                ]
            )
    fieldnames.extend(["target_name", "target_description", "translation_notes"])

    source_map = source.translations_by_id()
    rows: list[dict[str, str]] = []
    for achievement in source.achievements:
        row: dict[str, str] = {"api_name": achievement.api_name}
        values = source_map[achievement.api_name]
        for source_language in source.languages:
            name, description = values.get(source_language, ("", ""))
            row[f"{source_language}_name"] = name
            row[f"{source_language}_description"] = description

        target_name, target_description = values.get(language, ("", ""))
        for prefix, reference_document, reference_map in reference_maps:
            reference_values = reference_map.get(achievement.api_name, {})
            for source_language in reference_document.languages:
                name, description = reference_values.get(source_language, ("", ""))
                row[f"{prefix}_{source_language}_name"] = name
                row[f"{prefix}_{source_language}_description"] = description
            if not target_name or not target_description:
                reference_target = reference_values.get(language, ("", ""))
                target_name = target_name or reference_target[0]
                target_description = target_description or reference_target[1]

        row["target_name"] = target_name
        row["target_description"] = target_description
        row["translation_notes"] = ""
        rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_translations(
    path: Path, expected_ids: set[str]
) -> dict[str, TranslationEntry]:
    entries: dict[str, TranslationEntry] = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"api_name", "target_name", "target_description"}
        missing_columns = required - set(reader.fieldnames or ())
        if missing_columns:
            raise ValueError(
                "translation CSV is missing columns: " + ", ".join(sorted(missing_columns))
            )
        for row_number, row in enumerate(reader, 2):
            api_name = str(row.get("api_name") or "").strip()
            if not api_name:
                raise ValueError(f"translation CSV row {row_number} has no api_name")
            if api_name in entries:
                raise ValueError(f"translation CSV contains duplicate ID {api_name!r}")
            name = _validate_text(str(row.get("target_name") or ""), api_name, "name")
            description = _validate_text(
                str(row.get("target_description") or ""), api_name, "description"
            )
            if not name or not description:
                raise ValueError(f"translation is incomplete for {api_name!r}")
            entries[api_name] = TranslationEntry(name, description)

    actual_ids = set(entries)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        details = []
        if missing:
            details.append("missing IDs: " + ", ".join(missing))
        if extra:
            details.append("extra IDs: " + ", ".join(extra))
        raise ValueError("translation ID set does not match source; " + "; ".join(details))
    return entries


def write_research_template(
    path: Path,
    app_id: str,
    target_language: str,
    source_languages: tuple[str, ...],
    *,
    network_access: str,
    online_sources: list[dict[str, str]] | None = None,
    notes: list[str] | None = None,
) -> None:
    payload = {
        "version": 1,
        "app_id": app_id,
        "target_language": target_language,
        "network_access": network_access,
        "source_schema_languages": list(source_languages),
        "consulted_schema_languages": [],
        "online_sources": online_sources or [],
        "notes": notes or [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_research(
    path: Path,
    app_id: str,
    target_language: str,
    source_languages: tuple[str, ...],
) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read research manifest {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("research manifest must use version 1")
    if str(payload.get("app_id") or "") != app_id:
        raise ValueError("research manifest app_id does not match the project")
    if str(payload.get("target_language") or "").casefold() != target_language:
        raise ValueError("research manifest target_language does not match the project")

    consulted = {
        str(language).casefold()
        for language in payload.get("consulted_schema_languages", [])
        if str(language).strip()
    }
    missing_languages = set(source_languages) - consulted
    if missing_languages:
        raise ValueError(
            "research manifest does not confirm review of every schema language: "
            + ", ".join(sorted(missing_languages))
        )

    network_access = str(payload.get("network_access") or "").casefold()
    if network_access not in {"available", "unavailable"}:
        raise ValueError("research manifest network_access must be available or unavailable")
    online_sources = payload.get("online_sources")
    if not isinstance(online_sources, list):
        raise ValueError("research manifest online_sources must be an array")
    for item in online_sources:
        if not isinstance(item, dict):
            raise ValueError("each online source must be an object")
        url = str(item.get("url") or "")
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError(f"online source has an invalid URL: {url!r}")
    if network_access == "available" and not online_sources:
        raise ValueError(
            "network access is available, but no online translation source was recorded"
        )
    return payload
