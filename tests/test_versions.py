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
    generate_versions_documents,
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


def test_inject_reaches_nested_expr_let():
    # expr annidato in let (issue #28): il nodo annidato che nomina la
    # variabile riceve l'iniezione nel *proprio* let, ombreggiando il default
    data = _study({"d": {"values": [1, 2]}})
    data["axes"]["density"]["base"] = {
        "expr": "g * 2",
        "let": {"g": {"expr": "d + 1", "let": {"d": 0}}},
    }
    out = inject_combo(data, {"d": 10})
    node = out["axes"]["density"]["base"]
    assert node["let"]["g"]["let"]["d"] == 10
    from granstudies.expr import eval_expr

    assert eval_expr(node["expr"], node["let"]) == 22


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


# --- chiavi riservate onset/duration del blocco versions (issue #26) -----------

def test_reserved_keys_are_not_variables():
    data = _study({
        "d": {"values": [1, 2]},
        "onset": {"values": [0, 30]},
        "duration": {"values": [10, 10]},
    })
    # niente errore "non referenziata": onset/duration non sono variabili di
    # scope, e non compaiono tra i valori risolti.
    assert parse_versions(data) == {"d": [1, 2]}


def test_only_reserved_keys_errors():
    data = _study({"onset": {"values": [0, 30]}})
    with pytest.raises(SpecError, match="variabil"):
        parse_versions(data)


def test_onset_values_wrong_length_errors():
    data = _study({"d": {"values": [1, 2, 3]}, "onset": {"values": [0, 10]}})
    with pytest.raises(SpecError, match="onset"):
        generate_versions_document(data, "vtest", output_sr=None)


def test_onset_band_with_explicit_n_mismatch_errors():
    data = _study({
        "d": {"values": [1, 2, 3]},
        "onset": {"base": 0, "range": 10, "n": 2},
    })
    with pytest.raises(SpecError, match="n"):
        generate_versions_document(data, "vtest", output_sr=None)


def test_onset_negative_errors():
    data = _study({"d": {"values": [1, 2]}, "onset": {"values": [-1, 5]}})
    with pytest.raises(SpecError, match="onset"):
        generate_versions_document(data, "vtest", output_sr=None)


def test_reserved_duration_non_positive_errors():
    data = _study({"d": {"values": [1, 2]}, "duration": {"values": [0, 10]}})
    with pytest.raises(SpecError, match="duration"):
        generate_versions_document(data, "vtest", output_sr=None)


def test_onset_key_positions_versions_absolutely():
    data = _study({"d": {"values": [1, 2]}, "onset": {"values": [3, 7]}})
    doc = generate_versions_document(data, "vtest", output_sr=None)
    onsets = [s["onset"] for s in doc["streams"]]
    assert onsets == [3, 3, 7, 7]             # sovrapposte: legittimo
    assert doc["duration"] == 27              # max(onset + duration) = 7 + 20


def test_onset_ramp_without_step_spreads_over_versions():
    data = _study({"d": {"values": [1, 2, 3]}, "onset": {"ramp": {"start": 0, "stop": 100}}})
    doc = generate_versions_document(data, "vtest", output_sr=None)
    onsets = sorted({s["onset"] for s in doc["streams"]})
    assert onsets == [0, 50, 100]             # linspace: n = numero versioni


def test_onset_ramp_with_step_wrong_count_errors():
    data = _study({"d": {"values": [1, 2, 3]}, "onset": {"ramp": {"start": 0, "stop": 10, "step": 10}}})
    with pytest.raises(SpecError, match="onset"):
        generate_versions_document(data, "vtest", output_sr=None)


def test_onset_band_deterministic_with_derived_seed():
    data = _study({"d": {"values": [1, 2, 3]}, "onset": {"base": 0, "range": 50}})
    a = generate_versions_document(data, "vtest", output_sr=None)
    b = generate_versions_document(data, "vtest", output_sr=None)
    assert [s["onset"] for s in a["streams"]] == [s["onset"] for s in b["streams"]]
    assert all(0 <= s["onset"] <= 50 for s in a["streams"])


def test_stream_onset_relative_to_version_onset():
    data = _study({"d": {"values": [1, 2]}, "onset": {"values": [3, 7]}})
    data["streams"]["mobile"] = {"onset": 2}  # onset per-stream (issue #26)
    doc = generate_versions_document(data, "vtest", output_sr=None)
    by_id = {s["stream_id"]: s for s in doc["streams"]}
    assert by_id["mobile__d=1"]["onset"] == 5     # 3 + 2
    assert by_id["mobile__d=2"]["onset"] == 9     # 7 + 2


def test_duration_key_is_version_default_stream_wins():
    data = _study({"d": {"values": [1, 2]}, "duration": {"values": [5, 8]}})
    data["streams"]["fermo"] = {
        "duration": 4,                        # la duration propria vince
        "axes": {"density": {"base": {"expr": "env"}}},
    }
    doc = generate_versions_document(data, "vtest", output_sr=None)
    by_id = {s["stream_id"]: s for s in doc["streams"]}
    assert by_id["fermo__d=1"]["duration"] == 4
    assert by_id["fermo__d=2"]["duration"] == 4
    assert by_id["mobile__d=1"]["duration"] == 5   # default di versione
    assert by_id["mobile__d=2"]["duration"] == 8


def test_duration_key_without_onset_concatenates_on_generated_durations():
    data = _study({"d": {"values": [1, 2, 3]}, "duration": {"values": [5, 8, 2]}})
    doc = generate_versions_document(data, "vtest", output_sr=None)
    onsets = sorted({s["onset"] for s in doc["streams"]})
    assert onsets == [0, 5, 13]               # cumsum delle durate generate
    assert doc["duration"] == 15              # 13 + 2


def test_reserved_duration_works_without_top_level_duration():
    data = _study({"d": {"values": [1, 2]}, "duration": {"values": [5, 8]}})
    del data["duration"]
    doc = generate_versions_document(data, "vtest", output_sr=None)
    onsets = [s["onset"] for s in doc["streams"]]
    assert onsets == [0, 0, 5, 5]
    assert doc["duration"] == 13


def test_onset_key_with_per_stream_durations_no_top_level():
    data = _study({"d": {"values": [1, 2]}, "onset": {"values": [0, 30]}})
    del data["duration"]
    data["streams"]["fermo"] = {
        "duration": 10,
        "axes": {"density": {"base": {"expr": "env"}}},
    }
    data["streams"]["mobile"] = {"duration": 6}
    doc = generate_versions_document(data, "vtest", output_sr=None)
    assert doc["duration"] == 40              # 30 + 10


# --- split per variabile esterna -----------------------------------------------

def _study_dg(versions):
    """Fixture a due variabili: ``g`` deve essere referenziata da un'expr,
    altrimenti scatta la guardia anti-refuso di ``parse_versions``."""
    data = _study(versions)
    data["axes"]["density"]["range"] = {"expr": "g", "let": {"g": 0}}
    return data


def test_split_one_document_per_outer_value():
    """La prima variabile e' il confine di file: N_d documenti, ognuno con le
    sole combo di quel d, ribasato a zero."""
    data = _study_dg({"d": {"values": [1, 2]}, "g": {"values": [4, 5, 6]}})
    docs = generate_versions_documents(data, "vtest", output_sr=None)
    assert [label for label, _ in docs] == ["d=1", "d=2"]
    for label, doc in docs:
        ids = [s["stream_id"] for s in doc["streams"]]
        assert len(ids) == 6                  # 3 valori di g x 2 stream
        assert all(label in i for i in ids)
        assert min(s["onset"] for s in doc["streams"]) == 0
        assert doc["duration"] == 60          # 3 versioni x 20 s


def test_split_preserves_relative_layout_with_explicit_onset():
    """Con onset espliciti la ribasatura toglie solo l'offset del gruppo: i
    buchi e le distanze interne restano quelli scritti."""
    data = _study_dg({
        "d": {"values": [1, 2]},
        "g": {"values": [4, 5]},
        "onset": {"values": [0, 25, 100, 140]},
    })
    docs = generate_versions_documents(data, "vtest", output_sr=None)
    assert [sorted({s["onset"] for s in doc["streams"]}) for _, doc in docs] == [
        [0, 25], [0, 40],
    ]
