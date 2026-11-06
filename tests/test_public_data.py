from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from steam_localizer.project import apply_project, prepare_project
from steam_localizer.public_data import MAX_PAGE_BYTES, PublicAchievementClient, parse_public_page
from steam_localizer.translation_json import decode_translation, json_bytes, render_translation
from steam_localizer.library import LibraryError, TranslationLibraryClient
from steam_localizer.translations import TranslationEntry, load_translations, validate_placeholders


def public_page(language="english", *, app_id=123456, ids=("FIRST", "SECOND"), description=""):
    data = {"appid": app_id, "language": language, "groups": [{"achievements": [
        {"api_name": api_name, "name": f"{language} {api_name}", "description": description}
        for api_name in ids
    ]}]}
    return ('<script id="valve-ssr-data">' + json.dumps({"loaderData": [json.dumps(data)]}) + '</script>').encode()


def public_client(pages):
    def open_page(request, timeout):
        language = request.full_url.split("?l=")[1]
        value = pages[language]
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(value)
    return PublicAchievementClient(open_page)


class PublicDataTests(unittest.TestCase):
    def test_page_requires_verified_identity_ids_and_text(self):
        invalid = [b'<html>login</html>', public_page(app_id=654321), public_page("german"),
                   public_page(ids=("FIRST", "FIRST")), public_page(ids=("",))]
        for data in invalid:
            with self.subTest(data=data[:60]), self.assertRaises(ValueError):
                parse_public_page(data.decode(), "123456", "english")
        self.assertEqual(parse_public_page(public_page().decode(), "123456", "english")["FIRST"], ("english FIRST", ""))

    def test_query_data_and_duplicate_json_keys(self):
        data = {"appid": 123456, "language": "english", "groups": [{"achievements": [
            {"api_name": "A", "name": "A", "description": ""}]}]}
        html = '<script id="valve-ssr-data">' + json.dumps({"renderContext": {"queryData": json.dumps(data)}}) + '</script>'
        self.assertEqual(set(parse_public_page(html, "123456", "english")), {"A"})
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            parse_public_page('<script id="valve-ssr-data">{"loaderData":[],"loaderData":[]}</script>', "123456", "english")

    def test_missing_language_does_not_invent_text(self):
        snapshot = public_client({"english": public_page(), "japanese": OSError("unavailable")}).fetch("123456", ("english", "japanese"))
        self.assertEqual(snapshot["languages"], ["english"])
        self.assertEqual(snapshot["unavailable_languages"][0]["language"], "japanese")
        self.assertEqual(snapshot["submission_blockers"], [])
        self.assertIn("retrieved_at", snapshot["sources"][0])

    def test_oversized_or_unavailable_page_fails_without_workspace(self):
        for page in [OSError("forbidden"), b'x' * (MAX_PAGE_BYTES + 1)]:
            with tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary) / "project"
                with self.assertRaisesRegex(ValueError, "cannot obtain public achievements"):
                    prepare_project(None, "schinese", workspace, app_id="123456", public_client=public_client({"english": page}))
                self.assertFalse(workspace.exists())

    def prepare(self, root, pages=None, languages=("english",), library=None):
        library = library or Mock(lookup=Mock(return_value=None))
        return prepare_project(None, "schinese", root, app_id="123456", source_languages=languages,
                               public_client=public_client(pages or {"english": public_page()}), library_client=library)

    def translate(self, root, *, name="成就", description=""):
        path = root / "work" / "translations.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            fieldnames = reader.fieldnames
        for row in rows:
            row["target_name"], row["target_description"] = name, description
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        research_path = root / "work" / "sources.json"
        research = json.loads(research_path.read_text(encoding="utf-8"))
        research["consulted_schema_languages"] = research["source_schema_languages"]
        research_path.write_bytes(json_bytes(research))

    def test_public_workflow_outputs_standalone_json_without_bin_claims(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            library = Mock(lookup=Mock(side_effect=LibraryError("offline catalog")))
            self.prepare(root, library=library)
            with (root / "work/translations.csv").open(encoding="utf-8-sig") as stream:
                draft = list(csv.DictReader(stream))
            self.assertEqual(draft[0]["target_name"], "")
            self.translate(root)
            report = apply_project(root)
            self.assertEqual(report["source_kind"], "public-data-derived")
            self.assertTrue(report["json_submission_eligible"])
            for key in ("source_sha256", "roundtrip_equal", "final_bin", "final_zip", "localized_sha256"):
                self.assertNotIn(key, report)
            self.assertEqual({p.name for p in (root / "final").iterdir()}, {"UserGameStatsSchema_123456.json", "report.json"})
            payload = (root / "final/UserGameStatsSchema_123456.json").read_bytes()
            translation = decode_translation(payload)
            self.assertNotIn(b'\r', payload)
            self.assertTrue(payload.endswith(b'\n'))
            self.assertEqual(translation["languages"], ["english", "schinese"])
            self.assertEqual(translation["achievements"]["SECOND"]["translations"]["schinese"], {"name": "成就", "description": ""})

    def test_inconsistent_language_snapshots_block_formal_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self.prepare(root, {"english": public_page(), "german": public_page("german", ids=("FIRST",))}, ("english", "german"))
            self.translate(root)
            with self.assertRaisesRegex(ValueError, "ID set differs"):
                apply_project(root)
            self.assertEqual({p.name for p in (root / "final").iterdir()}, {"report.json"})
            self.assertFalse(json.loads((root / "final/report.json").read_text())["json_submission_eligible"])

    def test_source_tampering_blank_targets_and_missing_placeholders_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self.prepare(root, {"english": public_page(description="Collect %s1 and {count}")})
            self.translate(root)
            with self.assertRaisesRegex(ValueError, "placeholders"):
                apply_project(root)
            self.translate(root, description="收集 %s1 和 {count}")
            apply_project(root)
            snapshot = root / "input/public-achievements.json"
            snapshot.write_bytes(snapshot.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, "has changed"):
                apply_project(root)

    def test_source_options_reject_invalid_ids_variants_offline_and_existing_workspaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for kwargs in ({"app_id": "../123"}, {"app_id": "0"}, {"app_id": "4294967296"},
                           {"app_id": "123456", "variant_id": "../bad"}, {"app_id": "123456", "offline": True}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    prepare_project(None, "schinese", root / "project", **kwargs)
            with self.assertRaisesRegex(ValueError, "workspace is not empty"):
                (root / "existing.txt").write_text("preserve", encoding="utf-8")
                self.prepare(root)

    def test_json_only_library_reference_and_conflicting_ids(self):
        for ids in (("FIRST", "SECOND"), ("FIRST",)):
            with self.subTest(ids=ids), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "project"
                reference = json_bytes(render_translation("123456", "default", {
                    api_name: {"english": (api_name, ""), "schinese": ("现有译文", "")}
                    for api_name in ids
                }))
                variant = {"format": "json", "languages": ["english", "schinese"], "achievements": len(ids),
                           "json": {"version": 2, "size": len(reference), "sha256": hashlib.sha256(reference).hexdigest()}}
                catalog = json_bytes({"version": 2, "games": {"123456": {"variants": {"default": variant}}}})
                client = TranslationLibraryClient(lambda request, timeout: io.BytesIO(catalog if request.full_url.endswith('index-v2.json') else reference))
                prepared = self.prepare(root, library=client)
                with (root / "work/translations.csv").open(encoding="utf-8-sig") as stream:
                    draft = list(csv.DictReader(stream))
                self.assertEqual(draft[0]["library_schinese_name"], "现有译文")
                self.assertTrue(prepared["translation_library_match"])
                self.translate(root)
                if len(ids) == 2:
                    self.assertTrue(apply_project(root)["json_submission_eligible"])
                else:
                    with self.assertRaisesRegex(ValueError, "conflict with the selected"):
                        apply_project(root)

    def test_empty_target_and_extra_or_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self.prepare(root)
            self.translate(root, name="")
            with self.assertRaisesRegex(ValueError, "name missing schinese"):
                apply_project(root)
            self.translate(root)
            path = root / "work/translations.csv"
            original = path.read_bytes()
            with path.open("a", encoding="utf-8", newline="") as stream:
                stream.write('EXTRA,,,额外,,\n')
            with self.assertRaisesRegex(ValueError, "extra IDs"):
                load_translations(path, {"FIRST", "SECOND"})
            path.write_bytes(original + original.splitlines(keepends=True)[1])
            with self.assertRaisesRegex(ValueError, "duplicate ID"):
                load_translations(path, {"FIRST", "SECOND"})

    def test_public_description_only_fields_are_preserved(self):
        page = public_page(description="Description").replace(b'english FIRST', b'').replace(b'english SECOND', b'')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self.prepare(root, {"english": page})
            self.translate(root, name="", description="描述")
            self.assertEqual(apply_project(root)["target_language_coverage"],
                             {"names": 0, "descriptions": 2, "complete_achievements": 0})


class TranslationJsonTests(unittest.TestCase):
    def test_placeholder_counts_escapes_and_percent_prose(self):
        cases = [("Collect %s1: {count} %d", "收集 %s1：{count} %d"),
                 ("100% complete", "100% 完成"), ("literal %%s", "字面量 %%s")]
        for original, target in cases:
            validate_placeholders({"A": {"english": (original, "")}}, "schinese", {"A": TranslationEntry(target, "")})
        with self.assertRaisesRegex(ValueError, "placeholders"):
            validate_placeholders({"A": {"english": ("%s1 %s1", "")}}, "schinese", {"A": TranslationEntry("%s1", "")})

    def test_stable_sort_and_full_field_validation(self):
        values = {"Z": {"english": ("", "Description"), "schinese": ("", "描述")},
                  "A": {"english": ("Name", ""), "schinese": ("名称", "")}}
        payload = render_translation("123456", "default", values)
        self.assertEqual(list(payload["achievements"]), ["A", "Z"])
        self.assertEqual(len(payload), 5)
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            decode_translation(b'{"version":2,"version":2}')
        for value in ({**payload, "source_sha256": "fake"}, {**payload, "languages": ["schinese", "english"]},
                      {**payload, "version": True}, {**payload, "app_id": "00123456"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_translation(json_bytes(value))
        values["A"]["schinese"] = ("", "")
        with self.assertRaisesRegex(ValueError, "A name missing schinese"):
            render_translation("123456", "default", values)


if __name__ == "__main__":
    unittest.main()
