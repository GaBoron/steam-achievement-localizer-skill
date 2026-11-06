"""The library's standalone format 2 display-text contract (no BIN metadata)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol


MAX_JSON_BYTES = 32 * 1024 * 1024
LANGUAGE_RE = re.compile(r"[a-z][a-z0-9_]{1,31}")
VARIANT_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
TextMap = dict[str, dict[str, tuple[str, str]]]


class TextSource(Protocol):
    @property
    def languages(self) -> tuple[str, ...]: ...

    def translations_by_id(self) -> TextMap: ...

    def coverage(self) -> dict[str, dict[str, int]]: ...


def validate_app_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > 4294967295:
        raise ValueError("invalid Steam app ID")
    return value


def validate_variant(value: str) -> str:
    if not isinstance(value, str) or not VARIANT_RE.fullmatch(value):
        raise ValueError("invalid variant ID")
    return value


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def validate_translation(payload: Any, *, allow_incomplete: bool = False) -> dict[str, Any]:
    required = {"version", "app_id", "variant_id", "languages", "achievements"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("format 2 JSON must contain exactly version, app_id, variant_id, languages, achievements")
    if type(payload["version"]) is not int or payload["version"] != 2:
        raise ValueError("standalone JSON must use version 2")
    validate_app_id(payload["app_id"])
    validate_variant(payload["variant_id"])
    languages = payload["languages"]
    if (
        not isinstance(languages, list) or not 1 <= len(languages) <= 64
        or any(not isinstance(code, str) or not LANGUAGE_RE.fullmatch(code) for code in languages)
        or languages != sorted(set(languages))
    ):
        raise ValueError("languages must be sorted, unique Steam language codes (1 to 64)")
    achievements = payload["achievements"]
    if not isinstance(achievements, dict) or not 1 <= len(achievements) <= 10000:
        raise ValueError("JSON must contain 1 to 10000 achievements")
    issues: list[str] = []
    for api_name, achievement in achievements.items():
        if (
            not isinstance(api_name, str) or not api_name.strip() or len(api_name) > 512
            or any(ord(char) < 32 or ord(char) == 127 for char in api_name)
        ):
            raise ValueError("invalid achievement API name")
        if not isinstance(achievement, dict) or set(achievement) != {"translations"}:
            raise ValueError(f"{api_name} must contain translations only")
        translations = achievement["translations"]
        if not isinstance(translations, dict) or set(translations) != set(languages):
            raise ValueError(f"{api_name}: translation languages do not match languages")
        for language, fields in translations.items():
            if not isinstance(fields, dict) or set(fields) != {"name", "description"}:
                raise ValueError(f"{api_name}.{language} must contain name and description only")
            for field, text in fields.items():
                if not isinstance(text, str) or "\0" in text or len(text) > 65536:
                    raise ValueError(f"{api_name}.{language}.{field} must be text without NUL (at most 65536 characters)")
        if not allow_incomplete:
            for field in ("name", "description"):
                missing = [code for code in languages if not translations[code][field].strip()]
                if missing and len(missing) != len(languages):
                    issues.append(f"{api_name} {field} missing " + ", ".join(missing))
    if issues:
        raise ValueError("localized output has inconsistent language coverage: " + "; ".join(issues))
    if len(json_bytes(payload)) > MAX_JSON_BYTES:
        raise ValueError("translation JSON exceeds 32 MiB")
    return payload


def decode_translation(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("translation JSON exceeds 32 MiB")
    try:
        payload = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid UTF-8 translation JSON: {exc}") from exc
    return validate_translation(payload)


def render_translation(app_id: str, variant_id: str, values: TextMap, *, allow_incomplete: bool = False) -> dict[str, Any]:
    languages = sorted({code for translations in values.values() for code in translations})
    payload = {
        "version": 2,
        "app_id": app_id,
        "variant_id": variant_id,
        "languages": languages,
        "achievements": {
            api_name: {
                "translations": {
                    code: {
                        "name": translations.get(code, ("", ""))[0],
                        "description": translations.get(code, ("", ""))[1],
                    }
                    for code in languages
                }
            }
            for api_name, translations in sorted(values.items())
        },
    }
    return validate_translation(payload, allow_incomplete=allow_incomplete)


@dataclass(frozen=True)
class TextDocument:
    """Display text without inventing Binary KeyValues nodes."""

    values: TextMap

    @classmethod
    def from_translation(cls, payload: dict[str, Any]) -> "TextDocument":
        validate_translation(payload)
        return cls({
            api_name: {
                code: (fields["name"], fields["description"])
                for code, fields in achievement["translations"].items()
            }
            for api_name, achievement in payload["achievements"].items()
        })

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(sorted({code for translations in self.values.values() for code in translations}))

    def translations_by_id(self) -> TextMap:
        return {api_name: dict(translations) for api_name, translations in self.values.items()}

    def coverage(self) -> dict[str, dict[str, int]]:
        result = {}
        for code in self.languages:
            fields = [translations.get(code, ("", "")) for translations in self.values.values()]
            result[code] = {
                "names": sum(bool(name.strip()) for name, _ in fields),
                "descriptions": sum(bool(description.strip()) for _, description in fields),
                "complete_achievements": sum(bool(name.strip() and description.strip()) for name, description in fields),
            }
        return result
