import pytest

from granstudies import yaml_loc
from granstudies.errors import SpecError
from granstudies.spread import expand_spreads
from granstudies.study_spec import resolve_streams


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


# --- strategy ramp ---------------------------------------------------------------

def test_ramp_full_owns_count():
    entry = {"spread": {"over": {"base.onset": {"ramp": {"start": 0, "stop": 6, "step": 2}}}}}
    out = expand_spreads(_streams(v=entry))
    assert list(out) == ["v_1", "v_2", "v_3", "v_4"]
    assert [out[k]["base"]["onset"] for k in out] == [0, 2, 4, 6]


def test_ramp_start_step_needs_n():
    entry = {
        "spread": {
            "n": 4,
            "over": {"base.pointer.start": {"ramp": {"start": 0.1, "step": 0.1}}},
        },
    }
    out = expand_spreads(_streams(v=entry))
    assert [out[k]["base"]["pointer"]["start"] for k in out] == [0.1, 0.2, 0.3, 0.4]


def test_ramp_start_step_without_n_raises():
    entry = {"spread": {"over": {"base.onset": {"ramp": {"start": 0, "step": 1}}}}}
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


def test_ramp_start_stop_is_linspace_over_n():
    entry = {
        "spread": {
            "n": 5,
            "over": {"base.volume": {"ramp": {"start": -12, "stop": 0}}},
        },
    }
    out = expand_spreads(_streams(v=entry))
    assert [out[k]["base"]["volume"] for k in out] == [-12, -9, -6, -3, 0]


def test_ramp_start_stop_with_n_1_holds_start():
    entry = {"spread": {"n": 1, "over": {"base.volume": {"ramp": {"start": -12, "stop": 0}}}}}
    out = expand_spreads(_streams(v=entry))
    assert out["v_1"]["base"]["volume"] == -12


def test_ramp_only_start_raises():
    entry = {"spread": {"n": 3, "over": {"base.onset": {"ramp": {"start": 0}}}}}
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


def test_ramp_full_count_mismatch_with_explicit_n_raises():
    entry = {
        "spread": {
            "n": 3,
            "over": {"base.onset": {"ramp": {"start": 0, "stop": 6, "step": 2}}},
        },
    }
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


# --- strategy banda ----------------------------------------------------------------

def test_band_draws_n_values_in_band():
    entry = {
        "spread": {
            "n": 6,
            "over": {"base.volume": {"base": -12, "range": 6}},
        },
    }
    out = expand_spreads(_streams(v=entry))
    vols = [out[k]["base"]["volume"] for k in out]
    assert len(vols) == 6
    assert all(-12 <= v <= -6 for v in vols)


def test_band_with_distribution_and_drift_in_spread():
    # Le chiavi di banda dell'issue #16 viaggiano anche nella strategy di spread.
    entry = {
        "spread": {
            "n": 6,
            "over": {"base.volume": {"base": -12, "range": 6,
                                     "distribution": "gaussian",
                                     "drift": {"step": 0.2}}},
        },
    }
    a = expand_spreads(_streams(v=entry))
    b = expand_spreads(_streams(v=entry))
    vols = [a[k]["base"]["volume"] for k in a]
    assert [b[k]["base"]["volume"] for k in b] == vols
    assert len(vols) == 6
    assert all(-12 <= v <= -6 for v in vols)


def test_band_explicit_seed_matches_band_generator():
    from granstudies.value_generators import band

    entry = {
        "spread": {
            "n": 4,
            "over": {"base.volume": {"base": -12, "range": 6, "seed": 42}},
        },
    }
    out = expand_spreads(_streams(v=entry))
    assert [out[k]["base"]["volume"] for k in out] == band(n=4, base=-12, range=6, seed=42)


def test_band_default_seed_deterministic_and_decorrelated_per_path():
    entry = {
        "spread": {
            "n": 5,
            "over": {
                "base.volume": {"base": -12, "range": 6},
                "base.pointer.start": {"base": 0.1, "range": 0.5},
            },
        },
    }
    out_a = expand_spreads(_streams(v=entry))
    out_b = expand_spreads(_streams(v=entry))
    vols = [out_a[k]["base"]["volume"] for k in out_a]
    starts = [out_a[k]["base"]["pointer"]["start"] for k in out_a]
    # deterministico tra run
    assert vols == [out_b[k]["base"]["volume"] for k in out_b]
    # path diversi si decorrelano da soli (frazioni della banda diverse)
    frac_v = [(v + 12) / 6 for v in vols]
    frac_s = [(s - 0.1) / 0.5 for s in starts]
    assert frac_v != frac_s


def test_band_with_inner_n_owns_count():
    entry = {"spread": {"over": {"base.volume": {"base": -12, "range": 6, "n": 3}}}}
    out = expand_spreads(_streams(v=entry))
    assert list(out) == ["v_1", "v_2", "v_3"]


def test_band_without_n_anywhere_raises():
    entry = {"spread": {"over": {"base.volume": {"base": -12, "range": 6}}}}
    with pytest.raises(SpecError):
        expand_spreads(_streams(v=entry))


def test_ramp_full_paired_with_band():
    entry = {
        "spread": {
            "over": {
                "base.onset": {"ramp": {"start": 0, "stop": 4, "step": 2}},
                "base.volume": {"base": -12, "range": 6},
            },
        },
    }
    out = expand_spreads(_streams(v=entry))
    assert list(out) == ["v_1", "v_2", "v_3"]
    assert all("volume" in out[k]["base"] for k in out)


# --- patch: l'esplicito ritocca il generato ---------------------------------------

def test_patch_merges_on_top_and_is_consumed():
    streams = _streams(v=_spread_entry(), v_2={"base": {"volume": -20}})
    out = expand_spreads(streams)
    assert list(out) == ["v_1", "v_2", "v_3"]     # la patch non e' un quarto stream
    assert out["v_2"]["base"]["volume"] == -20
    assert out["v_2"]["base"]["pointer"]["start"] == 0.2   # strategy preservata
    assert "volume" not in out["v_1"]["base"]


def test_patch_wins_on_strategy_path():
    streams = _streams(v=_spread_entry(), v_2={"base": {"pointer": {"start": 0.99}}})
    out = expand_spreads(streams)
    assert out["v_2"]["base"]["pointer"]["start"] == 0.99
    assert out["v_1"]["base"]["pointer"]["start"] == 0.1


def test_patch_defined_before_spread_applies():
    streams = _streams(v_2={"base": {"volume": -20}}, v=_spread_entry())
    out = expand_spreads(streams)
    assert list(out) == ["v_1", "v_2", "v_3"]
    assert out["v_2"]["base"]["volume"] == -20


def test_patch_none_entry_is_noop():
    streams = _streams(v=_spread_entry(), v_2=None)
    out = expand_spreads(streams)
    assert list(out) == ["v_1", "v_2", "v_3"]
    assert out["v_2"]["base"]["pointer"]["start"] == 0.2


def test_patch_can_reactivate_sweep():
    streams = _streams(v=_spread_entry(), v_2={"sweep": {"orders": [1]}})
    out = expand_spreads(streams)
    assert out["v_2"]["sweep"]["orders"] == [1]
    assert out["v_1"]["sweep"] == {"orders": [], "orderings": []}


def test_patch_with_spread_raises():
    streams = _streams(
        v={"spread": {"n": 2, "over": {"base.onset": {"values": [0, 1]}}}},
        v_2={"spread": {"n": 2, "over": {"base.onset": {"values": [5, 6]}}}},
    )
    with pytest.raises(SpecError) as exc:
        expand_spreads(streams)
    assert "v_2" in str(exc.value)


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


# --- integrazione con resolve_streams ---------------------------------------------

def _doc():
    return {
        "study_id": "s",
        "duration": 30,
        "base": {"onset": 0, "sample": "c.wav"},
        "axes": {"a": {"path": "density", "baseline": 20, "values": [5, 50]}},
        "streams": {
            "base": {},
            "v": {
                "spread": {
                    "n": 3,
                    "over": {"base.onset": {"ramp": {"start": 0, "step": 2}}},
                },
            },
        },
    }


def test_resolve_streams_expands_spread():
    specs = resolve_streams(_doc())
    assert [s.stream_id for s in specs] == ["base", "v_1", "v_2", "v_3"]
    onsets = [s.base["onset"] for s in specs[1:]]
    assert onsets == [0, 2, 4]


def test_resolve_streams_spread_has_sweep_off_by_default():
    specs = resolve_streams(_doc())
    by_id = {s.stream_id: s for s in specs}
    assert by_id["v_1"].orders == []
    assert by_id["v_1"].orderings == []
    # lo stream non-spread conserva il default (tutti gli ordini)
    assert by_id["base"].orders == [1]


def test_resolve_streams_applies_patch():
    doc = _doc()
    doc["streams"]["v_2"] = {"base": {"volume": -20}}
    specs = resolve_streams(doc)
    by_id = {s.stream_id: s for s in specs}
    assert len(specs) == 4
    assert by_id["v_2"].base["volume"] == -20
    assert by_id["v_2"].base["onset"] == 2


def test_generated_streams_have_decorrelated_seeds():
    specs = resolve_streams(_doc())
    by_id = {s.stream_id: s for s in specs}
    assert by_id["v_1"].resolved_y_seed() != by_id["v_2"].resolved_y_seed()


def test_spread_error_carries_line_and_stream():
    text = """\
study_id: s
base:
  onset: 0
axes:
  a: {path: density, baseline: 20, values: [5, 50]}
streams:
  v:
    spread:
      n: 3
      over:
        base.onset: {values: [1, 2]}
"""
    data, locs = yaml_loc.loads(text, source="study.yml")
    with pytest.raises(SpecError) as exc:
        resolve_streams(data, "s", locs=locs)
    assert exc.value.stream == "v"
    assert exc.value.source == "study.yml"
    assert exc.value.line == 8  # riga di streams.v.spread


# --- CLI: artefatto streams_expanded.yml (lo "yaml di aiuto") ----------------------

def _cli_study(tmp_path, monkeypatch, doc):
    import os

    import yaml as _yaml

    from granstudies import __main__ as cli

    sdir = tmp_path / "studies" / doc["study_id"]
    sdir.mkdir(parents=True)
    (sdir / "study.yml").write_text(_yaml.safe_dump(doc, sort_keys=False))
    monkeypatch.setattr(
        cli, "study_dir",
        lambda study: os.path.join(str(tmp_path), "studies", study),
    )
    monkeypatch.setattr(
        cli, "gen_dir",
        lambda study: os.path.join(str(tmp_path), "generated", study),
    )
    return cli, doc["study_id"], tmp_path / "generated" / doc["study_id"]


def _stack_doc():
    doc = _doc()
    doc["stack"] = {}
    doc["streams"]["v"]["spread"]["over"]["base.onset"] = {
        "ramp": {"start": 0, "step": 2},
    }
    return doc


def test_cmd_stack_writes_expanded_streams(tmp_path, monkeypatch):
    import yaml as _yaml

    cli, study, gdir = _cli_study(tmp_path, monkeypatch, _stack_doc())
    assert cli.cmd_stack(study) == 0
    artifact = gdir / "yaml" / "streams_expanded.yml"
    assert artifact.exists()
    expanded = _yaml.safe_load(artifact.read_text())
    assert list(expanded) == ["base", "v_1", "v_2", "v_3"]
    assert expanded["v_2"]["base"]["onset"] == 2
    assert all("spread" not in (e or {}) for e in expanded.values())


def test_cmd_stack_without_spread_writes_no_artifact(tmp_path, monkeypatch):
    doc = _stack_doc()
    doc["streams"] = {"base": {}}
    cli, study, gdir = _cli_study(tmp_path, monkeypatch, doc)
    assert cli.cmd_stack(study) == 0
    assert not (gdir / "yaml" / "streams_expanded.yml").exists()


def test_cmd_sweep_writes_expanded_streams(tmp_path, monkeypatch):
    doc = _stack_doc()
    doc["sweep"] = {"mode": "discrete"}
    doc["base"]["duration"] = 5
    cli, study, gdir = _cli_study(tmp_path, monkeypatch, doc)
    assert cli.cmd_sweep(study) == 0
    assert (gdir / "yaml" / "streams_expanded.yml").exists()
