import pytest

from granstudies.stack import axis_envelope


# --- caso X linear (default): n dalla Y ------------------------------------------

def test_values_with_default_x_linear():
    env = axis_envelope({"values": [1, 2, 3]}, None, duration=30.0)
    assert env == [[0.0, 1], [0.5, 2], [1.0, 3]]


def test_ramp_with_explicit_x_linear():
    env = axis_envelope(
        {"ramp": {"start": 0.001, "stop": 0.002, "step": 0.0005}},
        {"linear": {}},
        duration=30.0,
    )
    assert [t for t, _ in env] == [0.0, 0.5, 1.0]
    assert [v for _, v in env] == [0.001, 0.0015, 0.002]


def test_rand_with_n_and_x_linear():
    env = axis_envelope(
        {"rand": {"n": 4, "min": 0, "max": 10, "seed": 1}}, None, duration=30.0
    )
    assert len(env) == 4
    assert [t for t, _ in env] == [0.0, pytest.approx(1 / 3), pytest.approx(2 / 3), 1.0]


def test_single_value_is_single_point():
    env = axis_envelope({"values": [42]}, None, duration=30.0)
    assert env == [[0.0, 42]]


# --- caso X-rand (rspline): la X possiede n, la Y segue --------------------------

def test_rspline_end_to_end_counts_match_and_deterministic():
    y = {"rand": {"min": 0, "max": 10}}
    x = {"rand": {"cps": {"base": 5, "range": 0}}}
    a = axis_envelope(y, x, duration=10.0, y_seed=1, x_seed=2)
    b = axis_envelope(y, x, duration=10.0, y_seed=1, x_seed=2)
    assert a == b
    assert len(a) == 50                       # n emerge: 5 Hz x 10 s
    times = [t for t, _ in a]
    assert times == sorted(times)
    assert all(0 <= v <= 10 for _, v in a)


def test_rspline_y_sampled_at_real_times():
    # Banda Y collassata e mobile: il valore DEVE essere l'interpolazione al
    # tempo reale del punto (coupling), non all'indice.
    band = [[0, 0], [1, 10]]
    y = {"rand": {"min": band, "max": band}}
    x = {"rand": {"cps": {"base": 5, "range": 0}}}
    env = axis_envelope(y, x, duration=10.0)
    for t, v in env:
        assert v == pytest.approx(10 * t, abs=1e-6)


def test_seed_in_axis_config_wins_over_global():
    y = {"rand": {"min": 0, "max": 10, "seed": 7}}
    x = {"rand": {"cps": {"base": 5, "range": 1}, "seed": 9}}
    a = axis_envelope(y, x, duration=10.0, y_seed=1, x_seed=1)
    b = axis_envelope(y, x, duration=10.0, y_seed=2, x_seed=2)
    assert a == b                             # i seed per-asse vincono sui globali


def test_global_seeds_apply_when_axis_has_none():
    y = {"rand": {"min": 0, "max": 10}}
    x = {"rand": {"cps": {"base": 5, "range": 1}}}
    a = axis_envelope(y, x, duration=10.0, y_seed=1, x_seed=1)
    b = axis_envelope(y, x, duration=10.0, y_seed=2, x_seed=2)
    assert a != b


# --- validazione n-ownership (nei due sensi) -------------------------------------

def test_x_rand_with_y_values_raises():
    with pytest.raises(ValueError):
        axis_envelope({"values": [1, 2]}, {"rand": {"cps": {"base": 5}}}, duration=10.0)


def test_x_rand_with_y_rand_with_n_raises():
    with pytest.raises(ValueError):
        axis_envelope(
            {"rand": {"n": 5, "min": 0, "max": 1}},
            {"rand": {"cps": {"base": 5}}},
            duration=10.0,
        )


def test_x_linear_with_y_rand_without_n_raises():
    with pytest.raises(ValueError):
        axis_envelope({"rand": {"min": 0, "max": 1}}, {"linear": {}}, duration=10.0)


def test_x_default_with_y_rand_without_n_raises():
    with pytest.raises(ValueError):
        axis_envelope({"rand": {"min": 0, "max": 1}}, None, duration=10.0)
