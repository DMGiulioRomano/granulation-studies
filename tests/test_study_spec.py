import pytest

from granstudies.study_spec import parse_study_spec


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

def test_plateau_and_transition_are_read():
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {
                "plateau": 7,
                "transition": 3,
                "density": {"path": "density", "baseline": 20, "values": [5, 50]},
            },
            "sweep": {"orders": [1]},
        }
    )
    assert spec.plateau == 7
    assert spec.transition == 3
    # plateau/transition non sono assi
    assert [ax.name for ax in spec.axes] == ["density"]


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
