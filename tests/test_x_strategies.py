import pytest

from granstudies.x_strategies import linear, resolve_x, walk, x_owns_n


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


# --- resolve_x (linear = assenza dell'asse dal blocco stack) ---------------------

def test_resolve_x_default_is_linear():
    # Config vuota o assente -> linear (n dalla Y).
    assert resolve_x({}, n=3) == [0.0, 0.5, 1.0]
    assert resolve_x(None, n=3) == [0.0, 0.5, 1.0]


def test_resolve_x_rejects_walk_with_external_n():
    # Una entry con 'base' e' una camminata (possiede n): non risolvibile con
    # un n dalla Y.
    with pytest.raises(ValueError):
        resolve_x({"base": 5}, n=10)


def test_resolve_x_rejects_entry_without_base():
    # Una entry sotto stack senza 'base' e' malformata (niente piu' nome-strategy).
    with pytest.raises(ValueError):
        resolve_x({"seed": 3}, n=5)


# --- walk (i tempi emergono dalla frequenza, la X possiede n) --------------------

def test_walk_deterministic_with_seed():
    a = walk(duration=25.0, base=[[0, 3], [1, 10]], range=[[0, 1], [1, 1]], seed=7)
    b = walk(duration=25.0, base=[[0, 3], [1, 10]], range=[[0, 1], [1, 1]], seed=7)
    assert a == b


def test_walk_different_seed_differs():
    a = walk(duration=25.0, base=[[0, 3], [1, 10]], range=[[0, 1], [1, 1]], seed=1)
    b = walk(duration=25.0, base=[[0, 3], [1, 10]], range=[[0, 1], [1, 1]], seed=2)
    assert a != b


def test_walk_times_sorted_normalized_start_at_zero():
    times = walk(duration=10.0, base=5, range=2, seed=0)
    assert times[0] == 0.0
    assert times == sorted(times)
    assert all(0.0 <= t < 1.0 for t in times)


def test_walk_n_emerges_from_frequency():
    # Banda collassata (range 0): f=5 Hz esatti su 10 s -> passo 0.2 s -> 50 punti.
    times = walk(duration=10.0, base=5, range=0, seed=0)
    assert len(times) == 50


def test_walk_deterministic_branch_never_hits_t_one():
    # range assente = camminata deterministica: come la stocastica, mai un punto
    # esatto su t=1.0 (il bordo e' coperto dall'hold dell'envelope).
    times = walk(duration=10.0, base=5)
    assert all(t < 1.0 for t in times)


def test_walk_higher_frequency_more_points():
    lo = walk(duration=10.0, base=2, range=0.5, seed=3)
    hi = walk(duration=10.0, base=20, range=0.5, seed=3)
    assert len(hi) > len(lo)


def test_walk_frequency_envelope_densifies_where_high():
    # Frequenza bassa nella prima meta', alta nella seconda: piu' punti dopo 0.5.
    base = {"type": "step", "points": [[0, 2], [0.5, 40]]}
    times = walk(duration=10.0, base=base, range=0, seed=0)
    first = [t for t in times if t < 0.5]
    second = [t for t in times if t >= 0.5]
    assert len(second) > len(first)


def test_walk_curve_warps_frequency_envelope():
    # curve dentro l'Env di base: la frequenza scende con u^2 -> resta alta piu'
    # a lungo (piu' punti nella prima meta') rispetto alla discesa lineare.
    lin = walk(duration=10.0, base=[[0, 10], [1, 1]], seed=0)
    crv = walk(duration=10.0, base={"points": [[0, 10], [1, 1]], "curve": 2}, seed=0)
    assert len([t for t in crv if t < 0.5]) > len([t for t in lin if t < 0.5])


def test_walk_rejects_non_positive_frequency():
    with pytest.raises(ValueError):
        walk(duration=10.0, base=0, range=0, seed=0)


def test_walk_caps_runaway_frequency():
    with pytest.raises(ValueError):
        walk(duration=10.0, base=1e9, range=0, seed=0)


def test_walk_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        walk(duration=0.0, base=5, range=0, seed=0)


# --- n-ownership -----------------------------------------------------------------

def test_x_owns_n_true_when_base_present():
    assert x_owns_n({"base": 5}) is True
    assert x_owns_n({"base": [[0, 3], [1, 10]], "range": 1, "seed": 7}) is True
    assert x_owns_n({}) is False
    assert x_owns_n({"seed": 3}) is False
    assert x_owns_n(None) is False
