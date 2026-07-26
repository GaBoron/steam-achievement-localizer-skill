from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


TYPE_NAMES = {
    0: "BEGIN",
    1: "STRING",
    2: "INT32",
    3: "FLOAT32",
    4: "POINTER",
    5: "WIDESTRING",
    6: "COLOR",
    7: "UINT64",
    8: "END",
}
IGNORED_LANGUAGE_KEYS = {"token", "tokens"}


@dataclass
class Node:
    type_id: int
    name: str
    children: list["Node"] = field(default_factory=list)
    value: str | None = None
    raw_value: bytes = b""


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0

    def read_byte(self) -> int:
        if self.position >= len(self.data):
            raise ValueError("unexpected EOF while reading a type byte")
        value = self.data[self.position]
        self.position += 1
        return value

    def read_bytes(self, count: int) -> bytes:
        if self.position + count > len(self.data):
            raise ValueError("unexpected EOF while reading a value")
        value = self.data[self.position : self.position + count]
        self.position += count
        return value

    def read_cstring_bytes(self) -> bytes:
        end = self.data.find(b"\0", self.position)
        if end < 0:
            raise ValueError("unterminated UTF-8 string")
        value = self.data[self.position : end]
        self.position = end + 1
        return value

    def read_cstring(self) -> str:
        return self.read_cstring_bytes().decode("utf-8")


def _parse_nodes(reader: Reader) -> list[Node]:
    nodes: list[Node] = []
    while True:
        type_id = reader.read_byte()
        if type_id == 8:
            return nodes
        if type_id not in TYPE_NAMES:
            raise ValueError(f"unknown Binary KeyValues type {type_id}")
        node = Node(type_id, reader.read_cstring())
        if type_id == 0:
            node.children = _parse_nodes(reader)
        elif type_id == 1:
            node.raw_value = reader.read_cstring_bytes()
            node.value = node.raw_value.decode("utf-8")
        elif type_id in (2, 3, 4, 6):
            node.raw_value = reader.read_bytes(4)
        elif type_id == 7:
            node.raw_value = reader.read_bytes(8)
        elif type_id == 5:
            raise ValueError("WideString Binary KeyValues nodes are not supported")
        nodes.append(node)


def parse(data: bytes) -> list[Node]:
    reader = Reader(data)
    nodes = _parse_nodes(reader)
    if reader.position != len(data):
        raise ValueError(
            f"Binary KeyValues parser stopped at {reader.position}, file size is {len(data)}"
        )
    return nodes


def serialize(nodes: list[Node]) -> bytes:
    output = bytearray()
    for node in nodes:
        output.append(node.type_id)
        output.extend(node.name.encode("utf-8"))
        output.append(0)
        if node.type_id == 0:
            output.extend(serialize(node.children))
        elif node.type_id == 1:
            output.extend(node.raw_value)
            output.append(0)
        elif node.type_id in (2, 3, 4, 6, 7):
            output.extend(node.raw_value)
        else:
            raise ValueError(f"cannot serialize Binary KeyValues type {node.type_id}")
    output.append(8)
    return bytes(output)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _walk(nodes: list[Node]) -> Iterator[Node]:
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _first_object(node: Node, name: str) -> Node | None:
    return next(
        (child for child in node.children if child.type_id == 0 and child.name == name),
        None,
    )


def _nested_object(node: Node, *names: str) -> Node | None:
    current: Node | None = node
    for name in names:
        current = _first_object(current, name) if current is not None else None
    return current


def _first_string(node: Node, name: str) -> str:
    child = next(
        (child for child in node.children if child.type_id == 1 and child.name == name),
        None,
    )
    return child.value or "" if child else ""


def _language_values(node: Node) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in node.children:
        if child.type_id != 1:
            continue
        language = child.name.casefold()
        if language in IGNORED_LANGUAGE_KEYS:
            continue
        if language in values:
            raise ValueError(f"duplicate language node {language!r}")
        values[language] = child.value or ""
    return values


@dataclass(frozen=True)
class Achievement:
    api_name: str
    name_node: Node
    description_node: Node

    def translations(self) -> dict[str, tuple[str, str]]:
        names = _language_values(self.name_node)
        descriptions = _language_values(self.description_node)
        return {
            language: (names.get(language, ""), descriptions.get(language, ""))
            for language in sorted(set(names) | set(descriptions))
        }


@dataclass
class SchemaDocument:
    source_bytes: bytes
    nodes: list[Node]
    achievements: list[Achievement]

    @classmethod
    def from_bytes(cls, payload: bytes) -> "SchemaDocument":
        nodes = parse(payload)
        if serialize(nodes) != payload:
            raise ValueError("schema failed byte-identical Binary KeyValues roundtrip")
        achievements: list[Achievement] = []
        seen_ids: set[str] = set()
        for bits in (
            node for node in _walk(nodes) if node.type_id == 0 and node.name == "bits"
        ):
            for node in bits.children:
                if node.type_id != 0:
                    continue
                api_name = _first_string(node, "name")
                name_node = _nested_object(node, "display", "name")
                description_node = _nested_object(node, "display", "desc")
                if not api_name or name_node is None or description_node is None:
                    continue
                if api_name in seen_ids:
                    raise ValueError(f"duplicate achievement API ID {api_name!r}")
                seen_ids.add(api_name)
                achievements.append(Achievement(api_name, name_node, description_node))
        if not achievements:
            raise ValueError("schema contains no recognizable achievement records")
        return cls(payload, nodes, achievements)

    @classmethod
    def from_path(cls, path: Path) -> "SchemaDocument":
        return cls.from_bytes(Path(path).read_bytes())

    @property
    def languages(self) -> tuple[str, ...]:
        languages: set[str] = set()
        for achievement in self.achievements:
            languages.update(achievement.translations())
        return tuple(
            sorted(
                languages,
                key=lambda language: (
                    {"english": 0, "schinese": 1, "tchinese": 2}.get(language, 3),
                    language,
                ),
            )
        )

    def coverage(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for language in self.languages:
            names = 0
            descriptions = 0
            complete = 0
            for achievement in self.achievements:
                name, description = achievement.translations().get(language, ("", ""))
                names += bool(name.strip())
                descriptions += bool(description.strip())
                complete += bool(name.strip() and description.strip())
            result[language] = {
                "names": names,
                "descriptions": descriptions,
                "complete_achievements": complete,
            }
        return result

    def translations_by_id(self) -> dict[str, dict[str, tuple[str, str]]]:
        return {
            achievement.api_name: achievement.translations()
            for achievement in self.achievements
        }

    def set_translation(
        self, api_name: str, language: str, name: str, description: str
    ) -> int:
        achievement = next(
            (item for item in self.achievements if item.api_name == api_name), None
        )
        if achievement is None:
            raise ValueError(f"unknown achievement API ID {api_name!r}")
        return _set_language(achievement.name_node, language, name) + _set_language(
            achievement.description_node, language, description
        )

    def to_bytes(self) -> bytes:
        return serialize(self.nodes)


def _set_language(parent: Node, language: str, value: str) -> int:
    matches = [
        child
        for child in parent.children
        if child.type_id == 1 and child.name.casefold() == language.casefold()
    ]
    if len(matches) > 1:
        raise ValueError(f"duplicate target language node {language!r}")
    encoded = value.encode("utf-8")
    if matches:
        changed = matches[0].raw_value != encoded
        matches[0].value = value
        matches[0].raw_value = encoded
        return int(changed)
    parent.children.append(Node(1, language, value=value, raw_value=encoded))
    return 1
