from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def discover_steam_directories() -> tuple[Path, ...]:
    candidates: list[Path] = []
    for environment_name in ("STEAM_DIR", "SteamPath"):
        value = os.environ.get(environment_name)
        if value:
            candidates.append(Path(value))
    for environment_name in ("ProgramFiles(x86)", "ProgramFiles"):
        value = os.environ.get(environment_name)
        if value:
            candidates.append(Path(value) / "Steam")
    candidates.extend(
        [Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")]
    )
    if os.name == "nt":
        try:
            import winreg

            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (
                    r"Software\Valve\Steam",
                    r"Software\WOW6432Node\Valve\Steam",
                ):
                    try:
                        with winreg.OpenKey(hive, subkey) as key:
                            for value_name in ("SteamPath", "InstallPath"):
                                try:
                                    value, _ = winreg.QueryValueEx(key, value_name)
                                except FileNotFoundError:
                                    continue
                                if value:
                                    candidates.append(Path(value))
                    except FileNotFoundError:
                        continue
        except OSError:
            pass

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate.expanduser().resolve()).casefold()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(candidate)
    return tuple(unique)


def find_schema_files(
    app_id: str | None = None, steam_directory: Path | None = None
) -> dict[str, Any]:
    if app_id is not None and not app_id.isdigit():
        raise ValueError(f"invalid Steam app ID: {app_id!r}")
    steam_directories = (
        (Path(steam_directory),) if steam_directory else discover_steam_directories()
    )
    pattern = f"UserGameStatsSchema_{app_id}.bin" if app_id else "UserGameStatsSchema_*.bin"
    matches: list[dict[str, Any]] = []
    searched: list[str] = []
    for steam_path in steam_directories:
        stats_directory = steam_path / "appcache" / "stats"
        searched.append(str(stats_directory))
        if not stats_directory.is_dir():
            continue
        for path in sorted(stats_directory.glob(pattern)):
            match = re.fullmatch(r"UserGameStatsSchema_(\d+)\.bin", path.name)
            matches.append(
                {
                    "app_id": match.group(1) if match else None,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "modified_epoch": path.stat().st_mtime,
                }
            )
    return {
        "app_id": app_id,
        "searched_directories": searched,
        "match_count": len(matches),
        "matches": matches,
    }
