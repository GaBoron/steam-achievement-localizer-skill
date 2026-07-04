#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TYPE_NAMES = {0: "BEGIN", 1: "STRING", 2: "INT32", 3: "FLOAT32", 4: "POINTER", 5: "WIDESTRING", 6: "COLOR", 7: "UINT64", 8: "END"}
SKILL_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = SKILL_ROOT / "VERSION"
REPO_URL = "https://github.com/GaBoron/steam-achievement-localizer-skill.git"
TAGS_API_URL = "https://api.github.com/repos/GaBoron/steam-achievement-localizer-skill/tags?per_page=100"
VERSION_CACHE_NAME = "version-check.json"


@dataclass
class Node:
    type_id: int
    name: str
    children: list["Node"] = field(default_factory=list)
    value: str | None = None
    raw_value: bytes = b""


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data, self.pos = data, 0

    def u8(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError("unexpected EOF reading type")
        v = self.data[self.pos]
        self.pos += 1
        return v

    def bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError("unexpected EOF reading value")
        v = self.data[self.pos:self.pos + n]
        self.pos += n
        return v

    def cbytes(self) -> bytes:
        end = self.data.find(b"\0", self.pos)
        if end < 0:
            raise EOFError("unterminated string")
        v = self.data[self.pos:end]
        self.pos = end + 1
        return v

    def cstr(self) -> str:
        return self.cbytes().decode("utf-8")


def parse_nodes(r: Reader) -> list[Node]:
    nodes: list[Node] = []
    while True:
        t = r.u8()
        if t == 8:
            return nodes
        if t not in TYPE_NAMES:
            raise ValueError(f"unknown type {t} at offset {r.pos - 1}")
        name = r.cstr()
        n = Node(t, name)
        if t == 0:
            n.children = parse_nodes(r)
        elif t == 1:
            raw = r.cbytes()
            n.raw_value = raw
            n.value = raw.decode("utf-8")
        elif t in (2, 3, 4, 6):
            n.raw_value = r.bytes(4)
        elif t == 7:
            n.raw_value = r.bytes(8)
        elif t == 5:
            raise NotImplementedError("WideString node encountered")
        nodes.append(n)


def cstr(s: str) -> bytes:
    return s.encode("utf-8") + b"\0"


def serialize(nodes: list[Node]) -> bytes:
    out = bytearray()
    for n in nodes:
        out.append(n.type_id)
        out.extend(cstr(n.name))
        if n.type_id == 0:
            out.extend(serialize(n.children))
        elif n.type_id == 1:
            out.extend(cstr(n.value if n.value is not None else n.raw_value.decode("utf-8")))
        elif n.type_id in (2, 3, 4, 6, 7):
            out.extend(n.raw_value)
        else:
            raise NotImplementedError(f"cannot serialize type {n.type_id}")
    out.append(8)
    return bytes(out)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def scalar(n: Node) -> Any:
    if n.type_id == 1:
        return n.value
    if n.type_id == 2:
        return struct.unpack("<i", n.raw_value)[0]
    if n.type_id == 3:
        return struct.unpack("<f", n.raw_value)[0]
    if n.type_id in (4, 6):
        return struct.unpack("<I", n.raw_value)[0]
    if n.type_id == 7:
        return struct.unpack("<Q", n.raw_value)[0]
    return None


def to_json(n: Node) -> dict[str, Any]:
    d: dict[str, Any] = {"type": TYPE_NAMES[n.type_id], "name": n.name}
    if n.type_id == 0:
        d["children"] = [to_json(c) for c in n.children]
    else:
        d["value"] = scalar(n)
        if n.type_id != 1:
            d["raw_hex"] = n.raw_value.hex()
    return d


def walk(nodes: list[Node]):
    for n in nodes:
        yield n
        if n.children:
            yield from walk(n.children)


def begins(n: Node, name: str) -> list[Node]:
    return [c for c in n.children if c.type_id == 0 and c.name == name]


def strings(n: Node, name: str) -> list[Node]:
    return [c for c in n.children if c.type_id == 1 and c.name == name]


def first_str(n: Node, name: str) -> str | None:
    s = strings(n, name)
    return (s[0].value or "") if s else None


def nested(n: Node, *names: str) -> Node | None:
    cur: Node | None = n
    for name in names:
        if cur is None:
            return None
        matches = begins(cur, name)
        cur = matches[0] if matches else None
    return cur


def achievement_nodes(nodes: list[Node]) -> list[Node]:
    out: list[Node] = []
    for bits in [n for n in walk(nodes) if n.type_id == 0 and n.name == "bits"]:
        for child in bits.children:
            if child.type_id == 0 and strings(child, "name") and nested(child, "display", "name") and nested(child, "display", "desc"):
                out.append(child)
    return out


def load_schema(path: Path) -> tuple[bytes, list[Node]]:
    data = path.read_bytes()
    r = Reader(data)
    nodes = parse_nodes(r)
    if r.pos != len(data):
        raise ValueError(f"parser stopped at {r.pos}, file size {len(data)}")
    return data, nodes


def achievement_rows(nodes: list[Node], lang: str) -> list[dict[str, Any]]:
    rows = []
    for i, ach in enumerate(achievement_nodes(nodes), 1):
        dn = nested(ach, "display", "name")
        dd = nested(ach, "display", "desc")
        assert dn and dd
        rows.append({
            "index": i,
            "node_key": ach.name,
            "api_name": first_str(ach, "name") or "",
            "english_name": first_str(dn, "english") or "",
            "english_description": first_str(dd, "english") or "",
            f"{lang}_name": first_str(dn, lang) or "",
            f"{lang}_description": first_str(dd, lang) or "",
        })
    return rows


def export_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = list(rows[0].keys()) if rows else ["index", "node_key", "api_name", "english_name", "english_description"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def export_missing_translation_csv(rows: list[dict[str, Any]], lang: str, path: Path) -> int:
    missing = [
        {
            "api_name": r.get("api_name", ""),
            "english_name": r.get("english_name", ""),
            "english_description": r.get("english_description", ""),
            "target_name": "",
            "target_description": "",
        }
        for r in rows
        if not r.get(f"{lang}_name", "").strip() or not r.get(f"{lang}_description", "").strip()
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["api_name", "english_name", "english_description", "target_name", "target_description"])
        w.writeheader()
        w.writerows(missing)
    return len(missing)


def pick(row: dict[str, str], keys: list[str]) -> str:
    for k in keys:
        if row.get(k, "").strip():
            return row[k].strip()
    return ""


@dataclass
class TranslationLoadResult:
    entries: dict[str, tuple[str, str]]
    sanitized_count: int = 0


def clean_translation_text(value: str) -> tuple[str, bool]:
    cleaned = re.sub(r"[\r\n\t]+", " ", value)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    return cleaned, cleaned != value


def load_translations(path: Path, lang: str) -> TranslationLoadResult:
    out: dict[str, tuple[str, str]] = {}
    sanitized_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = pick(row, ["api_name", "id", "achievement_id", "name"])
            target_name = pick(row, [f"{lang}_name", "target_name", "translated_name", "name_zh", "schinese_name"])
            target_desc = pick(row, [f"{lang}_description", "target_description", "translated_description", "description_zh", "schinese_description"])
            target_name, changed_name = clean_translation_text(target_name)
            target_desc, changed_desc = clean_translation_text(target_desc)
            sanitized_count += int(changed_name) + int(changed_desc)
            if key and (target_name or target_desc):
                out[key] = (target_name, target_desc)
    return TranslationLoadResult(out, sanitized_count)


def upsert_string(parent: Node, lang: str, value: str) -> bool:
    if not value:
        return False
    existing = strings(parent, lang)
    if existing:
        if existing[0].value == value:
            return False
        existing[0].value = value
        existing[0].raw_value = value.encode("utf-8")
        return True
    english = strings(parent, "english")
    at = parent.children.index(english[-1]) + 1 if english else len(parent.children)
    parent.children.insert(at, Node(1, lang, value=value, raw_value=value.encode("utf-8")))
    return True


def apply_translations(nodes: list[Node], translations: dict[str, tuple[str, str]], lang: str) -> int:
    changed = 0
    for ach in achievement_nodes(nodes):
        key = first_str(ach, "name")
        if not key or key not in translations:
            continue
        dn = nested(ach, "display", "name")
        dd = nested(ach, "display", "desc")
        if dn and upsert_string(dn, lang, translations[key][0]):
            changed += 1
        if dd and upsert_string(dd, lang, translations[key][1]):
            changed += 1
    return changed


def latin_residue(rows: list[dict[str, Any]], lang: str) -> int:
    rx = re.compile(r"[A-Za-z]{2,}")
    return sum(1 for r in rows if rx.search(r.get(f"{lang}_name", "")) or rx.search(r.get(f"{lang}_description", "")))


def empty_target_ids(rows: list[dict[str, Any]], lang: str) -> list[str]:
    return [
        str(r.get("api_name", ""))
        for r in rows
        if not r.get(f"{lang}_name", "").strip() or not r.get(f"{lang}_description", "").strip()
    ]


def semver_key(tag: str) -> tuple[int, ...]:
    cleaned = tag.strip().lstrip("vV")
    nums = re.findall(r"\d+", cleaned)
    return tuple(int(n) for n in nums) if nums else (-1,)


def run_git(args: list[str], cwd: Path, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, timeout=timeout, check=False)


def latest_tag_from_lines(lines: list[str]) -> str | None:
    tags: list[str] = []
    for line in lines:
        ref = line.strip().split()[-1] if line.strip() else ""
        if not ref.startswith("refs/tags/") or ref.endswith("^{}"):
            continue
        tags.append(ref.removeprefix("refs/tags/"))
    return sorted(tags, key=semver_key, reverse=True)[0] if tags else None


def latest_github_tag() -> tuple[str | None, str, str | None]:
    proc = subprocess.run(["git", "ls-remote", "--tags", "--refs", REPO_URL], text=True, capture_output=True, timeout=20, check=False)
    if proc.returncode == 0:
        tag = latest_tag_from_lines(proc.stdout.splitlines())
        if tag:
            return tag, "git ls-remote", None
    git_error = (proc.stderr or proc.stdout or "git ls-remote returned no tags").strip()
    try:
        with urllib.request.urlopen(TAGS_API_URL, timeout=20) as response:
            tags = [item["name"] for item in json.loads(response.read().decode("utf-8")) if item.get("name")]
        if tags:
            return sorted(tags, key=semver_key, reverse=True)[0], "GitHub tags API", git_error
    except Exception as exc:  # noqa: BLE001 - keep preflight diagnostics concise.
        return None, "unavailable", f"{git_error}; GitHub API failed: {exc}"
    return None, "unavailable", git_error


def default_version_cache_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "SteamAchievementLocalizerSkill" / VERSION_CACHE_NAME
    return Path.home() / ".cache" / "steam-achievement-localizer-skill" / VERSION_CACHE_NAME


def read_version_cache(cache_file: Path) -> dict[str, Any] | None:
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def write_version_cache(cache_file: Path, report: dict[str, Any]) -> None:
    if not report.get("github_latest_tag"):
        return
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def local_version() -> tuple[str | None, str]:
    if VERSION_FILE.exists():
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        if version:
            return version, str(VERSION_FILE)
    proc = run_git(["describe", "--tags", "--abbrev=0"], SKILL_ROOT)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip(), "git describe"
    return None, "unavailable"


def git_worktree_state() -> dict[str, Any]:
    root_proc = run_git(["rev-parse", "--show-toplevel"], SKILL_ROOT)
    if root_proc.returncode != 0:
        return {"inside_git_repository": False}
    root = Path(root_proc.stdout.strip())
    status_proc = run_git(["status", "--short"], root)
    branch_proc = run_git(["branch", "--show-current"], root)
    return {
        "inside_git_repository": True,
        "repository_root": str(root),
        "branch": branch_proc.stdout.strip(),
        "dirty": bool(status_proc.stdout.strip()),
        "status_short": status_proc.stdout.splitlines(),
    }


def build_version_report(max_age_hours: float = 24.0, force: bool = False, cache_file: Path | None = None) -> dict[str, Any]:
    local, source = local_version()
    cache_path = cache_file or default_version_cache_path()
    now = time.time()
    if not force and max_age_hours > 0:
        cached = read_version_cache(cache_path)
        if cached and cached.get("github_latest_tag") and cached.get("local_version") == local:
            checked_at = float(cached.get("checked_at_epoch", 0))
            age_seconds = now - checked_at
            if 0 <= age_seconds <= max_age_hours * 3600:
                report = dict(cached)
                report.update({
                    "local_version": local,
                    "local_version_source": source,
                    "versions_match": bool(local and report.get("github_latest_tag") and local == report.get("github_latest_tag")),
                    "cache_file": str(cache_path),
                    "cache_hit": True,
                    "cache_age_seconds": round(age_seconds, 3),
                    "checked_now": False,
                })
                report.update(git_worktree_state())
                return report
    latest, latest_source, error = latest_github_tag()
    report: dict[str, Any] = {
        "local_version": local,
        "local_version_source": source,
        "github_latest_tag": latest,
        "github_latest_tag_source": latest_source,
        "versions_match": bool(local and latest and local == latest),
        "check_error": error,
        "cache_file": str(cache_path),
        "cache_hit": False,
        "cache_age_seconds": None,
        "checked_now": True,
        "checked_at_epoch": now,
    }
    report.update(git_worktree_state())
    write_version_cache(cache_path, report)
    return report


def discover_steam_dirs() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("STEAM_DIR", "SteamPath"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value))
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Steam")
    candidates.extend([Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")])
    if os.name == "nt":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (r"Software\Valve\Steam", r"Software\WOW6432Node\Valve\Steam"):
                    try:
                        with winreg.OpenKey(hive, subkey) as key:
                            for value_name in ("SteamPath", "InstallPath"):
                                try:
                                    value, _ = winreg.QueryValueEx(key, value_name)
                                    if value:
                                        candidates.append(Path(value))
                                except FileNotFoundError:
                                    pass
                    except FileNotFoundError:
                        pass
        except Exception:
            pass
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate).lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(candidate)
    return unique


def resolve_schema(schema: Path | None, game_id: str | None, steam_dir: Path | None) -> tuple[Path, list[str]]:
    if schema:
        return schema, []
    if not game_id:
        raise SystemExit("provide --schema or --game-id")
    searched: list[str] = []
    steam_dirs = [steam_dir] if steam_dir else discover_steam_dirs()
    for base in steam_dirs:
        if base is None:
            continue
        candidate = base / "appcache" / "stats" / f"UserGameStatsSchema_{game_id}.bin"
        searched.append(str(candidate))
        if candidate.exists():
            return candidate, searched
    raise SystemExit("schema file not found. Searched:\n" + "\n".join(searched))


def find_schema_files(game_id: str | None = None, steam_dir: Path | None = None) -> dict[str, Any]:
    steam_dirs = [steam_dir] if steam_dir else discover_steam_dirs()
    matches: list[dict[str, Any]] = []
    stats_dirs: list[str] = []
    pattern = f"UserGameStatsSchema_{game_id}.bin" if game_id else "UserGameStatsSchema_*.bin"
    for base in steam_dirs:
        if base is None:
            continue
        stats_dir = base / "appcache" / "stats"
        stats_dirs.append(str(stats_dir))
        if not stats_dir.is_dir():
            continue
        for path in sorted(stats_dir.glob(pattern)):
            match = re.search(r"UserGameStatsSchema_(\d+)\.bin$", path.name)
            matches.append({
                "game_id": match.group(1) if match else None,
                "schema": str(path),
                "size": path.stat().st_size,
                "modified_epoch": path.stat().st_mtime,
            })
    return {
        "game_id": game_id,
        "steam_dirs": [str(p) for p in steam_dirs if p is not None],
        "stats_dirs": stats_dirs,
        "match_count": len(matches),
        "matches": matches,
    }


def copy_source_to_workspace(source: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / source.name
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return dest


def process_schema(
    input_path: Path,
    out_dir: Path,
    target_language: str,
    translations: Path | None = None,
    localized_bin: Path | None = None,
    strict_no_latin: bool = False,
) -> dict[str, Any]:
    data, nodes = load_schema(input_path)
    rebuilt = serialize(nodes)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    roundtrip_path = out_dir / f"{stem}.roundtrip.bin"
    tree_path = out_dir / f"{stem}.tree.json"
    csv_path = out_dir / f"{stem}.achievements.csv"
    missing_csv_path = out_dir / f"{stem}.{target_language}.missing.csv"
    report_path = out_dir / f"{stem}.report.json"
    roundtrip_path.write_bytes(rebuilt)
    tree_path.write_text(json.dumps([to_json(n) for n in nodes], ensure_ascii=False, indent=2), encoding="utf-8")
    rows = achievement_rows(nodes, target_language)
    export_csv(rows, csv_path)
    missing_count = export_missing_translation_csv(rows, target_language, missing_csv_path)
    source_ids = {str(r["api_name"]) for r in rows if r.get("api_name")}
    report: dict[str, Any] = {
        "input": str(input_path),
        "size": len(data),
        "sha256_original": sha256(data),
        "sha256_roundtrip": sha256(rebuilt),
        "roundtrip_equal": data == rebuilt,
        "achievement_count": len(rows),
        "with_existing_target_language": sum(1 for r in rows if r.get(f"{target_language}_name") or r.get(f"{target_language}_description")),
        "achievements_csv": str(csv_path),
        "missing_target_language_csv": str(missing_csv_path),
        "missing_target_language_count": missing_count,
        "roundtrip_bin": str(roundtrip_path),
        "tree_json": str(tree_path),
        "report_json": str(report_path),
    }
    if translations:
        if data != rebuilt:
            raise SystemExit("source file failed byte-identical roundtrip; refusing to apply translations")
        translation_result = load_translations(translations, target_language)
        translation_ids = set(translation_result.entries)
        changed = apply_translations(nodes, translation_result.entries, target_language)
        loc = serialize(nodes)
        loc_path = localized_bin or (out_dir / f"{stem}.{target_language}.bin")
        loc_path.parent.mkdir(parents=True, exist_ok=True)
        loc_path.write_bytes(loc)
        loc_data, loc_nodes = load_schema(loc_path)
        loc_rebuilt = serialize(loc_nodes)
        loc_rows = achievement_rows(loc_nodes, target_language)
        loc_csv_path = out_dir / f"{stem}.{target_language}.achievements.csv"
        export_csv(loc_rows, loc_csv_path)
        residue = latin_residue(loc_rows, target_language)
        empty_ids = empty_target_ids(loc_rows, target_language)
        report.update({
            "translations_csv": str(translations),
            "localized_bin": str(loc_path),
            "localized_achievements_csv": str(loc_csv_path),
            "translation_rows_loaded": len(translation_result.entries),
            "translation_text_sanitized_count": translation_result.sanitized_count,
            "target_language_nodes_changed": changed,
            "sha256_localized": sha256(loc_data),
            "sha256_localized_roundtrip": sha256(loc_rebuilt),
            "localized_roundtrip_equal": loc_data == loc_rebuilt,
            "localized_achievement_count": len(loc_rows),
            "target_language_coverage_count": len(loc_rows) - len(empty_ids),
            "missing_translation_ids": sorted(source_ids - translation_ids),
            "extra_translation_ids": sorted(translation_ids - source_ids),
            "empty_target_field_ids": empty_ids,
            "target_language_latin_residue": residue,
        })
        if strict_no_latin and residue:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise SystemExit(f"target language fields contain {residue} rows with Latin words")
        if loc_data != loc_rebuilt:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise SystemExit("localized file failed byte-identical roundtrip")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def install_localized_file(original: Path, localized: Path, out_dir: Path) -> dict[str, Any]:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup = out_dir / f"{original.name}.backup-{timestamp}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, backup)
    shutil.copy2(localized, original)
    installed_hash = file_sha256(original)
    localized_hash = file_sha256(localized)
    return {
        "installed": True,
        "installed_path": str(original),
        "backup_path": str(backup),
        "installed_sha256": installed_hash,
        "installed_matches_localized": installed_hash == localized_hash,
    }


def version_check_cli(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="Check local skill version against the latest GitHub tag.")
    ap.add_argument("--warn-only", action="store_true", help="print the report but return success on mismatch or network failure")
    ap.add_argument("--max-age-hours", type=float, default=24.0, help="reuse a successful cached GitHub tag check within this many hours")
    ap.add_argument("--force", action="store_true", help="ignore the cache and query GitHub now")
    ap.add_argument("--cache-file", type=Path, help="override the version-check cache path")
    args = ap.parse_args(argv)
    report = build_version_report(max_age_hours=args.max_age_hours, force=args.force, cache_file=args.cache_file)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.warn_only:
        return
    if not report.get("versions_match"):
        raise SystemExit(2)


def legacy_cli(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="Parse, export, verify, and localize Steam UserGameStatsSchema Binary KeyValues files.")
    ap.add_argument("input", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("outputs"))
    ap.add_argument("--target-language", default="schinese")
    ap.add_argument("--translations", type=Path)
    ap.add_argument("--localized-bin", type=Path)
    ap.add_argument("--strict-no-latin", action="store_true", help="fail if target fields contain Latin words after apply/verify")
    args = ap.parse_args(argv)
    report = process_schema(args.input, args.out_dir, args.target_language, args.translations, args.localized_bin, args.strict_no_latin)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def find_schema_cli(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="Find Steam UserGameStatsSchema_*.bin files from common Steam install locations.")
    ap.add_argument("--game-id", help="Steam app ID to locate; omit to list all local schema files")
    ap.add_argument("--steam-dir", type=Path, help="explicit Steam install directory")
    args = ap.parse_args(argv)
    print(json.dumps(find_schema_files(args.game_id, args.steam_dir), ensure_ascii=False, indent=2))


def workflow_cli(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="Automate the skill workflow: version preflight, schema discovery, safe copy, export, apply, verify, and optional install.")
    ap.add_argument("--game-id")
    ap.add_argument("--schema", type=Path)
    ap.add_argument("--steam-dir", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("outputs"))
    ap.add_argument("--target-language", default="schinese")
    ap.add_argument("--translations", type=Path)
    ap.add_argument("--localized-bin", type=Path)
    ap.add_argument("--install", action="store_true", help="back up the original schema and replace it with the verified localized copy")
    ap.add_argument("--strict-no-latin", action="store_true", help="fail if target fields contain Latin words after apply/verify")
    ap.add_argument("--skip-version-check", action="store_true")
    ap.add_argument("--force-version-check", action="store_true", help="ignore the cached version preflight and query GitHub now")
    ap.add_argument("--version-max-age-hours", type=float, default=24.0, help="reuse a successful cached version check within this many hours")
    ap.add_argument("--version-cache-file", type=Path, help="override the version-check cache path")
    ap.add_argument("--require-current-version", action="store_true", help="fail when the local skill version does not match the latest GitHub tag")
    args = ap.parse_args(argv)

    version_report = None if args.skip_version_check else build_version_report(
        max_age_hours=args.version_max_age_hours,
        force=args.force_version_check,
        cache_file=args.version_cache_file,
    )
    if args.require_current_version and version_report and not version_report.get("versions_match"):
        print(json.dumps({"version": version_report}, ensure_ascii=False, indent=2))
        raise SystemExit("local skill version does not match the latest GitHub tag")

    source, searched = resolve_schema(args.schema, args.game_id, args.steam_dir)
    working_source = copy_source_to_workspace(source, args.out_dir)
    report = process_schema(working_source, args.out_dir, args.target_language, args.translations, args.localized_bin, args.strict_no_latin)
    report.update({
        "version": version_report,
        "original_schema": str(source),
        "working_schema_copy": str(working_source),
        "schema_search_paths": searched,
        "installed": False,
    })
    if args.install:
        localized_value = report.get("localized_bin")
        if not localized_value:
            raise SystemExit("--install requires --translations or an existing localized output from this workflow")
        localized = Path(str(localized_value))
        if not localized.is_file():
            raise SystemExit(f"localized output is not a file: {localized}")
        report.update(install_localized_file(source, localized, args.out_dir))
    if not args.translations:
        report["next_step"] = "Review and fill the exported achievements CSV, then rerun workflow with --translations."
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "version-check":
        version_check_cli(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "find-schema":
        find_schema_cli(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "workflow":
        workflow_cli(sys.argv[2:])
    else:
        legacy_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
