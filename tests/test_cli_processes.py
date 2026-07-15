"""Separazione dei processi stack/versions (fase 0 di percorso-v1).

``stack`` e ``versions`` sono processi indipendenti come ``sweep`` e
``stack``: stesso ``study.yml``, sottocomandi e cartelle di output propri.
``cmd_stack`` ignora il blocco ``versions:`` (lo stack com'e' scritto e'
l'istanza di partenza del percorso); ``cmd_versions`` lo richiede e scrive
in ``yaml/versions/versions.yml``.
"""
import os

import pytest
import yaml

from granstudies import __main__ as cli
from granstudies.errors import SpecError


# Documento con blocco versions E default nel let: valido anche senza
# iniezione (stile documentato: il default tiene lo studio renderizzabile
# come stack puro, decisione "partenza-nel-materiale").
DOC_WITH_DEFAULT = {
    "study_id": "s_processes",
    "seed": 7,
    "duration": 10,
    "samples_dir": "samples",
    "base": {"onset": 0, "sample": "corpus.wav"},
    "axes": {
        "density": {
            "path": "density",
            "baseline": 50,
            "n": 4,
            "base": {"expr": "env + d", "let": {"env": [[0, 40], [1, 60]], "d": 0}},
            "range": 0,
        },
    },
    "stack": {},
    "streams": {"fermo": {}, "mobile": {}},
    "versions": {"d": {"values": [1, 2]}},
}


def _write_study(tmp_path, monkeypatch, doc):
    sdir = tmp_path / "studies" / doc["study_id"]
    sdir.mkdir(parents=True)
    (sdir / "study.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    monkeypatch.setattr(cli, "study_dir", lambda study: os.path.join(str(tmp_path), "studies", study))
    monkeypatch.setattr(cli, "gen_dir", lambda s: os.path.join(str(tmp_path), "generated", s))
    return doc["study_id"]


# --- cmd_stack ignora versions -----------------------------------------------

def test_cmd_stack_with_versions_block_writes_pure_stack(tmp_path, monkeypatch):
    """Il blocco versions non tocca lo stack: stream_id nudi, niente repliche."""
    study = _write_study(tmp_path, monkeypatch, DOC_WITH_DEFAULT)
    assert cli.cmd_stack(study) == 0
    out = os.path.join(str(tmp_path), "generated", study, "yaml", "stack", "stack.yml")
    with open(out) as fh:
        doc = yaml.safe_load(fh)
    ids = [s["stream_id"] for s in doc["streams"]]
    assert ids == ["fermo", "mobile"]
    assert doc["duration"] == 10


def test_cmd_stack_without_let_default_raises(tmp_path, monkeypatch):
    """Senza default nel let lo stack puro non e' risolvibile: errore, non
    fallback silenzioso su versions (il confine tra i processi e' netto)."""
    doc = yaml.safe_load(yaml.safe_dump(DOC_WITH_DEFAULT))
    doc["study_id"] = "s_nodefault"
    del doc["axes"]["density"]["base"]["let"]["d"]
    study = _write_study(tmp_path, monkeypatch, doc)
    with pytest.raises(SpecError):
        cli.cmd_stack(study)


# --- cmd_versions --------------------------------------------------------------

def test_cmd_versions_writes_document_in_own_dir(tmp_path, monkeypatch):
    study = _write_study(tmp_path, monkeypatch, DOC_WITH_DEFAULT)
    assert cli.cmd_versions(study) == 0
    out = os.path.join(str(tmp_path), "generated", study, "yaml", "versions", "versions.yml")
    with open(out) as fh:
        doc = yaml.safe_load(fh)
    ids = [s["stream_id"] for s in doc["streams"]]
    assert ids == ["fermo__d=1", "mobile__d=1", "fermo__d=2", "mobile__d=2"]
    assert [s["onset"] for s in doc["streams"]] == [0, 0, 10, 10]
    assert doc["duration"] == 20
    # Lo stack non viene scritto dal processo versions.
    stack_out = os.path.join(str(tmp_path), "generated", study, "yaml", "stack", "stack.yml")
    assert not os.path.exists(stack_out)


def test_cmd_versions_without_block_is_noop(tmp_path, monkeypatch):
    """Attivazione per presenza, come sweep e stack: senza blocco, messaggio
    e uscita pulita."""
    doc = yaml.safe_load(yaml.safe_dump(DOC_WITH_DEFAULT))
    doc["study_id"] = "s_noversions"
    del doc["versions"]
    study = _write_study(tmp_path, monkeypatch, doc)
    assert cli.cmd_versions(study) == 0
    out = os.path.join(str(tmp_path), "generated", study, "yaml", "versions", "versions.yml")
    assert not os.path.exists(out)


def test_parser_has_versions_subcommand():
    args = cli.build_parser().parse_args(["versions", "s_x"])
    assert args.command == "versions"
    assert args.study == "s_x"


# --- cmd_sv: ramo versions ------------------------------------------------------

def test_cmd_sv_exports_versions_document(tmp_path, monkeypatch):
    """Con blocco versions e artefatti presenti, sv emette la sessione del
    documento versions accanto a quella dello stack (workflow d'ascolto)."""
    study = _write_study(tmp_path, monkeypatch, DOC_WITH_DEFAULT)
    g = os.path.join(str(tmp_path), "generated", study)
    for sub, name in (("stack", "stack"), ("versions", "versions")):
        os.makedirs(os.path.join(g, "yaml", sub), exist_ok=True)
        os.makedirs(os.path.join(g, "audio", sub), exist_ok=True)
        with open(os.path.join(g, "yaml", sub, f"{name}.yml"), "w") as fh:
            fh.write("streams: []\n")
        with open(os.path.join(g, "audio", sub, f"{name}.aif"), "wb") as fh:
            fh.write(b"")

    calls = []
    import granstudies.sv_export as sv_export
    monkeypatch.setattr(sv_export, "stack_to_sv",
                        lambda variant, audio, out, layout: calls.append(("doc", variant, out)))
    monkeypatch.setattr(sv_export, "stack_stems_to_sv",
                        lambda variant, audio_dir, out: False)

    assert cli.cmd_sv(study, layout="multi") == 0
    variants = [c[1] for c in calls]
    assert any(os.path.join("yaml", "stack", "stack.yml") in v for v in variants)
    assert any(os.path.join("yaml", "versions", "versions.yml") in v for v in variants)
    outs = [c[2] for c in calls]
    assert any(os.path.join("sv", "versions", f"{study}_versions.sv") in o for o in outs)
