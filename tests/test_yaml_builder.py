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
