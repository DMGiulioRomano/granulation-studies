import pytest

from granstudies.x_strategies import linear, rand, resolve_x, x_owns_n


# --- linear (default: tempi equispaziati) ---------------------------------------

def test_linear_five_points_equispaced():
    assert linear(n=5) == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_linear_single_point():
    assert linear(n=1) == [0.0]


def test_linear_two_points_are_extremes():
    assert linear(n=2) == [0.0, 1.0]


def test_linear_rejects_non_positive_n():
    with pytest.raises(ValueError):
        linear(n=0)


# --- resolve_x (dispatch dal nome della strategy) --------------------------------

def test_resolve_x_dispatches_to_linear():
    assert resolve_x({"linear": {}}, n=5) == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_resolve_x_default_is_linear():
    # Config vuota o assente -> strategy di default (linear, nessun parametro).
    assert resolve_x({}, n=3) == [0.0, 0.5, 1.0]
    assert resolve_x(None, n=3) == [0.0, 0.5, 1.0]


def test_resolve_x_rejects_unknown_strategy():
    with pytest.raises(ValueError):
        resolve_x({"accelerando": {}}, n=5)


def test_resolve_x_rejects_multiple_strategies():
    with pytest.raises(ValueError):
        resolve_x({"linear": {}, "rand": {}}, n=5)


# --- rand (rspline: i tempi emergono dalla frequenza, la X possiede n) -----------

def test_rand_deterministic_with_seed():
    cfg = {"base": [[0, 3], [1, 10]], "range": [[0, 1], [1, 1]]}
    a = rand(duration=25.0, cps=cfg, seed=7)
    b = rand(duration=25.0, cps=cfg, seed=7)
    assert a == b


def test_rand_different_seed_differs():
    cfg = {"base": [[0, 3], [1, 10]], "range": [[0, 1], [1, 1]]}
    assert rand(duration=25.0, cps=cfg, seed=1) != rand(duration=25.0, cps=cfg, seed=2)


def test_rand_times_sorted_normalized_start_at_zero():
    times = rand(duration=10.0, cps={"base": 5, "range": 2}, seed=0)
    assert times[0] == 0.0
    assert times == sorted(times)
    assert all(0.0 <= t < 1.0 for t in times)


def test_rand_n_emerges_from_frequency():
    # Banda collassata (range 0): f=5 Hz esatti su 10 s -> passo 0.2 s -> 50 punti.
    times = rand(duration=10.0, cps={"base": 5, "range": 0}, seed=0)
    assert len(times) == 50


def test_rand_higher_frequency_more_points():
    lo = rand(duration=10.0, cps={"base": 2, "range": 0.5}, seed=3)
    hi = rand(duration=10.0, cps={"base": 20, "range": 0.5}, seed=3)
    assert len(hi) > len(lo)


def test_rand_frequency_envelope_densifies_where_high():
    # Frequenza bassa nella prima meta', alta nella seconda: piu' punti dopo 0.5.
    cfg = {"base": {"type": "step", "points": [[0, 2], [0.5, 40]]}, "range": 0}
    times = rand(duration=10.0, cps=cfg, seed=0)
    first = [t for t in times if t < 0.5]
    second = [t for t in times if t >= 0.5]
    assert len(second) > len(first)


def test_rand_rejects_non_positive_frequency():
    with pytest.raises(ValueError):
        rand(duration=10.0, cps={"base": 0, "range": 0}, seed=0)


def test_rand_caps_runaway_frequency():
    with pytest.raises(ValueError):
        rand(duration=10.0, cps={"base": 1e9, "range": 0}, seed=0)


def test_rand_requires_cps_base():
    with pytest.raises(ValueError):
        rand(duration=10.0, cps={}, seed=0)


# --- n-ownership -----------------------------------------------------------------

def test_x_owns_n_true_for_rand_false_otherwise():
    assert x_owns_n({"rand": {"cps": {"base": 5}}}) is True
    assert x_owns_n({"linear": {}}) is False
    assert x_owns_n({}) is False
    assert x_owns_n(None) is False


def test_resolve_x_rejects_rand_with_external_n():
    # X-rand possiede n: risolverla con un n dalla Y e' un errore di n-ownership.
    with pytest.raises(ValueError):
        resolve_x({"rand": {"cps": {"base": 5}}}, n=10)
