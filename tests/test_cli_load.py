"""Caricamento spec dalla CLI: ``_load_spec`` deve risolvere le stream.

Nei documenti in stile stack-test il documento base e' incompleto per
costruzione (la ``n`` delle bande vive negli override di stream): validare
il grezzo, come faceva ``_load_spec``, produce falsi positivi su studi in
cui ogni stream e' valida.
"""
import os

import pytest
import yaml

from granstudies import __main__ as cli


BASE_INCOMPLETE = {
    "study_id": "s_stack",
    "duration": 10,
    "samples_dir": "samples",
    "base": {"onset": 0, "duration": 5, "sample": "corpus.wav"},
    "axes": {
        # Banda senza n: valida solo dopo l'override di stream.
        "density": {"path": "density", "baseline": 20, "base": 4, "range": 8},
    },
    "stack": {},
    "streams": {
        "lineare": {"axes": {"density": {"n": 6}}},
        "camminata": {"stack": {"density": {"base": 2, "range": 3}}},
    },
}


def _write_study(tmp_path, monkeypatch, doc):
    sdir = tmp_path / "studies" / doc["study_id"]
    sdir.mkdir(parents=True)
    (sdir / "study.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    monkeypatch.setattr(cli, "study_dir", lambda study: os.path.join(str(tmp_path), "studies", study))
    return doc["study_id"]


def test_load_spec_resolves_streams(tmp_path, monkeypatch):
    """Base incompleto + stream valide: _load_spec non deve sollevare."""
    study = _write_study(tmp_path, monkeypatch, BASE_INCOMPLETE)
    spec = cli._load_spec(study)
    assert spec.samples_dir == "samples"


def test_load_spec_single_stream_unchanged(tmp_path, monkeypatch):
    doc = {
        "study_id": "s_single",
        "samples_dir": "samples",
        "base": {"density": 20},
        "axes": {"a": {"path": "density", "baseline": 20, "values": [5, 50]}},
    }
    study = _write_study(tmp_path, monkeypatch, doc)
    spec = cli._load_spec(study)
    assert spec.study_id == "s_single"
    assert spec.stream_id is None
    assert spec.axis("a").values == [5, 50]


def test_load_spec_invalid_stream_still_raises(tmp_path, monkeypatch):
    """La validazione per-stream resta: una stream rotta deve fallire."""
    doc = dict(BASE_INCOMPLETE, study_id="s_broken")
    doc["streams"] = {"rotta": {}}  # nessun override: la banda resta senza n
    study = _write_study(tmp_path, monkeypatch, doc)
    with pytest.raises(ValueError):
        cli._load_spec(study)
