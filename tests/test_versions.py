"""Test del processo ``versions``: repliche dello stack concatenate per onset.

Il blocco top-level ``versions:`` dichiara variabili (vocabolario dei
generatori Y) che vengono iniettate negli scope ``let`` dei nodi-expr del
documento; ogni combinazione (prodotto cartesiano, ordine di dichiarazione)
replica gli stream dello stack con onset scalato di ``k * duration``.
"""
import copy

import pytest

from granstudies.errors import SpecError
from granstudies.versions import (
    generate_versions_document,
    inject_combo,
    parse_versions,
    version_combos,
)


# --- documento base condiviso dai test --------------------------------------

def _study(versions):
    return {
        "study_id": "vtest",
        "seed": 7,
        "duration": 20,
        "base": {"onset": 0, "sample": "corpus.wav"},
        "axes": {
            "density": {
                "path": "density",
                "baseline": 50,
                "n": 4,
                "base": {
                    "expr": "env + d",
                    "let": {"env": [[0, 40], [1, 60]], "d": 0},
                },
                "range": 0,
            },
        },
        "stack": {},
        "streams": {
            "fermo": {
                "axes": {"density": {"base": {"expr": "env"}}},
            },
            "mobile": {},
        },
        "versions": versions,
    }


# --- parse e validazione -----------------------------------------------------

def test_parse_values_generator():
    data = _study({"d": {"values": [1, 2, 3]}})
    out = parse_versions(data)
    assert out == {"d": [1, 2, 3]}


def test_parse_ramp_generator():
    data = _study({"d": {"ramp": {"start": 1, "stop": 3, "step": 1}}})
    assert parse_versions(data) == {"d": [1, 2, 3]}


def test_parse_band_generator_deterministic():
    data = _study({"d": {"n": 3, "base": 0, "range": 10, "seed": 1}})
    a = parse_versions(data)
    b = parse_versions(data)
    assert a == b
    assert len(a["d"]) == 3
    assert all(0 <= v <= 10 for v in a["d"])


def test_parse_band_without_n_errors():
    data = _study({"d": {"base": 0, "range": 10}})
    with pytest.raises(SpecError, match="'n'"):
        parse_versions(data)


def test_empty_block_errors():
    data = _study({})
    with pytest.raises(SpecError, match="versions"):
        parse_versions(data)


def test_reserved_names_error():
    for name in ("i", "n", "pi", "e"):
        data = _study({name: {"values": [1]}})
        # la variabile riservata non e' referenziata, ma l'errore giusto e'
        # quello sul nome, non sul riferimento mancante.
        with pytest.raises(SpecError, match="riservat"):
            parse_versions(data)


def test_unreferenced_var_errors():
    data = _study({"zeta": {"values": [1, 2]}})
    with pytest.raises(SpecError, match="zeta"):
        parse_versions(data)


def test_versions_requires_stack_block():
    data = _study({"d": {"values": [1]}})
    del data["stack"]
    with pytest.raises(SpecError, match="stack"):
        generate_versions_document(data, "vtest", output_sr=None)


def test_versions_requires_duration():
    data = _study({"d": {"values": [1]}})
    del data["duration"]
    with pytest.raises(SpecError, match="duration"):
        generate_versions_document(data, "vtest", output_sr=None)


# --- prodotto cartesiano -----------------------------------------------------

def test_combos_single_var():
    assert version_combos({"d": [1, 2, 3]}) == [{"d": 1}, {"d": 2}, {"d": 3}]


def test_combos_two_vars_lexicographic_declaration_order():
    combos = version_combos({"f": [50, 100], "d": [1, 2]})
    assert combos == [
        {"f": 50, "d": 1},
        {"f": 50, "d": 2},
        {"f": 100, "d": 1},
        {"f": 100, "d": 2},
    ]


# --- iniezione nello scope let ------------------------------------------------

def test_inject_shadows_let_default():
    data = _study({"d": {"values": [1, 2]}})
    out = inject_combo(data, {"d": 2})
    node = out["axes"]["density"]["base"]
    assert node["let"]["d"] == 2
    assert node["expr"] == "env + d"       # l'espressione non si tocca


def test_inject_only_where_referenced():
    data = _study({"d": {"values": [1]}})
    # lo stream 'fermo' ha un expr che NON nomina d: il suo let (ereditato
    # via deep-merge) non deve ricevere l'iniezione.
    out = inject_combo(data, {"d": 1})
    fermo = out["streams"]["fermo"]["axes"]["density"]["base"]
    assert "let" not in fermo or "d" not in (fermo.get("let") or {})


def test_inject_does_not_mutate_input():
    data = _study({"d": {"values": [1]}})
    snapshot = copy.deepcopy(data)
    inject_combo(data, {"d": 1})
    assert data == snapshot


# --- documento generato --------------------------------------------------------

def _doc(versions):
    return generate_versions_document(_study(versions), "vtest", output_sr=None)


def test_document_replicates_streams_per_combo():
    doc = _doc({"d": {"values": [1, 2, 3]}})
    ids = [s["stream_id"] for s in doc["streams"]]
    assert len(ids) == 6                    # 3 versioni x 2 stream
    assert ids[0] == "fermo__d=1"
    assert ids[1] == "mobile__d=1"
    assert ids[-1] == "mobile__d=3"


def test_document_onsets_shifted_by_version():
    doc = _doc({"d": {"values": [1, 2]}})
    onsets = [s["onset"] for s in doc["streams"]]
    assert onsets == [0, 0, 20, 20]
    durations = {s["duration"] for s in doc["streams"]}
    assert durations == {20}
    assert doc["duration"] == 40            # copre l'ultima versione


def test_document_injected_values_reach_envelopes():
    doc = _doc({"d": {"values": [1, 2]}})
    by_id = {s["stream_id"]: s for s in doc["streams"]}

    def ys(sid):
        return [v for _, v in by_id[sid]["density"]["points"]]

    # fermo campiona env (40 -> 60); mobile = env + d, identico a meno
    # dell'offset (stessi seed -> stessa sequenza in ogni versione).
    base = ys("fermo__d=1")
    assert ys("fermo__d=2") == base
    assert ys("mobile__d=1") == [pytest.approx(v + 1) for v in base]
    assert ys("mobile__d=2") == [pytest.approx(v + 2) for v in base]


def test_document_two_vars_stream_labels():
    data = _study({"f": {"values": [50, 100]}, "d": {"values": [1]}})
    data["axes"]["density"]["base"]["expr"] = "env * f / 50 + d"
    data["axes"]["density"]["base"]["let"]["f"] = 50
    doc = generate_versions_document(data, "vtest", output_sr=None)
    ids = [s["stream_id"] for s in doc["streams"]]
    assert ids[0] == "fermo__f=50__d=1"
    assert ids[-1] == "mobile__f=100__d=1"


def test_stream_own_onset_preserved_inside_version():
    data = _study({"d": {"values": [1, 2]}})
    data["streams"]["mobile"] = {"base": {"onset": 2}}
    doc = generate_versions_document(data, "vtest", output_sr=None)
    by_id = {s["stream_id"]: s for s in doc["streams"]}
    assert by_id["mobile__d=1"]["onset"] == 2
    assert by_id["mobile__d=2"]["onset"] == 22
