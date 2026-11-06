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
from .public_data import PublicAchievementClient, document_from_snapshot
from .translation_json import (
    TextDocument,
    TextSource,
    decode_translation,
    json_bytes,
    render_translation,
    unique_object,
    validate_app_id,
    validate_variant,
)
from .translations import (
    ReferenceDocument,
    load_translations,
    validate_language,
    validate_placeholders,
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
    final_json: Path
    public_source: Path
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
            final_json=root / "final" / f"UserGameStatsSchema_{app_id}.json",
            public_source=root / "input" / "public-achievements.json",
            final_report=root / "final" / "report.json",
        )


def _app_id_from_path(path: Path) -> str:
    match = SCHEMA_NAME_RE.fullmatch(Path(path).name)
    if match is None:
        raise ValueError("schema filename must be UserGameStatsSchema_<app_id>.bin")
    return validate_app_id(match.group(1))


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_zip(path: Path, member_name: str, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with zipfile.ZipFile(temporary, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, payload)
    os.replace(temporary, path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def prepare_project(
    schema_path: Path | None,
    target_language: str,
    workspace: Path | None = None,
    *,
    offline: bool = False,
    library_client: TranslationLibraryClient | None = None,
    app_id: str | None = None,
    variant_id: str = "default",
    source_languages: tuple[str, ...] = ("english",),
    public_client: PublicAchievementClient | None = None,
) -> dict[str, Any]:
    variant_id = validate_variant(variant_id)
    if schema_path is not None:
        if app_id is not None:
            raise ValueError("provide either --schema or --app-id, not both")
        schema_path = Path(schema_path).expanduser().resolve()
        if not schema_path.is_file():
            raise ValueError(f"schema file does not exist: {schema_path}")
        app_id = _app_id_from_path(schema_path)
    else:
        app_id = validate_app_id(app_id)
        if offline:
            raise ValueError("--app-id requires network access to obtain public achievement data")
    language = validate_language(target_language)
    root = workspace or (Path.cwd() / "localization" / f"{app_id}-{language}")
    paths = ProjectPaths.create(root, app_id)
    if paths.root.exists() and any(paths.root.iterdir()):
        raise ValueError(
            f"workspace is not empty: {paths.root}; reuse it with apply or choose a new path"
        )

    snapshot = None
    if schema_path is not None:
        source_payload = schema_path.read_bytes()
        source_document: TextSource = SchemaDocument.from_bytes(source_payload)
        source_path = paths.source
        source_kind = "BIN-derived"
    else:
        snapshot = (public_client or PublicAchievementClient()).fetch(app_id, source_languages)
        source_document = document_from_snapshot(snapshot, app_id)
        # Validate limits and text types even when partial source fields block submission.
        render_translation(app_id, variant_id, source_document.translations_by_id(), allow_incomplete=True)
        source_payload = json_bytes(snapshot)
        source_path = paths.public_source
        source_kind = "public-data-derived"
    _atomic_write(source_path, source_payload)

    references: list[ReferenceDocument] = []
    library_metadata: dict[str, Any] = {"checked": False, "match": None}
    research_sources: list[dict[str, str]] = []
    research_notes: list[str] = []
    network_access = "unavailable" if offline else "available"
    if snapshot is not None:
        research_sources.extend(snapshot["sources"])
        research_notes.extend(snapshot["limitations"])
    if offline:
        research_notes.append("Translation-library lookup skipped in offline mode.")
    else:
        client = library_client or TranslationLibraryClient()
        try:
            match = client.lookup(app_id, variant_id)
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
                    / Path(match.schema_file).name
                )
                downloaded = client.download(match, reference_path)
                if match.artifact_format == "json":
                    reference_payload = decode_translation(downloaded.payload)
                    if reference_payload["app_id"] != app_id or reference_payload["variant_id"] != variant_id:
                        raise ValueError("translation-library JSON app/variant does not match the project")
                    reference_document = TextDocument.from_translation(reference_payload)
                else:
                    reference_document = SchemaDocument.from_bytes(downloaded.payload)
                reference_ids = set(reference_document.translations_by_id())
                if match.achievement_count is not None and len(reference_ids) != match.achievement_count:
                    raise ValueError("translation-library achievement count does not match its catalog")
                if set(reference_document.languages) != set(match.languages):
                    raise ValueError("translation-library languages do not match its catalog")
                references.append(ReferenceDocument("library", reference_document))
                library_metadata["match"] = {
                    "game_name": match.game_name,
                    "languages": list(match.languages),
                    "schema_file": match.schema_file,
                    "sha256": match.sha256,
                    "source_url": match.source_url,
                    "local_reference": str(reference_path.relative_to(paths.root)),
                    "format": match.artifact_format,
                    "variant_id": match.variant_id,
                    "achievement_ids_match": reference_ids == set(source_document.translations_by_id()),
                }
                if snapshot is not None and reference_ids != set(source_document.translations_by_id()):
                    snapshot["submission_blockers"].append("public achievement IDs conflict with the selected translation-library variant")
                research_sources.append(
                    {
                        "kind": "community-translation-library",
                        "url": match.source_url,
                        "note": "Downloaded verified library variant as a translation reference.",
                    }
                )
        except (LibraryError, ValueError) as exc:
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
    if snapshot is not None:
        source_payload = json_bytes(snapshot)
        _atomic_write(source_path, source_payload)
    manifest = {
        "version": MANIFEST_VERSION,
        "app_id": app_id,
        "target_language": language,
        "variant_id": variant_id,
        "source_kind": source_kind,
        "original_source": str(schema_path) if schema_path is not None else None,
        "source_file": str(source_path.relative_to(paths.root)),
        "source_size": len(source_payload),
        "achievement_count": len(source_document.translations_by_id()),
        "source_languages": list(source_document.languages),
        "source_language_coverage": source_document.coverage(),
        "translation_library": library_metadata,
    }
    if snapshot is None:
        manifest["source_sha256"] = sha256(source_payload)
    else:
        manifest["source_content_sha256"] = sha256(source_payload)
        manifest["public_data"] = {key: snapshot[key] for key in ("sources", "unavailable_languages", "limitations", "submission_blockers")}
    _write_json(paths.manifest, manifest)
    return {
        "status": "prepared",
        "workspace": str(paths.root),
        "app_id": app_id,
        "target_language": language,
        "source_kind": source_kind,
        "variant_id": variant_id,
        "submission_blockers": snapshot["submission_blockers"] if snapshot else [],
        "achievement_count": len(source_document.translations_by_id()),
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
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read project manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("project manifest must use version 1")
    app_id = str(manifest.get("app_id") or "")
    validate_app_id(app_id)
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
    app_id = manifest["app_id"]
    variant_id = validate_variant(manifest.get("variant_id", "default"))
    target_language = validate_language(str(manifest.get("target_language") or ""))
    source_kind = manifest.get("source_kind", "BIN-derived")
    if source_kind not in {"BIN-derived", "public-data-derived"}:
        raise ValueError("unknown project source_kind")
    is_bin = source_kind == "BIN-derived"
    source_path = paths.source if is_bin else paths.public_source
    hash_key = "source_sha256" if is_bin else "source_content_sha256"
    source_payload = source_path.read_bytes()
    if sha256(source_payload) != manifest.get(hash_key):
        raise ValueError("workspace source file has changed since prepare")
    snapshot = None
    if is_bin:
        source_document = SchemaDocument.from_bytes(source_payload)
    else:
        snapshot = json.loads(source_payload.decode("utf-8"), object_pairs_hook=unique_object)
        source_document = document_from_snapshot(snapshot, app_id)
        if snapshot["submission_blockers"]:
            _write_json(paths.final_report, {
                "status": "blocked", "source_kind": source_kind, "app_id": app_id,
                "json_submission_eligible": False,
                "submission_blockers": snapshot["submission_blockers"],
                "public_data": snapshot,
            })
            raise ValueError("public source cannot be submitted: " + "; ".join(snapshot["submission_blockers"]))
    source_languages = tuple(manifest.get("source_languages", []))
    if source_document.languages != source_languages:
        raise ValueError("workspace source languages do not match the project manifest")
    before = source_document.translations_by_id()
    if len(before) != manifest.get("achievement_count"):
        raise ValueError("workspace achievement count does not match the project manifest")
    research = validate_research(paths.research, app_id, target_language, source_languages)
    translations = load_translations(paths.translations, set(before))
    validate_placeholders(before, target_language, translations)
    changed_fields = 0
    after = {api_name: dict(values) for api_name, values in before.items()}
    for api_name, entry in translations.items():
        if is_bin:
            changed_fields += source_document.set_translation(
                api_name, target_language, entry.name, entry.description
            )
        # When the only original language is the target, preserve its field pattern too.
        if set(before[api_name]) == {target_language}:
            for original, replacement in zip(before[api_name][target_language], (entry.name, entry.description)):
                if bool(original.strip()) != bool(replacement.strip()):
                    raise ValueError(f"{api_name}: target fields must preserve the source field pattern")
        after[api_name][target_language] = (entry.name, entry.description)

    localized_payload = None
    if is_bin:
        localized_payload = source_document.to_bytes()
        localized_document = SchemaDocument.from_bytes(localized_payload)
        after = localized_document.translations_by_id()
    else:
        localized_document = TextDocument(after)
    if _without_target(before, target_language) != _without_target(after, target_language):
        raise ValueError("a non-target language changed while applying translations")
    if set(after) != set(before):
        raise ValueError("achievement ID set changed while applying translations")
    translation_json = render_translation(app_id, variant_id, after)
    final_json_payload = json_bytes(translation_json)

    if is_bin:
        _atomic_write(paths.final_bin, localized_payload)
        _atomic_zip(paths.final_zip, paths.final_bin.name, localized_payload)
        with zipfile.ZipFile(paths.final_zip) as archive:
            if archive.namelist() != [paths.final_bin.name]:
                raise ValueError("final ZIP does not contain exactly the canonical schema file")
            if archive.read(paths.final_bin.name) != localized_payload:
                raise ValueError("final ZIP payload does not match the localized schema")
    _atomic_write(paths.final_json, final_json_payload)
    report = {
        "status": "complete",
        "source_kind": source_kind,
        "app_id": app_id,
        "variant_id": variant_id,
        "target_language": target_language,
        "json_format_version": 2,
        "json_submission_eligible": True,
        "submission_blockers": [],
        "achievement_count": len(after),
        "target_language_coverage_count": len(after),
        "target_language_coverage": localized_document.coverage()[target_language],
        "source_languages_consulted": research["consulted_schema_languages"],
        "online_sources": research["online_sources"],
        "translation_library": manifest.get("translation_library"),
        "final_json": str(paths.final_json),
        "report": str(paths.final_report),
    }
    if is_bin:
        report.update({
            "original_source": manifest.get("original_source"),
            "original_was_modified": False,
            "source_sha256": sha256(source_payload),
            "localized_sha256": sha256(localized_payload),
            "localized_size": len(localized_payload),
            "roundtrip_equal": True,
            "target_language_nodes_changed": changed_fields,
            "final_bin": str(paths.final_bin),
            "final_zip": str(paths.final_zip),
            "final_zip_sha256": hashlib.sha256(paths.final_zip.read_bytes()).hexdigest(),
        })
    else:
        report["source_content_sha256"] = manifest["source_content_sha256"]
        report["public_data"] = {key: snapshot[key] for key in ("sources", "unavailable_languages", "limitations")}
    _write_json(paths.final_report, report)
    return report
