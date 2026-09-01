from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from steam_localizer.bkv import Node, SchemaDocument, serialize  # noqa: E402


def string(name: str, value: str) -> Node:
    return Node(1, name, value=value, raw_value=value.encode("utf-8"))


def object_node(name: str, *children: Node) -> Node:
    return Node(0, name, children=list(children))


def sample_schema() -> bytes:
    achievements = []
    for index, api_name in enumerate(("FIRST", "SECOND"), 1):
        names = object_node(
            "name",
            string("english", f"English {index}"),
            string("german", f"Deutsch {index}"),
            string("japanese", f"日本語 {index}"),
        )
        descriptions = object_node(
            "desc",
            string("english", f"English description {index}"),
            string("german", f"Deutsche Beschreibung {index}"),
            string("japanese", f"日本語の説明 {index}"),
        )
        achievements.append(
            object_node(
                str(index),
                string("name", api_name),
                object_node("display", names, descriptions),
            )
        )
    return serialize([object_node("root", object_node("bits", *achievements))])


def schema_with_name_only_second_achievement() -> bytes:
    nodes = SchemaDocument.from_bytes(sample_schema()).nodes
    document = SchemaDocument.from_bytes(serialize(nodes))
    second = next(item for item in document.achievements if item.api_name == "SECOND")
    for child in second.description_node.children:
        child.value = ""
        child.raw_value = b""
    return document.to_bytes()


class BinaryKeyValuesTests(unittest.TestCase):
    def test_roundtrip_and_all_language_discovery(self) -> None:
        payload = sample_schema()
        document = SchemaDocument.from_bytes(payload)

        self.assertEqual(document.to_bytes(), payload)
        self.assertEqual(document.languages, ("english", "german", "japanese"))
        self.assertEqual(len(document.achievements), 2)
        self.assertEqual(document.coverage()["german"]["complete_achievements"], 2)

    def test_only_target_language_changes(self) -> None:
        document = SchemaDocument.from_bytes(sample_schema())
        before = document.translations_by_id()

        document.set_translation("FIRST", "schinese", "第一", "第一个成就")
        localized = SchemaDocument.from_bytes(document.to_bytes())

        self.assertEqual(
            localized.translations_by_id()["FIRST"]["schinese"],
            ("第一", "第一个成就"),
        )
        for language in ("english", "german", "japanese"):
            self.assertEqual(
                localized.translations_by_id()["FIRST"][language],
                before["FIRST"][language],
            )

    def test_text_coverage_is_checked_per_achievement_and_field(self) -> None:
        document = SchemaDocument.from_bytes(schema_with_name_only_second_achievement())
        document.set_translation("FIRST", "schinese", "第一", "")
        document.set_translation("SECOND", "schinese", "第二", "")

        self.assertEqual(
            document.text_coverage_issues(),
            [
                {
                    "api_name": "FIRST",
                    "field": "description",
                    "present_languages": ["english", "german", "japanese"],
                    "missing_languages": ["schinese"],
                }
            ],
        )

        document.set_translation("FIRST", "schinese", "第一", "第一个成就")

        self.assertEqual(document.text_coverage_issues(), [])

        document.set_translation("SECOND", "schinese", "第二", "不应出现的描述")
        self.assertEqual(
            document.text_coverage_issues(),
            [
                {
                    "api_name": "SECOND",
                    "field": "description",
                    "present_languages": ["schinese"],
                    "missing_languages": ["english", "german", "japanese"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
