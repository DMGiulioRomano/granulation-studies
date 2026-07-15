"""Test del processo ``percorso``: istanze di spread distribuite sul tempo reale.

Il blocco top-level ``percorso:`` (issue #29) orchestra lo stack lungo una
timeline — strategy enumerata (``onset:``) o camminata (``arco:`` + ``passo:``)
— e dichiara traiettorie in grammatica-Env, campionate all'onset reale di ogni
istanza e iniettate negli scope ``let`` come fa ``versions``. Nessun prodotto
cartesiano: i valori cambiano insieme, appaiati sul tempo.
"""
import pytest

from granstudies.errors import SpecError
from granstudies.percorso import parse_percorso


# --- documento base condiviso dai test ---------------------------------------

def _study(percorso, **over):
    data = {
        "study_id": "ptest",
        "seed": 7,
        "base": {"onset": 0, "sample": "corpus.wav"},
        "axes": {
            "density": {
                "path": "density",
                "baseline": 50,
                "n": 4,
                "base": {
                    "expr": "env + w * 10",
                    "let": {"env": [[0, 40], [1, 60]], "w": 0},
                },
                "range": 0,
            },
        },
        "stack": {},
        "streams": {"fermo": {}},
        "percorso": percorso,
    }
    data.update(over)
    return data


# --- strategy: mutua esclusione ----------------------------------------------

def test_onset_with_arco_errors():
    data = _study({"onset": {"values": [0, 10]}, "arco": 60, "w": 1})
    with pytest.raises(SpecError, match="strategy"):
        parse_percorso(data)


def test_onset_with_passo_errors():
    data = _study({"onset": {"values": [0, 10]}, "passo": 5, "w": 1})
    with pytest.raises(SpecError, match="strategy"):
        parse_percorso(data)


def test_k_alone_errors_explaining_strategies():
    data = _study({"k": 8, "w": 1})
    with pytest.raises(SpecError) as exc:
        parse_percorso(data)
    # il messaggio spiega le due strategy
    assert "onset" in str(exc.value)
    assert "arco" in str(exc.value)


def test_empty_block_errors():
    with pytest.raises(SpecError, match="percorso"):
        parse_percorso(_study({}))


def test_block_not_dict_errors():
    with pytest.raises(SpecError, match="percorso"):
        parse_percorso(_study([1, 2]))


def test_requires_stack():
    data = _study({"arco": 60, "passo": 10, "w": 1})
    del data["stack"]
    with pytest.raises(SpecError, match="stack"):
        parse_percorso(data)


def test_coexists_with_versions():
    data = _study({"arco": 60, "passo": 10, "w": 1})
    data["versions"] = {"d": {"values": [1, 2]}}
    spec = parse_percorso(data)
    assert spec.strategy == "camminata"


# --- strategy enumerata: k posseduto da onset ---------------------------------

def test_enumerata_values_own_k():
    data = _study({"onset": {"values": [0, 10, 25]}, "w": 1})
    spec = parse_percorso(data)
    assert spec.strategy == "enumerata"
    assert spec.k == 3


def test_enumerata_k_crosscheck_ok():
    data = _study({"onset": {"values": [0, 10, 25]}, "k": 3, "w": 1})
    assert parse_percorso(data).k == 3


def test_enumerata_k_crosscheck_discordant_errors():
    data = _study({"onset": {"values": [0, 10, 25]}, "k": 4, "w": 1})
    with pytest.raises(SpecError, match="discord"):
        parse_percorso(data)


def test_enumerata_ramp_with_step_owns_k():
    data = _study({"onset": {"ramp": {"start": 0, "stop": 60, "step": 20}}, "w": 1})
    assert parse_percorso(data).k == 4    # 0, 20, 40, 60


def test_enumerata_ramp_without_step_requires_k():
    data = _study({"onset": {"ramp": {"start": 0, "stop": 60}}, "w": 1})
    with pytest.raises(SpecError, match="k"):
        parse_percorso(data)


def test_enumerata_ramp_without_step_with_k_ok():
    data = _study({"onset": {"ramp": {"start": 0, "stop": 60}}, "k": 4, "w": 1})
    assert parse_percorso(data).k == 4


def test_enumerata_band_with_n_owns_k():
    data = _study({"onset": {"base": 0, "range": 60, "n": 5}, "w": 1})
    assert parse_percorso(data).k == 5


def test_enumerata_band_without_n_requires_k():
    data = _study({"onset": {"base": 0, "range": 60}, "w": 1})
    with pytest.raises(SpecError, match="k"):
        parse_percorso(data)


def test_enumerata_k_not_int_errors():
    data = _study({"onset": {"ramp": {"start": 0, "stop": 60}}, "k": 2.5, "w": 1})
    with pytest.raises(SpecError, match="inter"):
        parse_percorso(data)


# --- strategy camminata: arco + passo ------------------------------------------

def test_camminata_parses():
    data = _study({"arco": 180, "passo": {"base": [30, 8]}, "w": 1})
    spec = parse_percorso(data)
    assert spec.strategy == "camminata"
    assert spec.arco == 180
    assert spec.passo.kind == "band"
    assert spec.k is None   # emerge dalla camminata, non si dichiara


def test_camminata_passo_scalar_is_constant():
    data = _study({"arco": 60, "passo": 10, "w": 1})
    spec = parse_percorso(data)
    assert spec.passo.kind == "const"


def test_camminata_arco_without_passo_errors():
    data = _study({"arco": 60, "w": 1})
    with pytest.raises(SpecError, match="passo"):
        parse_percorso(data)


def test_camminata_passo_without_arco_errors():
    data = _study({"passo": 10, "w": 1})
    with pytest.raises(SpecError, match="arco"):
        parse_percorso(data)


def test_camminata_k_declared_errors():
    data = _study({"arco": 60, "passo": 10, "k": 6, "w": 1})
    with pytest.raises(SpecError, match="k"):
        parse_percorso(data)


def test_camminata_arco_not_scalar_errors():
    data = _study({"arco": {"base": [60, 120]}, "passo": 10, "w": 1})
    with pytest.raises(SpecError, match="arco"):
        parse_percorso(data)


def test_camminata_arco_not_positive_errors():
    data = _study({"arco": 0, "passo": 10, "w": 1})
    with pytest.raises(SpecError, match="arco"):
        parse_percorso(data)


# --- grammatica delle traiettorie ----------------------------------------------

def test_trajectory_scalar_is_constant():
    data = _study({"arco": 60, "passo": 10, "w": 0.5})
    assert parse_percorso(data).variables["w"].kind == "const"


def test_trajectory_band_grammar():
    data = _study({
        "arco": 60, "passo": 10,
        "w": {"base": [0, 1], "range": 0.1,
              "drift": {"step": 0.2}, "distribution": "gaussian", "seed": 3},
    })
    assert parse_percorso(data).variables["w"].kind == "band"


def test_trajectory_expr_node():
    data = _study({
        "arco": 60, "passo": 10,
        "w": {"expr": "env * 2", "let": {"env": [0, 0.5]}},
    })
    assert parse_percorso(data).variables["w"].kind == "expr"


def test_trajectory_values_rejected_with_hint():
    data = _study({"arco": 60, "passo": 10, "w": {"values": [0, 1]}})
    with pytest.raises(SpecError, match="indicizzat"):
        parse_percorso(data)


def test_trajectory_ramp_rejected_with_hint():
    data = _study({"arco": 60, "passo": 10, "w": {"ramp": {"start": 0, "stop": 1}}})
    with pytest.raises(SpecError, match="indicizzat"):
        parse_percorso(data)


def test_trajectory_band_with_n_rejected():
    # le traiettorie non possiedono mai il conteggio
    data = _study({"arco": 60, "passo": 10, "w": {"base": [0, 1], "n": 5}})
    with pytest.raises(SpecError, match="conteggio"):
        parse_percorso(data)


def test_trajectory_band_extra_keys_rejected():
    data = _study({"arco": 60, "passo": 10, "w": {"base": [0, 1], "foo": 3}})
    with pytest.raises(SpecError, match="foo"):
        parse_percorso(data)


def test_trajectory_unrecognized_form_errors():
    data = _study({"arco": 60, "passo": 10, "w": [0, 1]})
    with pytest.raises(SpecError, match="traiettoria"):
        parse_percorso(data)


def test_trajectory_expr_mixed_with_band_errors():
    data = _study({
        "arco": 60, "passo": 10,
        "w": {"expr": "env", "let": {"env": [0, 1]}, "base": 0},
    })
    with pytest.raises(SpecError, match="strategy|expr|base"):
        parse_percorso(data)


# --- nomi riservati e guardia anti-refuso ---------------------------------------

@pytest.mark.parametrize("name", ["i", "n", "pi", "e"])
def test_reserved_scope_names_rejected(name):
    data = _study({"arco": 60, "passo": 10, name: 0.5, "w": 1})
    with pytest.raises(SpecError, match="riservat"):
        parse_percorso(data)


def test_unreferenced_variable_errors():
    data = _study({"arco": 60, "passo": 10, "w": 1, "zz": 3})
    with pytest.raises(SpecError, match="referenziata"):
        parse_percorso(data)


def test_variable_referenced_in_spread_patch_counts():
    data = _study({"arco": 60, "passo": 10, "w": 1, "g": 2})
    data["streams"] = {
        "coro": {"spread": {"n": 3, "over": {
            "base.volume": {"expr": "g * (i + 1)", "let": {"g": 1}},
        }}},
        "fermo": {},
    }
    spec = parse_percorso(data)
    assert set(spec.variables) == {"w", "g"}


# --- duration: traiettoria con unit --------------------------------------------

def test_duration_scalar_default_unit_factor():
    data = _study({"arco": 60, "passo": 10, "duration": 1.3, "w": 1})
    spec = parse_percorso(data)
    assert spec.duration.kind == "const"
    assert spec.duration_unit == "factor"


def test_duration_band_with_unit_s():
    data = _study({"arco": 60, "passo": 10,
                   "duration": {"base": [30, 8], "unit": "s"}, "w": 1})
    spec = parse_percorso(data)
    assert spec.duration.kind == "band"
    assert spec.duration_unit == "s"


def test_duration_expr_with_unit():
    data = _study({"arco": 60, "passo": 10,
                   "duration": {"expr": "1 + 1", "unit": "s"}, "w": 1})
    spec = parse_percorso(data)
    assert spec.duration.kind == "expr"
    assert spec.duration_unit == "s"


def test_duration_unknown_unit_errors():
    data = _study({"arco": 60, "passo": 10,
                   "duration": {"base": 1, "unit": "ms"}, "w": 1})
    with pytest.raises(SpecError, match="unit"):
        parse_percorso(data)


def test_duration_absent_is_legato():
    data = _study({"arco": 60, "passo": 10, "w": 1})
    spec = parse_percorso(data)
    assert spec.duration is None
    assert spec.duration_unit == "factor"


def test_percorso_without_variables_is_valid():
    # la timeline possiede tutto: la pura ripetizione dello stack e' legittima
    data = _study({"arco": 60, "passo": 10})
    spec = parse_percorso(data)
    assert spec.variables == {}
