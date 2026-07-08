import pytest

from granstudies.value_generators import (
    _interp_breakpoints,
    _threshold_at,
    ramp,
    rand,
    rand_at,
    resolve,
)


# --- curve: piega non lineare u^k del segmento (S1) ------------------------------

def test_curve_quadratic_on_known_segment():
    # u=0.5 su [[0,0],[1,10]]: lineare -> 5, curve 2 -> u^2=0.25 -> 2.5.
    assert _interp_breakpoints([[0, 0], [1, 10]], 0.5, curve=2) == 2.5


def test_curve_one_equals_linear():
    pts = [[0, 0], [1, 10]]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert _interp_breakpoints(pts, frac, curve=1) == _interp_breakpoints(pts, frac)


def test_curve_convex_opposite_below_one():
    # curve 0.5: u^0.5 > u -> sale piu' ripido all'inizio (valore > lineare).
    assert _interp_breakpoints([[0, 0], [1, 10]], 0.25, curve=0.5) == pytest.approx(5.0)


def test_curve_holds_at_borders_unchanged():
    # Fuori dai bordi la curve e' irrilevante: hold sul valore d'estremo.
    pts = [[0, 5], [1, 10]]
    assert _interp_breakpoints(pts, -0.1, curve=2) == 5
    assert _interp_breakpoints(pts, 1.5, curve=2) == 10


def test_curve_in_threshold_dict_form():
    spec = {"points": [[0, 0], [1, 10]], "curve": 2}
    assert _threshold_at(spec, 0.5) == 2.5


def test_curve_rejects_non_positive():
    with pytest.raises(ValueError):
        _interp_breakpoints([[0, 0], [1, 10]], 0.5, curve=0)
    with pytest.raises(ValueError):
        _interp_breakpoints([[0, 0], [1, 10]], 0.5, curve=-1)


def test_curve_with_step_type_raises():
    # type: step non ha rampa da piegare: curve != 1 e' un errore di config.
    with pytest.raises(ValueError):
        _threshold_at({"type": "step", "points": [[0, 0], [1, 10]], "curve": 2}, 0.5)


def test_curve_one_with_step_type_ok():
    # curve 1 (default esplicito) e' un no-op: convive con step.
    assert _threshold_at({"type": "step", "points": [[0, 0], [1, 10]], "curve": 1}, 0.5) == 0


def test_rand_deterministic_within_band():
    a = rand(n=8, base=0.001, range=0.009, seed=1988)
    b = rand(n=8, base=0.001, range=0.009, seed=1988)
    assert a == b                       # stesso seed -> stessa sequenza
    assert len(a) == 8
    assert all(0.001 <= v <= 0.01 for v in a)


def test_rand_different_seed_differs():
    assert rand(n=8, base=0, range=1, seed=1) != rand(n=8, base=0, range=1, seed=2)


def test_rand_time_varying_band_interpolates():
    # Banda collassata (range omesso, base mobile): valore forzato all'interpolazione.
    assert rand(n=3, base=[0.0, 1.0], seed=0) == [0.0, 0.5, 1.0]


def test_rand_band_breakpoints_control_when_it_changes():
    # base come [[t, v], ...]: tieni 0 fino a t=0.5, poi sali a 10.
    # Banda collassata (range omesso) -> valore forzato all'interpolazione.
    band = [[0, 0], [0.5, 0], [1, 10]]
    assert rand(n=3, base=band, seed=0) == [0.0, 0.0, 10.0]


def test_rand_band_step_interpolation_holds_then_jumps():
    # type: step tiene il valore sinistro e salta al breakpoint.
    # points [[0,0],[1,10]], n=3 (frac 0/0.5/1): step -> [0,0,10] (linear -> [0,5,10]).
    band = {"type": "step", "points": [[0, 0], [1, 10]]}
    assert rand(n=3, base=band, seed=0) == [0.0, 0.0, 10.0]


def test_rand_moving_range_widens_band():
    # range mobile [0 -> 1] su base fissa: al primo passo la banda e' collassata
    # (valore == base), all'ultimo e' [5, 6].
    out = rand(n=3, base=5, range=[0.0, 1.0], seed=0)
    assert out[0] == 5.0
    assert all(5.0 <= v <= 6.0 for v in out)


def test_rand_rejects_bad_config():
    with pytest.raises(ValueError):
        rand(n=0, base=0, range=1)
    with pytest.raises(ValueError):
        rand(n=3, base=1, range=-1)   # range negativo


def test_rand_at_deterministic_at_given_fracs():
    fracs = [0.0, 0.37, 0.81, 1.0]
    a = rand_at(fracs, base=0.001, range=0.009, seed=1988)
    b = rand_at(fracs, base=0.001, range=0.009, seed=1988)
    assert a == b
    assert len(a) == len(fracs)
    assert all(0.001 <= v <= 0.01 for v in a)


def test_rand_at_band_evaluated_at_real_times():
    # Banda collassata (range omesso, base mobile): il valore e' l'interpolazione
    # al frac REALE del punto, non all'indice i/(n-1) — coupling con la X-rand.
    band = [[0, 0], [1, 10]]
    assert rand_at([0.0, 0.25, 0.9], base=band, seed=0) == [0.0, 2.5, 9.0]


def test_rand_at_rejects_negative_range():
    with pytest.raises(ValueError):
        rand_at([0.0, 0.5], base=1, range=-1)


def test_rand_at_rejects_empty_fracs():
    with pytest.raises(ValueError):
        rand_at([], base=0, range=1)


def test_resolve_explicit_values_passthrough():
    assert resolve({"path": "x", "values": [1, 2, 3]}) == [1, 2, 3]


def test_resolve_dispatches_to_ramp():
    assert resolve({"path": "x", "ramp": {"start": 1, "stop": 3, "step": 1}}) == [1, 2, 3]


def test_resolve_rejects_no_generator_key():
    with pytest.raises(ValueError):
        resolve({"path": "x", "baseline": 0})


def test_resolve_rejects_multiple_generator_keys():
    with pytest.raises(ValueError):
        resolve({"path": "x", "values": [1], "ramp": {"start": 1, "stop": 3, "step": 1}})


def test_ramp_ascending_includes_endpoint_no_drift():
    # Il caso reale del diario: 0.003 -> 0.005 a passo 0.00025 = 9 gradini.
    assert ramp(0.003, 0.005, 0.00025) == [
        0.003, 0.00325, 0.0035, 0.00375, 0.004,
        0.00425, 0.0045, 0.00475, 0.005,
    ]


def test_ramp_step_not_dividing_does_not_overshoot():
    # 0.0021 / 0.00025 = 8.4 -> 8 gradini, ultimo 0.005 <= stop, mai oltre.
    out = ramp(0.003, 0.0051, 0.00025)
    assert out[-1] == 0.005
    assert out[-1] <= 0.0051


def test_ramp_rejects_non_positive_step():
    with pytest.raises(ValueError):
        ramp(0.003, 0.005, 0)


def test_ramp_descending():
    assert ramp(0.005, 0.003, 0.00025) == [
        0.005, 0.00475, 0.0045, 0.00425, 0.004,
        0.00375, 0.0035, 0.00325, 0.003,
    ]
