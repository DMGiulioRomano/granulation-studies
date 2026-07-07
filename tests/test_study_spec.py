import pytest

from granstudies.study_spec import parse_study_spec, resolve_streams


def _spec_dict():
    return {
        "study_id": "s",
        "base": {"density": 20, "volume": -6},
        "axes": {
            "a": {"path": "density", "baseline": 20, "values": [5, 50]},
            "b": {"path": "volume", "baseline": -6, "values": [-12, -3]},
        },
        "sweep": {"orders": [0, 1, 2]},
    }


def test_parse_basic():
    spec = parse_study_spec(_spec_dict())
    assert spec.study_id == "s"
    assert [ax.name for ax in spec.axes] == ["a", "b"]
    assert spec.orders == [0, 1, 2]
    assert spec.axis("a").path == "density"


def test_orders_default_is_all_orders():
    d = _spec_dict()
    del d["sweep"]
    spec = parse_study_spec(d)
    assert spec.orders == [1, 2]


def test_validate_rejects_order_too_high():
    d = _spec_dict()
    d["sweep"]["orders"] = [3]  # solo 2 assi
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_validate_rejects_value_out_of_bounds():
    d = _spec_dict()
    d["axes"]["a"]["values"] = [5, 99999]  # oltre density max
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_axis_ramp_generates_values():
    d = _spec_dict()
    d["axes"]["b"] = {
        "path": "volume",
        "baseline": -6,
        "ramp": {"start": -12, "stop": -6, "step": 3},
    }
    spec = parse_study_spec(d)
    assert spec.axis("b").values == [-12, -9, -6]


def test_axis_rejects_both_values_and_ramp():
    d = _spec_dict()
    d["axes"]["a"]["ramp"] = {"start": 5, "stop": 50, "step": 5}  # gia' ha values
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stream_ramp_override_replaces_inherited_values():
    # Uno stream che sceglie 'ramp' su un asse che nella base ha 'values':
    # il generatore dell'override rimpiazza quello ereditato (niente collisione).
    data = {
        "study_id": "s",
        "base": {"sample": "x.wav"},
        "axes": {"grain_duration": {"path": "grain.duration", "values": [0.001, 0.01]}},
        "sweep": {"mode": "envelope", "orders": [1]},
        "streams": {
            "prova": {
                "axes": {
                    "grain_duration": {"ramp": {"start": 0.003, "stop": 0.005, "step": 0.00025}}
                }
            }
        },
    }
    spec = resolve_streams(data)[0]
    assert spec.axis("grain_duration").values == [
        0.003, 0.00325, 0.0035, 0.00375, 0.004, 0.00425, 0.0045, 0.00475, 0.005,
    ]


def test_combine_defaults_to_cartesian():
    spec = parse_study_spec(_spec_dict())
    assert spec.combine == "cartesian"


def test_combine_parallel_is_read():
    d = _spec_dict()
    d["sweep"]["combine"] = "parallel"
    assert parse_study_spec(d).combine == "parallel"


def test_combine_rejects_unknown_value():
    d = _spec_dict()
    d["sweep"]["combine"] = "diagonale"
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_validate_rejects_empty_axes():
    with pytest.raises(ValueError):
        parse_study_spec({"axes": {}})


# --- single source of truth: baseline opzionale --------------------------------

def test_baseline_omitted_resolves_engine_default():
    # grain.duration ha default engine 0.05: omettere baseline lo risolve.
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {
                "grain_duration": {"path": "grain.duration", "values": [0.01, 0.2]},
            },
            "sweep": {"orders": [1]},
        }
    )
    assert spec.axis("grain_duration").baseline == 0.05


def test_baseline_omitted_distribution_resolves_default():
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {
                "distribution": {"path": "distribution", "values": [0.0, 1.0]},
            },
            "sweep": {"orders": [1]},
        }
    )
    assert spec.axis("distribution").baseline == 0.0


def test_density_without_baseline_raises():
    # density ha default=None nello schema: baseline obbligatorio.
    with pytest.raises(ValueError):
        parse_study_spec(
            {
                "study_id": "s",
                "base": {"sample": "x.wav"},
                "axes": {"density": {"path": "density", "values": [5, 50]}},
                "sweep": {"orders": [1]},
            }
        )


def test_pitch_without_baseline_raises():
    # pitch.* e' unit-driven (schema vuoto): baseline obbligatorio.
    with pytest.raises(ValueError):
        parse_study_spec(
            {
                "study_id": "s",
                "base": {"sample": "x.wav"},
                "axes": {"pitch": {"path": "pitch.semitones", "values": [-12, 0, 7]}},
                "sweep": {"orders": [1]},
            }
        )


def test_explicit_baseline_still_accepted():
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {"density": {"path": "density", "baseline": 20, "values": [5, 50]}},
            "sweep": {"orders": [1]},
        }
    )
    assert spec.axis("density").baseline == 20


def test_base_duration_absent_does_not_raise():
    # base.duration e' opzionale (calcolata per gli envelope).
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},  # niente duration
            "axes": {"density": {"path": "density", "baseline": 20, "values": [5, 50]}},
            "sweep": {"orders": [1]},
        }
    )
    assert "duration" not in spec.base


# --- timing envelope + sweep.mode ----------------------------------------------

def test_plateau_and_transition_read_from_sweep():
    # Invariante: axes conosce solo Y; il timing (X) appartiene al processo sweep.
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {
                "density": {"path": "density", "baseline": 20, "values": [5, 50]},
            },
            "sweep": {"orders": [1], "plateau": 3, "transition": 2},
        }
    )
    assert spec.plateau == 3
    assert spec.transition == 2


def test_plateau_in_axes_raises_with_migration_hint():
    # plateau/transition non vivono piu' in axes: errore chiaro, non un asse rotto.
    with pytest.raises(ValueError, match="sweep"):
        parse_study_spec(
            {
                "study_id": "s",
                "base": {"sample": "x.wav"},
                "axes": {
                    "plateau": 7,
                    "density": {"path": "density", "baseline": 20, "values": [5, 50]},
                },
                "sweep": {"orders": [1]},
            }
        )


def test_sweep_mode_accepts_envelope_discrete_both():
    for mode in ("envelope", "discrete", "both"):
        spec = parse_study_spec(
            {
                "study_id": "s",
                "base": {"sample": "x.wav"},
                "axes": {"density": {"path": "density", "baseline": 20, "values": [5, 50]}},
                "sweep": {"orders": [1], "mode": mode},
            }
        )
        assert spec.mode == mode


def test_sweep_mode_defaults_to_discrete():
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {"density": {"path": "density", "baseline": 20, "values": [5, 50]}},
            "sweep": {"orders": [1]},
        }
    )
    assert spec.mode == "discrete"


# --- blocco stack: (X per-asse) + modello seed -----------------------------------

def _stack_dict():
    return {
        "study_id": "s",
        "duration": 30,
        "base": {"sample": "x.wav"},
        "axes": {
            "seed": 1988,
            "density": {
                "path": "density",
                "baseline": 20,
                "rand": {"min": [[0, 10], [1, 2]], "max": [[0, 20], [1, 5]]},
                "interpolation": "cubic",
            },
            "grain_duration": {
                "path": "grain.duration",
                "ramp": {"start": 0.001, "stop": 0.002, "step": 0.0005},
            },
        },
        "stack": {
            "seed": 42,
            "density": {"rand": {"cps": {"base": [[0, 3], [1, 10]], "range": 1}}},
        },
    }


def test_stack_block_parsed_per_axis():
    spec = parse_study_spec(_stack_dict())
    assert spec.stack is not None
    assert "density" in spec.stack
    assert "seed" not in spec.stack            # chiave riservata, non un asse
    assert spec.stack_seed == 42
    assert spec.axes_seed == 1988


def test_axes_seed_is_not_an_axis():
    spec = parse_study_spec(_stack_dict())
    assert [ax.name for ax in spec.axes] == ["density", "grain_duration"]


def test_axis_carries_raw_generator_config():
    spec = parse_study_spec(_stack_dict())
    assert spec.axis("grain_duration").generator == {
        "ramp": {"start": 0.001, "stop": 0.002, "step": 0.0005}
    }
    assert "rand" in spec.axis("density").generator


def test_y_rand_without_n_deferred_when_x_rand():
    # La X possiede n: i valori Y non si enumerano al parse (emergono in stack).
    spec = parse_study_spec(_stack_dict())
    assert spec.axis("density").values == []
    assert spec.axis("density").defers_n() is True
    assert spec.axis("grain_duration").defers_n() is False


def test_y_rand_without_n_and_no_stack_raises():
    d = _stack_dict()
    del d["stack"]
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_y_rand_without_n_and_x_linear_raises():
    d = _stack_dict()
    d["stack"]["density"] = {"linear": {}}
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_x_rand_with_y_owning_n_raises():
    d = _stack_dict()
    d["axes"]["density"]["rand"]["n"] = 50    # Y con n + X-rand: conflitto
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stack_axis_unknown_raises():
    d = _stack_dict()
    d["stack"]["inesistente"] = {"linear": {}}
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stack_unknown_strategy_raises():
    d = _stack_dict()
    d["stack"]["density"] = {"accelerando": {}}
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stack_without_duration_raises():
    d = _stack_dict()
    del d["duration"]
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stack_seed_override_per_stream():
    d = _stack_dict()
    d["streams"] = {
        "voce_a": {"base": {"pointer": {"start": 0.1}}},
        "voce_b": {"stack": {"seed": 43}},
    }
    specs = {s.stream_id: s for s in resolve_streams(d)}
    assert specs["voce_a"].stack_seed == 42    # eredita il globale
    assert specs["voce_b"].stack_seed == 43    # override per-stream


def test_seed_autoderivation_per_stream_stable_and_decorrelated():
    d = _stack_dict()
    del d["stack"]["seed"]
    del d["axes"]["seed"]
    d["streams"] = {"voce_a": {}, "voce_b": {}}
    specs = {s.stream_id: s for s in resolve_streams(d)}
    a, b = specs["voce_a"], specs["voce_b"]
    # deterministici: due parse danno gli stessi seed
    again = {s.stream_id: s for s in resolve_streams(_dict_no_seeds())}
    assert a.resolved_y_seed() == again["voce_a"].resolved_y_seed()
    assert a.resolved_x_seed() == again["voce_a"].resolved_x_seed()
    # per-stream: stream diversi -> seed diversi (decorrelazione di default)
    assert a.resolved_y_seed() != b.resolved_y_seed()
    assert a.resolved_x_seed() != b.resolved_x_seed()
    # Y e X decorrelati anche dentro lo stesso stream
    assert a.resolved_y_seed() != a.resolved_x_seed()


def _dict_no_seeds():
    d = _stack_dict()
    del d["stack"]["seed"]
    del d["axes"]["seed"]
    d["streams"] = {"voce_a": {}, "voce_b": {}}
    return d


def test_global_seeds_win_over_autoderivation():
    spec = parse_study_spec(_stack_dict())
    assert spec.resolved_y_seed() == 1988
    assert spec.resolved_x_seed() == 42


def test_stream_x_strategy_override_replaces_inherited():
    # Uno stream che sceglie linear su un asse che nella base ha rand:
    # la strategy dell'override rimpiazza quella ereditata (niente collisione).
    d = _stack_dict()
    d["axes"]["density"]["rand"]["n"] = 8      # Y possiede n, cosi' linear e' valido
    d["stack"]["density"] = {"rand": {"cps": {"base": 5}}}
    del d["axes"]["density"]["rand"]["n"]      # torna senza n per la base
    d["streams"] = {
        "solo_linear": {
            "axes": {"density": {"rand": {"n": 8, "min": 0, "max": 10}}},
            "stack": {"density": {"linear": {}}},
        }
    }
    spec = [s for s in resolve_streams(d) if s.stream_id == "solo_linear"][0]
    assert spec.stack["density"] == {"linear": {}}
