from granstudies.yaml_builder import deep_set, deep_get, build_stream, build_document


def test_deep_set_creates_nested():
    d = {}
    deep_set(d, "grain.duration", 0.2)
    assert d == {"grain": {"duration": 0.2}}


def test_deep_set_overwrites_non_dict():
    d = {"grain": 5}
    deep_set(d, "grain.duration", 0.2)
    assert d == {"grain": {"duration": 0.2}}


def test_deep_set_top_level():
    d = {}
    deep_set(d, "density", 50)
    assert d == {"density": 50}


def test_deep_get():
    d = {"grain": {"duration": 0.2}}
    assert deep_get(d, "grain.duration") == 0.2
    assert deep_get(d, "grain.missing", "x") == "x"
    assert deep_get(d, "nope", None) is None


def test_build_stream_does_not_mutate_base():
    base = {"density": 20, "grain": {"duration": 0.05}}
    out = build_stream(base, {"grain.duration": 0.2})
    assert out["grain"]["duration"] == 0.2
    assert base["grain"]["duration"] == 0.05  # base intatto


def test_build_document_includes_optional_keys_only_when_given():
    base = {"density": 20}
    doc = build_document(base, {}, title="t", seed=1, duration=6)
    assert doc["title"] == "t" and doc["seed"] == 1 and doc["duration"] == 6
    assert doc["streams"][0]["density"] == 20

    minimal = build_document(base, {})
    assert "title" not in minimal and "seed" not in minimal
    assert minimal["streams"][0] == {"density": 20}


# --- envelope wrapping (gated) -------------------------------------------------

def test_build_stream_wraps_list_override_when_envelope_mode():
    out = build_stream(
        {"density": 20},
        {"density": [[0, 5], [1, 5]]},
        envelope_time_mode="normalized",
    )
    assert out["density"] == {
        "type": "linear",
        "points": [[0, 5], [1, 5]],
        "time_mode": "normalized",
    }


def test_build_stream_per_path_envelope_types():
    out = build_stream(
        {"density": 20, "grain": {"duration": 0.05}},
        {"density": [[0, 5], [1, 5]], "grain.duration": [[0, 0.01], [1, 0.2]]},
        envelope_time_mode="normalized",
        envelope_types={"density": "step", "grain.duration": "cubic"},
    )
    assert out["density"]["type"] == "step"
    assert out["grain"]["duration"]["type"] == "cubic"


def test_build_stream_envelope_types_fallback_to_scalar():
    # path non presente nella mappa -> ricade sul default envelope_type
    out = build_stream(
        {"density": 20},
        {"density": [[0, 5], [1, 5]]},
        envelope_time_mode="normalized",
        envelope_types={},
    )
    assert out["density"]["type"] == "linear"


def test_build_stream_list_override_raw_by_default():
    # backward compat (compose): senza envelope_time_mode la lista resta grezza
    out = build_stream({"density": 20}, {"density": [[0, 5], [1, 5]]})
    assert out["density"] == [[0, 5], [1, 5]]


def test_build_stream_scalar_override_never_wrapped():
    out = build_stream({"density": 20}, {"density": 50}, envelope_time_mode="normalized")
    assert out["density"] == 50


def test_build_document_wraps_list_override():
    doc = build_document(
        {"density": 20},
        {"density": [[0, 5], [0.5, 5], [1, 50]]},
        envelope_time_mode="normalized",
        duration=25,
    )
    stream = doc["streams"][0]
    assert stream["density"] == {
        "type": "linear",
        "points": [[0, 5], [0.5, 5], [1, 50]],
        "time_mode": "normalized",
    }
    assert doc["duration"] == 25
