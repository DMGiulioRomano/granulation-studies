import pytest

from granstudies.value_generators import ramp, resolve


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
