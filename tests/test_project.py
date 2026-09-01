from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from steam_localizer.bkv import SchemaDocument  # noqa: E402
from steam_localizer.project import apply_project, prepare_project  # noqa: E402
from test_bkv import sample_schema, schema_with_name_only_second_achievement  # noqa: E402


class ProjectWorkflowTests(unittest.TestCase):
    def test_prepare_and_apply_keep_work_and_final_files_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "UserGameStatsSchema_123456.bin"
            source.write_bytes(sample_schema())
            workspace = root / "project"

            prepared = prepare_project(
                source, "schinese", workspace, offline=True
            )

            self.assertEqual(prepared["source_languages"], ["english", "german", "japanese"])
            relative_files = {
                path.relative_to(workspace).as_posix()
                for path in workspace.rglob("*")
                if path.is_file()
            }
            self.assertEqual(
                relative_files,
                {
                    "input/UserGameStatsSchema_123456.bin",
                    "work/manifest.json",
                    "work/sources.json",
                    "work/translations.csv",
                },
            )

            translations_path = workspace / "work" / "translations.csv"
            with translations_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                self.assertIn("german_name", reader.fieldnames or [])
                self.assertIn("japanese_description", reader.fieldnames or [])
            for index, row in enumerate(rows, 1):
                row["target_name"] = f"成就{index}"
                row["target_description"] = f"完成第{index}项要求"
                row["translation_notes"] = "Compared every schema language."
            with translations_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            research_path = workspace / "work" / "sources.json"
            research = json.loads(research_path.read_text(encoding="utf-8"))
            research["consulted_schema_languages"] = ["english", "german", "japanese"]
            research_path.write_text(
                json.dumps(research, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            report = apply_project(workspace)

            self.assertFalse(report["original_was_modified"])
            self.assertEqual(report["target_language_coverage_count"], 2)
            final_bin = workspace / "final" / "UserGameStatsSchema_123456.bin"
            localized = SchemaDocument.from_path(final_bin)
            self.assertEqual(
                localized.translations_by_id()["FIRST"]["schinese"],
                ("成就1", "完成第1项要求"),
            )
            with zipfile.ZipFile(workspace / "final" / "UserGameStatsSchema_123456.zip") as archive:
                self.assertEqual(archive.namelist(), ["UserGameStatsSchema_123456.bin"])
                self.assertEqual(archive.read(archive.namelist()[0]), final_bin.read_bytes())
            final_files = {
                path.name for path in (workspace / "final").iterdir() if path.is_file()
            }
            self.assertEqual(
                final_files,
                {"UserGameStatsSchema_123456.bin", "UserGameStatsSchema_123456.zip", "report.json"},
            )

    def test_apply_requires_all_schema_languages_to_be_consulted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "UserGameStatsSchema_123456.bin"
            source.write_bytes(sample_schema())
            workspace = root / "project"
            prepare_project(source, "schinese", workspace, offline=True)

            with self.assertRaisesRegex(ValueError, "every schema language"):
                apply_project(workspace)

    def test_apply_preserves_each_achievements_optional_field_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "UserGameStatsSchema_123456.bin"
            source.write_bytes(schema_with_name_only_second_achievement())
            workspace = root / "project"
            prepared = prepare_project(source, "schinese", workspace, offline=True)

            translations_path = workspace / "work" / "translations.csv"
            with translations_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            rows[0]["target_name"] = "第一"
            rows[0]["target_description"] = "第一个成就"
            rows[1]["target_name"] = "第二"
            rows[1]["target_description"] = ""
            with translations_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            research_path = workspace / "work" / "sources.json"
            research = json.loads(research_path.read_text(encoding="utf-8"))
            research["consulted_schema_languages"] = prepared["source_languages"]
            research_path.write_text(
                json.dumps(research, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            report = apply_project(workspace)

            final_bin = workspace / "final" / "UserGameStatsSchema_123456.bin"
            localized = SchemaDocument.from_path(final_bin)
            self.assertEqual(
                report["target_language_coverage"],
                {"names": 2, "descriptions": 1, "complete_achievements": 1},
            )
            self.assertEqual(
                localized.translations_by_id()["SECOND"]["schinese"],
                ("第二", ""),
            )

    def test_apply_rejects_a_target_field_not_used_by_other_languages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "UserGameStatsSchema_123456.bin"
            source.write_bytes(schema_with_name_only_second_achievement())
            workspace = root / "project"
            prepared = prepare_project(source, "schinese", workspace, offline=True)

            translations_path = workspace / "work" / "translations.csv"
            with translations_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            for index, row in enumerate(rows, 1):
                row["target_name"] = f"成就{index}"
                row["target_description"] = f"描述{index}"
            with translations_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            research_path = workspace / "work" / "sources.json"
            research = json.loads(research_path.read_text(encoding="utf-8"))
            research["consulted_schema_languages"] = prepared["source_languages"]
            research_path.write_text(
                json.dumps(research, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError, "SECOND description missing english, german, japanese"
            ):
                apply_project(workspace)

    def test_apply_requires_online_sources_when_network_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "UserGameStatsSchema_123456.bin"
            source.write_bytes(sample_schema())
            workspace = root / "project"
            prepared = prepare_project(source, "schinese", workspace, offline=True)
            research_path = workspace / "work" / "sources.json"
            research = json.loads(research_path.read_text(encoding="utf-8"))
            research["network_access"] = "available"
            research["consulted_schema_languages"] = prepared["source_languages"]
            research["online_sources"] = []
            research_path.write_text(
                json.dumps(research, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "no online translation source"):
                apply_project(workspace)


if __name__ == "__main__":
    unittest.main()
