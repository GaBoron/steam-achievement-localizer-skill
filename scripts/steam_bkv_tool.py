#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, hashlib, json, re, struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TYPE_NAMES = {0:"BEGIN",1:"STRING",2:"INT32",3:"FLOAT32",4:"POINTER",5:"WIDESTRING",6:"COLOR",7:"UINT64",8:"END"}

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
        if self.pos >= len(self.data): raise EOFError("unexpected EOF reading type")
        v = self.data[self.pos]; self.pos += 1; return v
    def bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.data): raise EOFError("unexpected EOF reading value")
        v = self.data[self.pos:self.pos+n]; self.pos += n; return v
    def cbytes(self) -> bytes:
        end = self.data.find(b"\0", self.pos)
        if end < 0: raise EOFError("unterminated string")
        v = self.data[self.pos:end]; self.pos = end + 1; return v
    def cstr(self) -> str:
        return self.cbytes().decode("utf-8")

def parse_nodes(r: Reader) -> list[Node]:
    nodes: list[Node] = []
    while True:
        t = r.u8()
        if t == 8: return nodes
        if t not in TYPE_NAMES: raise ValueError(f"unknown type {t} at offset {r.pos - 1}")
        name = r.cstr(); n = Node(t, name)
        if t == 0: n.children = parse_nodes(r)
        elif t == 1:
            raw = r.cbytes(); n.raw_value = raw; n.value = raw.decode("utf-8")
        elif t in (2,3,4,6): n.raw_value = r.bytes(4)
        elif t == 7: n.raw_value = r.bytes(8)
        elif t == 5: raise NotImplementedError("WideString node encountered")
        nodes.append(n)

def cstr(s: str) -> bytes: return s.encode("utf-8") + b"\0"

def serialize(nodes: list[Node]) -> bytes:
    out = bytearray()
    for n in nodes:
        out.append(n.type_id); out.extend(cstr(n.name))
        if n.type_id == 0: out.extend(serialize(n.children))
        elif n.type_id == 1: out.extend(cstr(n.value if n.value is not None else n.raw_value.decode("utf-8")))
        elif n.type_id in (2,3,4,6,7): out.extend(n.raw_value)
        else: raise NotImplementedError(f"cannot serialize type {n.type_id}")
    out.append(8); return bytes(out)

def sha256(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def scalar(n: Node) -> Any:
    if n.type_id == 1: return n.value
    if n.type_id == 2: return struct.unpack("<i", n.raw_value)[0]
    if n.type_id == 3: return struct.unpack("<f", n.raw_value)[0]
    if n.type_id in (4,6): return struct.unpack("<I", n.raw_value)[0]
    if n.type_id == 7: return struct.unpack("<Q", n.raw_value)[0]
    return None

def to_json(n: Node) -> dict[str, Any]:
    d: dict[str, Any] = {"type": TYPE_NAMES[n.type_id], "name": n.name}
    if n.type_id == 0: d["children"] = [to_json(c) for c in n.children]
    else:
        d["value"] = scalar(n)
        if n.type_id != 1: d["raw_hex"] = n.raw_value.hex()
    return d

def walk(nodes: list[Node]):
    for n in nodes:
        yield n
        if n.children: yield from walk(n.children)

def begins(n: Node, name: str) -> list[Node]: return [c for c in n.children if c.type_id == 0 and c.name == name]
def strings(n: Node, name: str) -> list[Node]: return [c for c in n.children if c.type_id == 1 and c.name == name]
def first_str(n: Node, name: str) -> str | None:
    s = strings(n, name); return (s[0].value or "") if s else None

def nested(n: Node, *names: str) -> Node | None:
    cur: Node | None = n
    for name in names:
        if cur is None: return None
        matches = begins(cur, name); cur = matches[0] if matches else None
    return cur

def achievement_nodes(nodes: list[Node]) -> list[Node]:
    out: list[Node] = []
    for bits in [n for n in walk(nodes) if n.type_id == 0 and n.name == "bits"]:
        for child in bits.children:
            if child.type_id == 0 and strings(child, "name") and nested(child, "display", "name") and nested(child, "display", "desc"):
                out.append(child)
    return out

def load_schema(path: Path) -> tuple[bytes, list[Node]]:
    data = path.read_bytes(); r = Reader(data); nodes = parse_nodes(r)
    if r.pos != len(data): raise ValueError(f"parser stopped at {r.pos}, file size {len(data)}")
    return data, nodes

def achievement_rows(nodes: list[Node], lang: str) -> list[dict[str, Any]]:
    rows=[]
    for i, ach in enumerate(achievement_nodes(nodes), 1):
        dn = nested(ach, "display", "name"); dd = nested(ach, "display", "desc")
        assert dn and dd
        rows.append({
            "index": i, "node_key": ach.name, "api_name": first_str(ach, "name") or "",
            "english_name": first_str(dn, "english") or "", "english_description": first_str(dd, "english") or "",
            f"{lang}_name": first_str(dn, lang) or "", f"{lang}_description": first_str(dd, lang) or "",
        })
    return rows

def export_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader(); w.writerows(rows)

def pick(row: dict[str,str], keys: list[str]) -> str:
    for k in keys:
        if row.get(k, "").strip(): return row[k].strip()
    return ""

def load_translations(path: Path, lang: str) -> dict[str, tuple[str,str]]:
    out: dict[str, tuple[str,str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = pick(row, ["api_name", "id", "achievement_id", "name"])
            zh_name = pick(row, [f"{lang}_name", "target_name", "translated_name", "name_zh", "schinese_name"])
            zh_desc = pick(row, [f"{lang}_description", "target_description", "translated_description", "description_zh", "schinese_description"])
            if key and (zh_name or zh_desc): out[key] = (zh_name, zh_desc)
    return out

def upsert_string(parent: Node, lang: str, value: str) -> bool:
    if not value: return False
    existing = strings(parent, lang)
    if existing:
        if existing[0].value == value: return False
        existing[0].value = value; existing[0].raw_value = value.encode("utf-8"); return True
    english = strings(parent, "english")
    at = parent.children.index(english[-1]) + 1 if english else len(parent.children)
    parent.children.insert(at, Node(1, lang, value=value, raw_value=value.encode("utf-8")))
    return True

def apply_translations(nodes: list[Node], translations: dict[str, tuple[str,str]], lang: str) -> int:
    changed = 0
    for ach in achievement_nodes(nodes):
        key = first_str(ach, "name")
        if not key or key not in translations: continue
        dn = nested(ach, "display", "name"); dd = nested(ach, "display", "desc")
        if dn and upsert_string(dn, lang, translations[key][0]): changed += 1
        if dd and upsert_string(dd, lang, translations[key][1]): changed += 1
    return changed

def latin_residue(rows: list[dict[str,Any]], lang: str) -> int:
    rx = re.compile(r"[A-Za-z]{2,}")
    return sum(1 for r in rows if rx.search(r.get(f"{lang}_name", "")) or rx.search(r.get(f"{lang}_description", "")))

def main() -> None:
    ap = argparse.ArgumentParser(description="Parse, export, verify, and localize Steam UserGameStatsSchema Binary KeyValues files.")
    ap.add_argument("input", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("outputs"))
    ap.add_argument("--target-language", default="schinese")
    ap.add_argument("--translations", type=Path)
    ap.add_argument("--localized-bin", type=Path)
    ap.add_argument("--strict-no-latin", action="store_true", help="fail if target fields contain Latin words after apply/verify")
    args = ap.parse_args()
    data, nodes = load_schema(args.input)
    rebuilt = serialize(nodes)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem
    (args.out_dir / f"{stem}.roundtrip.bin").write_bytes(rebuilt)
    (args.out_dir / f"{stem}.tree.json").write_text(json.dumps([to_json(n) for n in nodes], ensure_ascii=False, indent=2), encoding="utf-8")
    rows = achievement_rows(nodes, args.target_language)
    export_csv(rows, args.out_dir / f"{stem}.achievements.csv")
    report: dict[str, Any] = {
        "input": str(args.input), "size": len(data), "sha256_original": sha256(data),
        "sha256_roundtrip": sha256(rebuilt), "roundtrip_equal": data == rebuilt,
        "achievement_count": len(rows), "with_existing_target_language": sum(1 for r in rows if r.get(f"{args.target_language}_name") or r.get(f"{args.target_language}_description")),
    }
    if args.translations:
        translations = load_translations(args.translations, args.target_language)
        changed = apply_translations(nodes, translations, args.target_language)
        loc = serialize(nodes)
        loc_path = args.localized_bin or (args.out_dir / f"{stem}.{args.target_language}.bin")
        loc_path.write_bytes(loc)
        loc_rows = achievement_rows(nodes, args.target_language)
        export_csv(loc_rows, args.out_dir / f"{stem}.{args.target_language}.achievements.csv")
        residue = latin_residue(loc_rows, args.target_language)
        report.update({"localized_bin": str(loc_path), "translation_rows_loaded": len(translations), "target_language_nodes_changed": changed, "sha256_localized": sha256(loc), "target_language_latin_residue": residue})
        if args.strict_no_latin and residue:
            (args.out_dir / f"{stem}.report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise SystemExit(f"target language fields contain {residue} rows with Latin words")
    (args.out_dir / f"{stem}.report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
