"""T17–T19 · JSON Schema (jsonschema): фрагменти корпусу, реєстр сутностей, альтернативи."""
import json
import os
from pathlib import Path

import jsonschema
import pytest

LAB = Path(__file__).resolve().parents[2]
SCHEMAS = json.loads((Path(__file__).resolve().parents[1] / "schemas.json").read_text(encoding="utf-8"))


def _errors(schema, items):
    v = jsonschema.Draft202012Validator(schema)
    return [(i, e.message) for i, it in enumerate(items) for e in v.iter_errors(it)]


@pytest.mark.critical
def test_T17_chunk_schema(corpus):
    err = _errors(SCHEMAS["chunk"], corpus[0])
    assert not err, f"фрагменти не відповідають схемі: {len(err)}; {err[:3]}"


@pytest.mark.critical
def test_T18_registry_schema(version):
    p = LAB / "data" / "clean" / "entity_registry.json"
    if version == "baseline" or os.environ.get("KB_DIR"):
        pytest.skip("реєстр сутностей існує лише для версії clean")
    reg = json.loads(p.read_text(encoding="utf-8"))
    err = _errors(SCHEMAS["entity"], reg["entities"])
    assert not err, f"реєстр сутностей: {err[:3]}"


@pytest.mark.critical
def test_T19_alternatives_schema(version):
    p = LAB / "data" / "clean" / "alternatives.jsonl"
    if version == "baseline" or os.environ.get("KB_DIR"):
        pytest.skip("альтернативи існують лише для версії clean")
    alts = [json.loads(l) for l in open(p, encoding="utf-8")]
    err = _errors(SCHEMAS["alternative"], alts)
    assert not err and len(alts) >= 2, f"альтернативи: {err[:3]}"
