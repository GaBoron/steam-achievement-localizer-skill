from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable


REPOSITORY = "GaBoron/steam-achievement-translation-library"
RAW_ROOT = f"https://raw.githubusercontent.com/{REPOSITORY}/main"
INDEX_URL = f"{RAW_ROOT}/index.json"
MAX_INDEX_BYTES = 8 * 1024 * 1024
MAX_SCHEMA_BYTES = 32 * 1024 * 1024
USER_AGENT = (
    "steam-achievement-localizer-skill "
    "(+https://github.com/GaBoron/steam-achievement-localizer-skill)"
)


class LibraryError(RuntimeError):
    pass


@dataclass(frozen=True)
class LibraryMatch:
    app_id: str
    game_name: str
    languages: tuple[str, ...]
    schema_file: str
    sha256: str
    file_size_bytes: int
    source_url: str


@dataclass(frozen=True)
class DownloadedReference:
    match: LibraryMatch
    payload: bytes
    path: Path


def _primary_variant(entry: dict[str, Any]) -> dict[str, Any]:
    variants = entry.get("schema_files")
    if variants is None:
        return entry
    if not isinstance(variants, list):
        raise LibraryError("translation-library schema_files is not an array")
    primary = [item for item in variants if isinstance(item, dict) and item.get("primary") is True]
    if len(primary) != 1:
        raise LibraryError("translation-library entry does not have exactly one primary variant")
    return primary[0]


def parse_match(payload: bytes, app_id: str) -> LibraryMatch | None:
    try:
        index = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LibraryError(f"translation-library index is invalid: {exc}") from exc
    if not isinstance(index, dict) or index.get("version") != 1:
        raise LibraryError("translation-library index must use version 1")
    entries = index.get("entries")
    if not isinstance(entries, list):
        raise LibraryError("translation-library index has no entries array")
    entry = next(
        (
            item
            for item in entries
            if isinstance(item, dict) and str(item.get("game_id") or "") == app_id
        ),
        None,
    )
    if entry is None:
        return None
    variant = _primary_variant(entry)
    schema_file = str(variant.get("schema_file") or "")
    schema_path = PurePosixPath(schema_file)
    expected = f"files/{app_id}/UserGameStatsSchema_{app_id}.bin"
    if schema_path.is_absolute() or ".." in schema_path.parts or schema_file != expected:
        raise LibraryError(f"unexpected primary schema path: {schema_file!r}")
    digest = str(variant.get("sha256") or "").casefold()
    size = variant.get("file_size_bytes")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise LibraryError("translation-library entry has an invalid SHA-256")
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_SCHEMA_BYTES:
        raise LibraryError("translation-library entry has an invalid file size")
    languages = entry.get("languages")
    if not isinstance(languages, list):
        raise LibraryError("translation-library entry has an invalid languages list")
    source_url = f"{RAW_ROOT}/{urllib.parse.quote(schema_file, safe='/')}"
    return LibraryMatch(
        app_id=app_id,
        game_name=str(entry.get("game_name") or ""),
        languages=tuple(str(language).casefold() for language in languages),
        schema_file=schema_file,
        sha256=digest,
        file_size_bytes=size,
        source_url=source_url,
    )


class TranslationLibraryClient:
    def __init__(self, opener: Callable[..., Any] | None = None) -> None:
        self._opener = opener or urllib.request.urlopen

    def _read(self, url: str, limit: int) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._opener(request, timeout=20) as response:
                payload = response.read(limit + 1)
        except (OSError, TimeoutError) as exc:
            raise LibraryError(f"cannot fetch {url}: {exc}") from exc
        if len(payload) > limit:
            raise LibraryError(f"response exceeds the {limit}-byte safety limit: {url}")
        return payload

    def lookup(self, app_id: str) -> LibraryMatch | None:
        return parse_match(self._read(INDEX_URL, MAX_INDEX_BYTES), app_id)

    def download(self, match: LibraryMatch, destination: Path) -> DownloadedReference:
        payload = self._read(match.source_url, match.file_size_bytes)
        if len(payload) != match.file_size_bytes:
            raise LibraryError(
                f"translation-library file size mismatch: expected {match.file_size_bytes}, got {len(payload)}"
            )
        digest = hashlib.sha256(payload).hexdigest()
        if digest != match.sha256:
            raise LibraryError(
                f"translation-library SHA-256 mismatch: expected {match.sha256}, got {digest}"
            )
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return DownloadedReference(match, payload, destination)
