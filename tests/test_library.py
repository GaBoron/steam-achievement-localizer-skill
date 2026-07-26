from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from steam_localizer.library import parse_match  # noqa: E402


class TranslationLibraryTests(unittest.TestCase):
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
