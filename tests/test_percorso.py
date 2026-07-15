"""Test del processo ``percorso``: istanze di spread distribuite sul tempo reale.

Il blocco top-level ``percorso:`` (issue #29) orchestra lo stack lungo una
timeline — strategy enumerata (``onset:``) o camminata (``arco:`` + ``passo:``)
— e dichiara traiettorie in grammatica-Env, campionate all'onset reale di ogni
istanza e iniettate negli scope ``let`` come fa ``versions``. Nessun prodotto
cartesiano: i valori cambiano insieme, appaiati sul tempo.
"""
import pytest

from granstudies.errors import SpecError
from granstudies.percorso import build_timeline, parse_percorso, resolve_durations


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


# --- timeline: strategy enumerata ----------------------------------------------

def _timeline(percorso, **over):
    data = _study(percorso, **over)
    spec = parse_percorso(data)
    return build_timeline(spec, data.get("study_id") or "study")


def test_enumerata_values_absolute_onsets():
    tl = _timeline({"onset": {"values": [0, 10, 25]}, "w": 1})
    assert tl.onsets == [0.0, 10.0, 25.0]
    assert tl.span == 25.0


def test_enumerata_ramp_step_grid():
    tl = _timeline({"onset": {"ramp": {"start": 0, "stop": 60, "step": 20}}, "w": 1})
    assert tl.onsets == [0.0, 20.0, 40.0, 60.0]


def test_enumerata_ramp_start_stop_equispaced_on_k():
    tl = _timeline({"onset": {"ramp": {"start": 0, "stop": 60}}, "k": 4, "w": 1})
    assert tl.onsets == [0.0, 20.0, 40.0, 60.0]


def test_enumerata_band_deterministic():
    p = {"onset": {"base": 0, "range": 60, "n": 4}, "w": 1}
    a, b = _timeline(p), _timeline(p)
    assert a.onsets == b.onsets
    assert len(a.onsets) == 4
    assert all(0 <= t <= 60 for t in a.onsets)


def test_enumerata_negative_onset_errors():
    with pytest.raises(SpecError, match="onset"):
        _timeline({"onset": {"values": [0, -5]}, "w": 1})


def test_enumerata_intervals_last_repeats():
    tl = _timeline({"onset": {"values": [0, 10, 25]}, "w": 1})
    # intervallo verso la prossima; l'ultima istanza usa l'ultimo intervallo noto
    assert tl.intervals == [10.0, 15.0, 15.0]


# --- timeline: strategy camminata ------------------------------------------------

def test_camminata_constant_passo_equispaced():
    tl = _timeline({"arco": 60, "passo": 10, "w": 1})
    assert tl.onsets == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    assert tl.intervals == [10.0] * 6
    assert tl.span == 60.0


def test_camminata_accumulates_passo_at_current_onset():
    # passo in rampa (banda collassata): accelerando deterministico
    tl = _timeline({"arco": 60, "passo": {"base": [10, 20]}, "w": 1})
    assert tl.onsets[0] == 0.0
    assert all(t < 60 for t in tl.onsets)
    for i, dt in enumerate(tl.intervals[:-1]):
        assert tl.onsets[i + 1] == pytest.approx(tl.onsets[i] + dt)
    # il passo cresce lungo l'arco: intervalli strettamente crescenti
    assert all(a < b for a, b in zip(tl.intervals, tl.intervals[1:]))


def test_camminata_passo_expr_constant():
    tl = _timeline({"arco": 30, "passo": {"expr": "5 + 5"}, "w": 1})
    assert tl.onsets == [0.0, 10.0, 20.0]


def test_camminata_passo_not_positive_errors():
    with pytest.raises(SpecError, match="passo"):
        _timeline({"arco": 60, "passo": 0, "w": 1})


def test_camminata_single_instance():
    tl = _timeline({"arco": 10, "passo": 25, "w": 1})
    assert tl.onsets == [0.0]
    assert tl.intervals == [25.0]


# --- duration: traiettoria, factor | s, legato di default -------------------------

def _durations(percorso, **over):
    data = _study(percorso, **over)
    spec = parse_percorso(data)
    sid = data.get("study_id") or "study"
    tl = build_timeline(spec, sid)
    return resolve_durations(spec, tl, sid)


def test_legato_default_enumerata():
    d = _durations({"onset": {"values": [0, 10, 25]}, "w": 1})
    assert d == [10.0, 15.0, 15.0]


def test_legato_default_camminata_last_uses_passo():
    # l'ultima istanza puo' sforare l'arco con la propria durata
    d = _durations({"arco": 60, "passo": 25, "w": 1})
    assert d == [25.0, 25.0, 25.0]   # onsets 0, 25, 50; 50 + 25 > 60


def test_factor_scales_interval():
    d = _durations({"onset": {"values": [0, 10, 25]}, "duration": 1.5, "w": 1})
    assert d == [15.0, 22.5, 22.5]


def test_factor_below_one_leaves_gaps():
    d = _durations({"arco": 40, "passo": 20, "duration": 0.5, "w": 1})
    assert d == [10.0, 10.0]


def test_unit_s_absolute():
    d = _durations({"arco": 40, "passo": 20,
                    "duration": {"base": 12, "unit": "s"}, "w": 1})
    assert d == [12.0, 12.0]


def test_duration_sampled_at_real_onset_camminata_norm_on_arco():
    # normalizzazione 0->1 sull'arco: onsets 0 e 30 su arco 60 -> frac 0 e 0.5
    d = _durations({"arco": 60, "passo": 30,
                    "duration": {"base": [[0, 10], [1, 20]], "unit": "s"}, "w": 1})
    assert d == [10.0, 15.0]


def test_duration_sampled_at_real_onset_enumerata_norm_on_last_onset():
    # normalizzazione sull'ultimo onset: 0, 10, 20 -> frac 0, 0.5, 1
    d = _durations({"onset": {"values": [0, 10, 20]},
                    "duration": {"base": [[0, 10], [1, 20]], "unit": "s"}, "w": 1})
    assert d == [10.0, 15.0, 20.0]


def test_enumerata_single_instance_factor_errors():
    with pytest.raises(SpecError, match="unit"):
        _durations({"onset": {"values": [0]}, "duration": 1.3, "w": 1})


def test_enumerata_single_instance_legato_errors():
    # il legato e' factor 1: senza intervallo di riferimento serve unit: s
    with pytest.raises(SpecError, match="unit"):
        _durations({"onset": {"values": [0]}, "w": 1})


def test_enumerata_single_instance_unit_s_ok():
    d = _durations({"onset": {"values": [0]},
                    "duration": {"base": 12, "unit": "s"}, "w": 1})
    assert d == [12.0]


def test_camminata_single_instance_legato_ok():
    # in camminata l'intervallo di riferimento esiste sempre: passo(t_K)
    d = _durations({"arco": 10, "passo": 25, "w": 1})
    assert d == [25.0]


def test_duration_not_positive_errors():
    with pytest.raises(SpecError, match="duration"):
        _durations({"arco": 40, "passo": 20,
                    "duration": {"base": 0, "unit": "s"}, "w": 1})


def test_legato_non_monotone_onsets_errors():
    with pytest.raises(SpecError, match="duration"):
        _durations({"onset": {"values": [0, 20, 10]}, "w": 1})
