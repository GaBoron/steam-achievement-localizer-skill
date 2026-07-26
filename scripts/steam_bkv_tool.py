#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from steam_localizer.project import apply_project, prepare_project
from steam_localizer.steam import find_schema_files


def _prepare_command(arguments: argparse.Namespace) -> dict[str, object]:
    return prepare_project(
        arguments.schema,
        arguments.target_language,
        arguments.workspace,
        offline=arguments.offline,
    )


def _apply_command(arguments: argparse.Namespace) -> dict[str, object]:
    return apply_project(arguments.workspace)


def _find_schema_command(arguments: argparse.Namespace) -> dict[str, object]:
    return find_schema_files(arguments.app_id, arguments.steam_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and apply researched Steam achievement translations safely."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare",
        help="create one organized translation workspace from a source schema",
    )
    prepare.add_argument("--schema", type=Path, required=True)
    prepare.add_argument("--target-language", required=True)
    prepare.add_argument(
        "--workspace",
        type=Path,
        help="project directory; defaults to localization/<app_id>-<language>",
    )
    prepare.add_argument(
        "--offline",
        action="store_true",
        help="skip the connected translation-library lookup",
    )
    prepare.set_defaults(handler=_prepare_command)

    apply = commands.add_parser(
        "apply",
        help="validate research and translations, then create canonical final artifacts",
    )
    apply.add_argument("--workspace", type=Path, required=True)
    apply.set_defaults(handler=_apply_command)

    find_schema = commands.add_parser(
        "find-schema", help="find Steam UserGameStatsSchema files on this computer"
    )
    find_schema.add_argument("--app-id")
    find_schema.add_argument("--steam-dir", type=Path)
    find_schema.set_defaults(handler=_find_schema_command)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    try:
        result = arguments.handler(arguments)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
