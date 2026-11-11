"""T01–T02 · SHACL (pySHACL): форми quality/shapes.ttl."""
from pathlib import Path

import pyshacl
import pytest
from rdflib import Graph, Namespace

SH = Namespace("http://www.w3.org/ns/shacl#")
SHAPES = Path(__file__).resolve().parents[1] / "shapes.ttl"


def _results(rdf, severity):
    _, rg, _ = pyshacl.validate(rdf, shacl_graph=Graph().parse(SHAPES), inference="none")
    return [(str(rg.value(r, SH.focusNode)).split("#")[-1], str(rg.value(r, SH.resultMessage)))
            for r in rg.subjects(SH.resultSeverity, SH[severity])]


@pytest.mark.critical
def test_T01_shacl_no_violations(rdf):
    v = _results(rdf, "Violation")
    assert not v, f"SHACL Violation: {len(v)}; приклади: {v[:5]}"


@pytest.mark.warning
def test_T02_shacl_warnings(rdf):
    w = [x for x in _results(rdf, "Warning") if not x[1].startswith("S8")]   # S8 (пунктуація) — лише інформативно
    assert not w, f"SHACL Warning (повнота): {len(w)}; приклади: {w[:5]}"
