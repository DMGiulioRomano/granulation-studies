"""La pagina del laboratorio: i parametri, le finestre, i sample."""
import json
import os

from granstudies.graph import build_html, write_graph


def _payload(html_text):
    start = html_text.index("const D = ") + len("const D = ")
    return json.loads(html_text[start:html_text.index("\n", start)].rstrip(";"))


def test_la_pagina_porta_con_se_i_parametri_del_laboratorio(tmp_path):
    """Il payload e' tutto qui: lo studio e le tacche fra cui si sceglie."""
    lab = {"base": {"volume": 12}, "params": [{"path": "grain.duration",
                                               "values": [0.001, 0.064],
                                               "kind": "num"}]}
    d = _payload(build_html("s01", lab))
    assert d["study"] == "s01"
    assert d["lab"]["params"][0]["path"] == "grain.duration"
    assert d["lab"]["base"] == {"volume": 12}


def test_write_graph_scrive_sempre_e_conta_i_parametri(tmp_path):
    """Non guarda piu' il disco: senza audio la pagina serve lo stesso."""
    out = str(tmp_path / "graph.html")
    assert write_graph("s01", out, {"base": {}, "params": [{"path": "a"}]}) == 1
    assert os.path.exists(out)
    assert write_graph("s01", out, {"base": {}, "params": []}) == 0


def test_le_finestre_sono_quelle_dell_engine_non_quelle_dello_studio():
    """Tutte le 16 del catalogo, col profilo vero: e' una scelta per stream."""
    from granstudies.__main__ import _finestre

    env = _finestre()
    assert len(env) == 16
    for nome in ("hanning", "expodec", "rexpodec", "rectangle"):
        assert nome in env
    # hanning parte e finisce a zero, rectangle e' piatta a uno: se il profilo
    # venisse da un'approssimazione scritta qui, questo non lo direbbe nessuno.
    assert env["hanning"][0] == 0.0 and env["hanning"][-1] == 0.0
    assert max(env["hanning"]) > 0.99
    assert set(env["rectangle"]) == {1.0}


def test_i_sample_sono_i_file_della_cartella(tmp_path):
    """Le tacche del `sample` non stanno nello study.yml: sono i file su disco."""
    from granstudies.graph import campioni

    (tmp_path / "sub").mkdir()
    for nome in ("b.wav", "a.flac", "note.md", "sub/c.aif"):
        (tmp_path / nome).write_bytes(b"")
    # Relativi alla cartella dei sample: e' cosi' che l'engine li risolve.
    assert campioni(str(tmp_path)) == ["a.flac", "b.wav", "sub/c.aif"]


# --- la CLI: `graph` e `serve` ---------------------------------------------

import yaml

from granstudies import __main__ as cli


def _studio(tmp_path, monkeypatch, doc, nome="lab01"):
    """Uno studio su disco, con la radice del repo spostata in ``tmp_path``."""
    sdir = tmp_path / "studies" / nome
    sdir.mkdir(parents=True)
    (sdir / "study.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    (tmp_path / "samples").mkdir()
    (tmp_path / "samples" / "voce.wav").write_bytes(b"")
    monkeypatch.setattr(cli, "REPO_ROOT", str(tmp_path))
    return nome


DOC = {
    "samples_dir": "samples",
    "base": {"onset": 0, "duration": 4, "sample": "voce.wav", "density": 20},
    "axes": {"grain.duration": {"baseline": 0.05, "values": [0.01, 0.05]}},
    "for_each": {"base.distribution": {"values": [0, 1]}},
}


def test_graph_scrive_una_pagina_sola_anche_con_for_each(tmp_path, monkeypatch):
    """Il laboratorio e' uno per studio: le tacche sono quelle di tutto il
    documento, assi esterni compresi, e non si riscrive per combinazione."""
    study = _studio(tmp_path, monkeypatch, DOC)
    assert cli.main(["graph", study]) == 0
    root = tmp_path / "generated" / study
    assert [p.name for p in root.iterdir()] == ["graph.html"]
    params = {p["path"]: p for p in _payload((root / "graph.html").read_text())["lab"]["params"]}
    assert params["grain.duration"]["values"] == [0.01, 0.05]
    assert params["distribution"]["values"] == [0, 1]          # da for_each: base.*
    assert params["sample"] == {"path": "sample", "values": ["voce.wav"], "kind": "cat"}
    # Senza tacche: si scrivono a mano, con i limiti dell'engine dove li sa.
    for libero in ("volume", "pan", "pan_range"):
        assert params[libero]["free"] is True and params[libero]["values"] == []


def test_graph_senza_values_lo_dice_ma_scrive_la_pagina(tmp_path, monkeypatch, capsys):
    """Sample, volume e pan ci sono sempre: contarli fra le tacche teneva muto
    l'avviso. E' un avviso e non un errore, perche' `make serve` viene dopo."""
    doc = {k: v for k, v in DOC.items() if k != "for_each"}
    doc["axes"] = {"density": {"baseline": 20, "ramp": {"start": 1, "stop": 10, "step": 5}}}
    study = _studio(tmp_path, monkeypatch, doc)
    assert cli.main(["graph", study]) == 0
    assert "`values:`" in capsys.readouterr().err
    assert (tmp_path / "generated" / study / "graph.html").exists()


def test_serve_senza_la_pagina_chiede_graph(tmp_path, monkeypatch, capsys):
    """Senza `graph.html` il browser troverebbe un 404: meglio dirlo prima,
    col comando che la scrive — non `sweep`, che la pagina non la fa."""
    from granstudies import serve

    def non_servire(*a, **k):
        raise AssertionError("ha preso la porta senza una pagina da servire")

    monkeypatch.setattr(serve, "crea", non_servire)
    study = _studio(tmp_path, monkeypatch, DOC)
    (tmp_path / "generated" / study / "yaml").mkdir(parents=True)   # c'e' uno sweep
    assert cli.cmd_serve(study, port=0) == 1
    err = capsys.readouterr().err
    assert f"graph {study}" in err and "sweep" not in err
