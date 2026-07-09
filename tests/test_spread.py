import pytest

from granstudies.errors import SpecError
from granstudies.spread import expand_spreads


def _streams(**entries):
    """Dict ``streams:`` di comodo (l'ordine di inserimento e' quello YAML)."""
    return dict(entries)


# --- passthrough -------------------------------------------------------------

def test_no_spread_passthrough():
    streams = _streams(base={}, altra={"base": {"volume": -12}})
    assert expand_spreads(streams) == streams


def test_none_entry_passthrough():
    streams = {"base": None}
    assert expand_spreads(streams) == streams


# --- espansione con values ---------------------------------------------------

def _spread_entry(**extra):
    entry = {
        "spread": {
            "over": {"base.pointer.start": {"values": [0.1, 0.2, 0.3]}},
        },
    }
    entry.update(extra)
    return entry


def test_values_expansion_names_and_paths():
    out = expand_spreads(_streams(v=_spread_entry()))
    assert list(out) == ["v_1", "v_2", "v_3"]
    assert out["v_1"]["base"]["pointer"]["start"] == 0.1
    assert out["v_3"]["base"]["pointer"]["start"] == 0.3
    for entry in out.values():
        assert "spread" not in entry


def test_common_override_preserved_on_every_generated():
    entry = _spread_entry(base={"volume": -12})
    out = expand_spreads(_streams(v=entry))
    for name in ("v_1", "v_2", "v_3"):
        assert out[name]["base"]["volume"] == -12


def test_strategy_wins_over_common_override_on_same_path():
    entry = _spread_entry(base={"pointer": {"start": 0.9, "speed_ratio": 0.5}})
    out = expand_spreads(_streams(v=entry))
    assert out["v_2"]["base"]["pointer"]["start"] == 0.2
    # le chiavi sorelle del deep-set restano
    assert out["v_2"]["base"]["pointer"]["speed_ratio"] == 0.5


def test_generated_entries_are_independent_copies():
    out = expand_spreads(_streams(v=_spread_entry(base={"volume": -12})))
    out["v_1"]["base"]["volume"] = 0
    assert out["v_2"]["base"]["volume"] == -12
    assert out["v_1"]["sweep"] is not out["v_2"]["sweep"]


def test_order_preserved_around_spread():
    streams = _streams(a={}, v=_spread_entry(), z={})
    assert list(expand_spreads(streams)) == ["a", "v_1", "v_2", "v_3", "z"]


def test_zero_padding_follows_n_width():
    entry = {"spread": {"n": 12, "over": {"base.onset": {"values": list(range(12))}}}}
    out = expand_spreads(_streams(v=entry))
    assert list(out)[0] == "v_01"
    assert list(out)[-1] == "v_12"


def test_multiple_paths_paired_by_index():
    entry = {
        "spread": {
            "over": {
                "base.pointer.start": {"values": [0.1, 0.2]},
                "base.onset": {"values": [0, 5]},
            },
        },
    }
    out = expand_spreads(_streams(v=entry))
    assert list(out) == ["v_1", "v_2"]
    assert out["v_2"]["base"]["pointer"]["start"] == 0.2
    assert out["v_2"]["base"]["onset"] == 5


def test_values_accepts_non_numeric():
    entry = {"spread": {"over": {"base.sample": {"values": ["a.wav", "b.wav"]}}}}
    out = expand_spreads(_streams(v=entry))
    assert out["v_1"]["base"]["sample"] == "a.wav"
    assert out["v_2"]["base"]["sample"] == "b.wav"


# --- default sweep: solo stack -------------------------------------------------

def test_sweep_default_injected_empty():
    out = expand_spreads(_streams(v=_spread_entry()))
    for entry in out.values():
        assert entry["sweep"] == {"orders": [], "orderings": []}


def test_explicit_sweep_respected():
    entry = _spread_entry(sweep={"orders": [1]})
    out = expand_spreads(_streams(v=entry))
    for entry in out.values():
        assert entry["sweep"] == {"orders": [1]}


# --- risoluzione di n ----------------------------------------------------------

def test_n_explicit_must_match_values_len():
    entry = {"spread": {"n": 4, "over": {"base.onset": {"values": [1, 2, 3]}}}}
    with pytest.raises(SpecError) as exc:
        expand_spreads(_streams(v=entry))
    assert exc.value.stream == "v"


def test_two_values_with_different_len_raise():
    entry = {
        "spread": {
            "over": {
                "base.onset": {"values": [1, 2, 3]},
                "base.volume": {"values": [-6, -3]},
            },
        },
    }
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


def test_n_below_one_raises():
    entry = {"spread": {"n": 0, "over": {"base.onset": {"values": []}}}}
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


# --- errori di schema ------------------------------------------------------------

def test_spread_without_over_raises():
    with pytest.raises(SpecError):
        expand_spreads(_streams(v={"spread": {"n": 3}}))


def test_spread_with_empty_over_raises():
    with pytest.raises(SpecError):
        expand_spreads(_streams(v={"spread": {"n": 3, "over": {}}}))


def test_spread_unknown_keys_raise():
    entry = {"spread": {"count": 3, "over": {"base.onset": {"values": [1]}}}}
    with pytest.raises(SpecError) as exc:
        expand_spreads(_streams(v=entry))
    assert "count" in str(exc.value)


def test_spread_not_a_dict_raises():
    with pytest.raises(SpecError):
        expand_spreads(_streams(v={"spread": 8}))


def test_over_entry_without_strategy_raises():
    entry = {"spread": {"n": 2, "over": {"base.onset": {}}}}
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


def test_over_entry_with_two_strategies_raises():
    entry = {
        "spread": {
            "over": {"base.onset": {"values": [1, 2], "ramp": {"start": 0, "step": 1}}},
        },
    }
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))
