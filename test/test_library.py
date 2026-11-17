from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from steam_localizer.library import LibraryError, TranslationLibraryClient, parse_match  # noqa: E402
from steam_localizer.translation_json import json_bytes, render_translation  # noqa: E402


class TranslationLibraryTests(unittest.TestCase):
    def test_catalog_v2_supports_bin_and_json_only_variants(self):
        for artifact_format in ("bin", "json"):
            with self.subTest(artifact_format=artifact_format):
                integrity = {"size": 100, "sha256": "a" * 64}
                variant = {"languages": ["english", "schinese"], "achievements": 2}
                if artifact_format == "bin":
                    variant.update(integrity)
                else:
                    variant.update({"format": "json", "json": {"version": 2, **integrity}})
                catalog = {"version": 2, "games": {"123456": {"name": "Example", "variants": {"default": variant}}}}
                match = parse_match(json_bytes(catalog), "123456")
                self.assertEqual(match.artifact_format, artifact_format)
                self.assertEqual(match.achievement_count, 2)
                self.assertTrue(match.source_url.endswith(f"/123456/default/UserGameStatsSchema_123456.{artifact_format}"))
                self.assertIsNone(parse_match(json_bytes(catalog), "123456", "other"))
                if artifact_format == "json":
                    variant["sha256"] = "b" * 64
                    with self.assertRaisesRegex(LibraryError, "invalid integrity metadata"):
                        parse_match(json_bytes(catalog), "123456")

    def test_download_checks_raw_size_and_content_before_saving(self):
        payload = json_bytes(render_translation("123456", "default", {"A": {"english": ("First", "")}}))
        variant = {"format": "json", "languages": ["english"], "achievements": 1,
                   "json": {"version": 2, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}}
        catalog = {"version": 2, "games": {"123456": {"variants": {"default": variant}}}}
        match = parse_match(json_bytes(catalog), "123456")
        client = TranslationLibraryClient(lambda request, timeout: io.BytesIO(payload[:-1] + b'x'))
        with self.assertRaisesRegex(LibraryError, "SHA-256 mismatch"):
            client.download(match, Path("must-not-be-written.json"))

    def test_parse_primary_library_contract(self) -> None:
        schema = b"schema"
        payload = json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "game_id": "123456",
                        "game_name": "Example",
                        "languages": ["schinese", "english"],
                        "schema_file": "files/123456/UserGameStatsSchema_123456.bin",
                        "sha256": hashlib.sha256(schema).hexdigest(),
                        "file_size_bytes": len(schema),
                    }
                ],
            }
        ).encode()

        match = parse_match(payload, "123456")

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.languages, ("schinese", "english"))
        self.assertTrue(match.source_url.endswith("/files/123456/UserGameStatsSchema_123456.bin"))


if __name__ == "__main__":
    unittest.main()
