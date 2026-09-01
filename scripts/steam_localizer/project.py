from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bkv import SchemaDocument, sha256
from .library import LibraryError, TranslationLibraryClient
from .translations import (
    ReferenceDocument,
    load_translations,
    validate_language,
    validate_research,
    write_research_template,
    write_translation_draft,
)


SCHEMA_NAME_RE = re.compile(r"UserGameStatsSchema_(\d+)\.bin$")
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    source: Path
    manifest: Path
    translations: Path
    research: Path
    final_bin: Path
    final_zip: Path
    final_report: Path

    @classmethod
    def create(cls, root: Path, app_id: str) -> "ProjectPaths":
        root = Path(root).expanduser().resolve()
        filename = f"UserGameStatsSchema_{app_id}.bin"
        return cls(
            root=root,
            source=root / "input" / filename,
            manifest=root / "work" / "manifest.json",
            translations=root / "work" / "translations.csv",
            research=root / "work" / "sources.json",
            final_bin=root / "final" / filename,
            final_zip=root / "final" / f"UserGameStatsSchema_{app_id}.zip",
            final_report=root / "final" / "report.json",
        )


def _app_id_from_path(path: Path) -> str:
    match = SCHEMA_NAME_RE.fullmatch(Path(path).name)
    if match is None:
        raise ValueError("schema filename must be UserGameStatsSchema_<app_id>.bin")
    return match.group(1)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_zip(path: Path, member_name: str, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member_name, payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def prepare_project(
    schema_path: Path,
    target_language: str,
    workspace: Path | None = None,
    *,
    offline: bool = False,
    library_client: TranslationLibraryClient | None = None,
) -> dict[str, Any]:
    schema_path = Path(schema_path).expanduser().resolve()
    if not schema_path.is_file():
        raise ValueError(f"schema file does not exist: {schema_path}")
    app_id = _app_id_from_path(schema_path)
    language = validate_language(target_language)
    root = workspace or (Path.cwd() / "localization" / f"{app_id}-{language}")
    paths = ProjectPaths.create(root, app_id)
    if paths.root.exists() and any(paths.root.iterdir()):
        raise ValueError(
            f"workspace is not empty: {paths.root}; reuse it with apply or choose a new path"
        )

    source_payload = schema_path.read_bytes()
    source_document = SchemaDocument.from_bytes(source_payload)
    _atomic_write(paths.source, source_payload)

    references: list[ReferenceDocument] = []
    library_metadata: dict[str, Any] = {"checked": False, "match": None}
    research_sources: list[dict[str, str]] = []
    research_notes: list[str] = []
    network_access = "unavailable" if offline else "available"
    if offline:
        research_notes.append("Translation-library lookup skipped in offline mode.")
    else:
        client = library_client or TranslationLibraryClient()
        try:
            match = client.lookup(app_id)
            library_metadata["checked"] = True
            if match is None:
                research_notes.append(
                    "The connected translation library has no entry for this app ID."
                )
            else:
                reference_path = (
                    paths.root
                    / "work"
                    / "references"
                    / "translation-library"
                    / paths.source.name
                )
                downloaded = client.download(match, reference_path)
                reference_document = SchemaDocument.from_bytes(downloaded.payload)
                references.append(ReferenceDocument("library", reference_document))
                library_metadata["match"] = {
                    "game_name": match.game_name,
                    "languages": list(match.languages),
                    "schema_file": match.schema_file,
                    "sha256": match.sha256,
                    "source_url": match.source_url,
                    "local_reference": str(reference_path.relative_to(paths.root)),
                }
                research_sources.append(
                    {
                        "kind": "community-translation-library",
                        "url": match.source_url,
                        "note": "Downloaded verified primary schema as a translation reference.",
                    }
                )
        except (LibraryError, ValueError) as exc:
            network_access = "unavailable"
            library_metadata["error"] = str(exc)
            research_notes.append(f"Translation-library lookup failed: {exc}")

    write_translation_draft(
        source_document,
        language,
        paths.translations,
        tuple(references),
    )
    write_research_template(
        paths.research,
        app_id,
        language,
        source_document.languages,
        network_access=network_access,
        online_sources=research_sources,
        notes=research_notes,
    )
    manifest = {
        "version": MANIFEST_VERSION,
        "app_id": app_id,
        "target_language": language,
        "original_source": str(schema_path),
        "source_file": str(paths.source.relative_to(paths.root)),
        "source_sha256": sha256(source_payload),
        "source_size": len(source_payload),
        "achievement_count": len(source_document.achievements),
        "source_languages": list(source_document.languages),
        "source_language_coverage": source_document.coverage(),
        "translation_library": library_metadata,
    }
    _write_json(paths.manifest, manifest)
    return {
        "status": "prepared",
        "workspace": str(paths.root),
        "app_id": app_id,
        "target_language": language,
        "achievement_count": len(source_document.achievements),
        "source_languages": list(source_document.languages),
        "translation_library_match": library_metadata.get("match") is not None,
        "translations_csv": str(paths.translations),
        "research_manifest": str(paths.research),
        "next_step": (
            "Review every source-language column, prioritize achievement-specific online "
            "context and verified existing translations, record that evidence in "
            "sources.json, and fill each target field used by the corresponding source "
            "achievement."
        ),
    }


def _load_manifest(workspace: Path) -> tuple[dict[str, Any], ProjectPaths]:
    workspace = Path(workspace).expanduser().resolve()
    manifest_path = workspace / "work" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read project manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("project manifest must use version 1")
    app_id = str(manifest.get("app_id") or "")
    if not app_id.isdigit():
        raise ValueError("project manifest has an invalid app_id")
    return manifest, ProjectPaths.create(workspace, app_id)


def _without_target(
    values: dict[str, dict[str, tuple[str, str]]], target_language: str
) -> dict[str, dict[str, tuple[str, str]]]:
    return {
        api_name: {
            language: text
            for language, text in translations.items()
            if language != target_language
        }
        for api_name, translations in values.items()
    }


def apply_project(workspace: Path) -> dict[str, Any]:
    manifest, paths = _load_manifest(workspace)
    target_language = validate_language(str(manifest.get("target_language") or ""))
    source_payload = paths.source.read_bytes()
    if sha256(source_payload) != str(manifest.get("source_sha256") or ""):
        raise ValueError("workspace source file has changed since prepare")
    source_document = SchemaDocument.from_bytes(source_payload)
    source_languages = tuple(str(value) for value in manifest.get("source_languages", []))
    if source_document.languages != source_languages:
        raise ValueError("workspace source languages do not match the project manifest")
    research = validate_research(
        paths.research,
        str(manifest["app_id"]),
        target_language,
        source_languages,
    )
    expected_ids = {achievement.api_name for achievement in source_document.achievements}
    translations = load_translations(paths.translations, expected_ids)
    before = source_document.translations_by_id()
    changed_fields = 0
    for api_name, entry in translations.items():
        changed_fields += source_document.set_translation(
            api_name, target_language, entry.name, entry.description
        )

    localized_payload = source_document.to_bytes()
    localized_document = SchemaDocument.from_bytes(localized_payload)
    after = localized_document.translations_by_id()
    if _without_target(before, target_language) != _without_target(after, target_language):
        raise ValueError("a non-target language changed while applying translations")
    if len(localized_document.achievements) != len(source_document.achievements):
        raise ValueError("achievement count changed while applying translations")
    coverage_issues = localized_document.text_coverage_issues()
    if coverage_issues:
        details = []
        for issue in coverage_issues:
            details.append(
                f"{issue['api_name']} {issue['field']} missing "
                + ", ".join(issue["missing_languages"])
            )
        raise ValueError(
            "localized output has inconsistent language coverage: " + "; ".join(details)
        )

    _atomic_write(paths.final_bin, localized_payload)
    _atomic_zip(paths.final_zip, paths.final_bin.name, localized_payload)
    with zipfile.ZipFile(paths.final_zip) as archive:
        if archive.namelist() != [paths.final_bin.name]:
            raise ValueError("final ZIP does not contain exactly the canonical schema file")
        if archive.read(paths.final_bin.name) != localized_payload:
            raise ValueError("final ZIP payload does not match the localized schema")

    report = {
        "status": "complete",
        "app_id": manifest["app_id"],
        "target_language": target_language,
        "original_source": manifest.get("original_source"),
        "original_was_modified": False,
        "source_sha256": sha256(source_payload),
        "localized_sha256": sha256(localized_payload),
        "localized_size": len(localized_payload),
        "roundtrip_equal": True,
        "achievement_count": len(localized_document.achievements),
        "target_language_coverage_count": len(localized_document.achievements),
        "target_language_coverage": localized_document.coverage()[target_language],
        "target_language_nodes_changed": changed_fields,
        "source_languages_consulted": research["consulted_schema_languages"],
        "online_sources": research["online_sources"],
        "translation_library": manifest.get("translation_library"),
        "final_bin": str(paths.final_bin),
        "final_zip": str(paths.final_zip),
        "report": str(paths.final_report),
    }
    report["final_zip_sha256"] = hashlib.sha256(paths.final_zip.read_bytes()).hexdigest()
    _write_json(paths.final_report, report)
    return report
