import pytest

from granstudies.value_generators import ramp, rand, resolve


def test_rand_deterministic_within_band():
    a = rand(n=8, min=0.001, max=0.01, seed=1988)
    b = rand(n=8, min=0.001, max=0.01, seed=1988)
    assert a == b                       # stesso seed -> stessa sequenza
    assert len(a) == 8
    assert all(0.001 <= v <= 0.01 for v in a)


def test_rand_different_seed_differs():
    assert rand(n=8, min=0, max=1, seed=1) != rand(n=8, min=0, max=1, seed=2)


def test_rand_time_varying_band_interpolates():
    # Banda collassata (min==max mobili): il valore e' forzato all'interpolazione.
    assert rand(n=3, min=[0.0, 1.0], max=[0.0, 1.0], seed=0) == [0.0, 0.5, 1.0]


def test_rand_band_breakpoints_control_when_it_changes():
    # min/max come [[t, v], ...]: tieni 0 fino a t=0.5, poi sali a 10.
    # Banda collassata (min==max) -> valore forzato all'interpolazione.
    band = [[0, 0], [0.5, 0], [1, 10]]
    assert rand(n=3, min=band, max=band, seed=0) == [0.0, 0.0, 10.0]


def test_rand_band_step_interpolation_holds_then_jumps():
    # type: step tiene il valore sinistro e salta al breakpoint.
    # points [[0,0],[1,10]], n=3 (frac 0/0.5/1): step -> [0,0,10] (linear -> [0,5,10]).
    band = {"type": "step", "points": [[0, 0], [1, 10]]}
    assert rand(n=3, min=band, max=band, seed=0) == [0.0, 0.0, 10.0]


def test_rand_rejects_bad_config():
    with pytest.raises(ValueError):
        rand(n=0, min=0, max=1)
    with pytest.raises(ValueError):
        rand(n=3, min=1, max=0)   # min > max


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
