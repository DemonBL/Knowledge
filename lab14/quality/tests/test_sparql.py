"""T03–T07 · інваріанти SPARQL (rdflib) над RDF-знімком: логічні та часові правила регламенту."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conflicts as K  # noqa: E402

PFX = K.PFX


@pytest.mark.critical
def test_T03_true_verdict_two_sources(rdf):
    rows = list(rdf.query(K.Q_TRUE_SOURCES))
    assert not rows, f"«правда» з < 2 офіційних джерел без complianceStatus: {[str(r.v).split('#')[1] for r in rows]}"


@pytest.mark.critical
def test_T04_fake_two_evidence(rdf):
    rows = list(rdf.query(K.Q_FAKE_EVIDENCE))
    assert not rows, f"«фейк/маніпуляція» з < 2 доказів: {[str(r.v).split('#')[1] for r in rows]}"


@pytest.mark.critical
def test_T05_no_refuted_and_confirmed(rdf):
    rows = list(rdf.query(K.Q_REFUTED_AND_CONFIRMED)) + list(rdf.query(K.Q_VERDICT_VS_OFFICIAL))
    assert not rows, f"суперечність вердикту й офіційного джерела: {rows[:5]}"


@pytest.mark.critical
def test_T06_temporal_flagged(rdf):
    rows = list(rdf.query(K.Q_VERDICT_BEFORE_PUB))
    assert not rows, f"вердикт раніше за публікацію без temporalFlag: {[str(r.v).split('#')[1] for r in rows]}"


@pytest.mark.critical
def test_T07_derived_not_before_parent(rdf):
    q = PFX + """SELECT ?a ?b WHERE { ?a hub:DERIVED_FROM ?b . ?a hub:publishedAt ?da . ?b hub:publishedAt ?db . FILTER (?da < ?db) }"""
    rows = list(rdf.query(q))
    assert not rows, f"похідна публікація раніша за батьківську: {rows[:5]}"
