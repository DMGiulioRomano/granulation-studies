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


def test_sweep_combine_removed_raises_with_migration_hint():
    # combine: parallel non esiste piu': l'accoppiamento degli assi vive nel
    # processo stack (stessa X, stesso n). Errore chiaro, non silenzio.
    d = _spec_dict()
    d["sweep"]["combine"] = "parallel"
    with pytest.raises(ValueError, match="stack"):
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
                # banda piatta senza n: la X-walk possiede il conteggio.
                "base": [[0, 10], [1, 2]],
                "range": [[0, 10], [1, 3]],
                "interpolation": "cubic",
            },
            "grain_duration": {
                "path": "grain.duration",
                "ramp": {"start": 0.001, "stop": 0.002, "step": 0.0005},
            },
        },
        "stack": {
            "seed": 42,
            "density": {"base": [[0, 3], [1, 10]], "range": 1},
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
    assert "band" in spec.axis("density").generator


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


def test_y_band_without_n_and_x_linear_raises():
    # Annullare l'entry stack riporta l'asse a linear: banda senza n senza
    # camminata-X e' un errore di n-ownership.
    d = _stack_dict()
    d["stack"]["density"] = None
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_x_walk_with_y_owning_n_raises():
    d = _stack_dict()
    d["axes"]["density"]["n"] = 50    # Y con n + X-walk: conflitto
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stack_axis_unknown_raises():
    d = _stack_dict()
    d["stack"]["inesistente"] = {"base": 5}
    with pytest.raises(ValueError):
        parse_study_spec(d)


def test_stack_entry_without_base_raises():
    # Una entry sotto stack senza 'base' e' malformata (niente piu' nome-strategy).
    d = _stack_dict()
    d["stack"]["density"] = {"range": 1}
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


# --- unit della camminata-X (hz | s), stessa catena del seed -----------------------

def test_stack_unit_reserved_key_parsed():
    d = _stack_dict()
    d["stack"]["unit"] = "s"
    spec = parse_study_spec(d)
    assert spec.stack_unit == "s"
    assert "unit" not in spec.stack            # chiave riservata, non un asse
    assert spec.resolved_x_unit() == "s"


def test_stack_unit_default_is_hz():
    spec = parse_study_spec(_stack_dict())
    assert spec.stack_unit is None
    assert spec.resolved_x_unit() == "hz"


def test_stack_unit_invalid_raises():
    d = _stack_dict()
    d["stack"]["unit"] = "ms"
    with pytest.raises(ValueError, match="unit"):
        parse_study_spec(d)


def test_stack_entry_unit_allowed_and_validated():
    d = _stack_dict()
    d["stack"]["density"]["unit"] = "s"
    spec = parse_study_spec(d)
    assert spec.stack["density"]["unit"] == "s"
    d["stack"]["density"]["unit"] = "hertz"
    with pytest.raises(ValueError, match="unit"):
        parse_study_spec(d)


def test_stack_unit_bpm_accepted_at_both_levels():
    d = _stack_dict()
    d["stack"]["unit"] = "bpm"
    d["stack"]["density"]["unit"] = "bpm"
    spec = parse_study_spec(d)
    assert spec.stack_unit == "bpm"
    assert spec.stack["density"]["unit"] == "bpm"


def test_stack_unit_override_per_stream():
    d = _stack_dict()
    d["stack"]["unit"] = "s"
    d["streams"] = {
        "voce_a": {},
        "voce_b": {"stack": {"unit": "hz"}},
    }
    specs = {s.stream_id: s for s in resolve_streams(d)}
    assert specs["voce_a"].stack_unit == "s"   # eredita il globale
    assert specs["voce_b"].stack_unit == "hz"  # override per-stream


# --- distribution e drift: plumbing di parse (issue #16) --------------------------

def test_sweep_band_axis_with_gaussian_and_drift():
    # Le nuove chiavi viaggiano con la banda (sibling di base/range) e i valori
    # si risolvono al parse, dentro la banda.
    d = _spec_dict()
    d["axes"]["a"] = {
        "path": "density", "baseline": 20,
        "n": 20, "base": 5, "range": 40,
        "distribution": "gaussian", "drift": {"step": 0.1},
    }
    spec = parse_study_spec(d)
    vals = spec.axis("a").values
    assert len(vals) == 20
    assert all(5 <= v <= 45 for v in vals)
    assert parse_study_spec(d).axis("a").values == vals   # deterministico


def test_axis_generator_carries_distribution_and_drift():
    d = _stack_dict()
    d["axes"]["density"]["distribution"] = "gaussian"
    d["axes"]["density"]["drift"] = {"step": 0.1}
    spec = parse_study_spec(d)
    params = spec.axis("density").generator["band"]
    assert params["distribution"] == "gaussian"
    assert params["drift"] == {"step": 0.1}


def test_stack_entry_accepts_distribution_and_drift():
    d = _stack_dict()
    d["stack"]["density"] = {
        "base": [[0, 3], [1, 10]], "range": 1,
        "distribution": "gaussian", "drift": {"step": 0.15},
    }
    spec = parse_study_spec(d)
    assert spec.stack["density"]["drift"] == {"step": 0.15}


def test_stack_entry_still_rejects_unknown_keys():
    d = _stack_dict()
    d["stack"]["density"]["sigma"] = 2
    with pytest.raises(ValueError, match="sigma"):
        parse_study_spec(d)


def test_stream_generator_switch_strips_drift_and_distribution():
    # Uno stream che passa a values deve perdere anche le nuove chiavi di banda
    # ereditate (come gia' base/range/n/seed).
    d = _stack_dict()
    d["axes"]["density"]["distribution"] = "gaussian"
    d["axes"]["density"]["drift"] = {"step": 0.1}
    d["streams"] = {
        "voce_a": {},
        "voce_b": {"axes": {"density": {"values": [5, 10]}},
                   "stack": {"density": None}},
    }
    specs = {s.stream_id: s for s in resolve_streams(d)}
    assert specs["voce_b"].axis("density").generator == {"values": [5, 10]}


def test_global_seeds_win_over_autoderivation():
    spec = parse_study_spec(_stack_dict())
    assert spec.resolved_y_seed() == 1988
    assert spec.resolved_x_seed() == 42


def test_stream_x_override_null_returns_to_linear():
    # Uno stream riporta un asse a linear annullando l'entry stack (stack: {asse:
    # null}); l'override Y porta una banda CON n (la Y torna a possedere n). Il
    # _replace_generators rimpiazza la banda ereditata senza collisione.
    d = _stack_dict()
    d["streams"] = {
        "solo_linear": {
            "axes": {"density": {"n": 8, "base": 0, "range": 10}},
            "stack": {"density": None},
        }
    }
    spec = [s for s in resolve_streams(d) if s.stream_id == "solo_linear"][0]
    assert "density" not in (spec.stack or {})        # entry annullata -> linear
    assert spec.axis("density").defers_n() is False    # la Y possiede n
    assert len(spec.axis("density").values) == 8


# --- generatori annidati (plan nested-generators) ---------------------------------

def test_nested_base_resolved_at_parse():
    d = {
        "study_id": "s",
        "base": {"sample": "x.wav"},
        "axes": {
            "a": {"path": "density", "baseline": 20, "n": 4,
                  "base": {"values": [1, 10]}, "range": 0},
        },
    }
    spec = parse_study_spec(d)
    assert spec.axis("a").values == pytest.approx([1.0, 4.0, 7.0, 10.0])


def test_nested_double_resolution_parse_equals_assembly():
    # Stesso seed -> il parse (sweep) e l'assemblaggio (stack) non divergono.
    from granstudies.stack import axis_envelope

    d = {
        "study_id": "s",
        "duration": 10,
        "base": {"sample": "x.wav"},
        "axes": {
            "a": {"path": "density", "baseline": 20, "n": 4,
                  "base": {"n": 3, "base": 0, "range": 9}, "range": 1},
        },
        "stack": {},
    }
    spec = parse_study_spec(d)
    env = axis_envelope(
        spec.axis("a").generator, None, 10.0,
        y_seed=spec.resolved_y_seed(), x_seed=spec.resolved_x_seed(),
    )
    assert [v for _, v in env] == spec.axis("a").values


def test_stack_config_accepts_nested_node_in_base():
    d = {
        "study_id": "s",
        "duration": 10,
        "base": {"sample": "x.wav"},
        "axes": {
            "a": {"path": "density", "baseline": 20,
                  "base": 0, "range": 9},
        },
        "stack": {"a": {"base": {"values": [2, 8]}, "range": 0.5}},
    }
    spec = parse_study_spec(d)
    assert spec.stack["a"]["base"] == {"values": [2, 8]}


def test_stream_override_merges_nested_env_dict():
    # La forma-nodo e' un dict: il merge di stream fonde le chiavi (type resta).
    data = {
        "study_id": "s",
        "base": {"sample": "x.wav"},
        "axes": {
            "a": {"path": "density", "baseline": 20, "n": 4,
                  "base": {"type": "step", "values": [0, 9]}, "range": 0},
        },
        "sweep": {"mode": "envelope", "orders": [1]},
        "streams": {"prova": {"axes": {"a": {"base": {"values": [1, 8]}}}}},
    }
    spec = [s for s in resolve_streams(data) if s.stream_id == "prova"][0]
    # type: step ereditato dal merge -> plateau: [1, 1, 1, 8]
    assert spec.axis("a").values == pytest.approx([1.0, 1.0, 1.0, 8.0])
