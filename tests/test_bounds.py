from granstudies import bounds


def test_bounds_from_engine_registry():
    # density: [0.01, 4000] dal registry dell'engine
    lo, hi = bounds.bounds_for("density")
    assert lo == 0.01 and hi == 4000.0


def test_bounds_nested_path():
    lo, hi = bounds.bounds_for("grain.duration")
    assert lo == 0.001 and hi == 10.0


def test_bounds_manual_pitch():
    assert bounds.bounds_for("pitch.semitones") == (-36.0, 36.0)


def test_bounds_unknown_path():
    assert bounds.bounds_for("non.esiste") is None


def test_clamp_within_and_outside():
    assert bounds.clamp("density", 50) == 50
    assert bounds.clamp("density", -5) == 0.01
    assert bounds.clamp("density", 99999) == 4000.0
    # path sconosciuto: no-op
    assert bounds.clamp("non.esiste", 12345) == 12345


def test_span():
    assert bounds.span("distribution") == 1.0
    assert bounds.span("pitch.semitones") == 72.0
    assert bounds.span("non.esiste") is None
