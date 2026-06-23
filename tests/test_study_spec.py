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
