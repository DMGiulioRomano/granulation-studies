import pytest

from granstudies.x_strategies import linear, resolve_x


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
