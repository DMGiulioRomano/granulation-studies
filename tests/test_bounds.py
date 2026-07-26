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


def test_bounds_grain_duration_dynamic_output_sr():
    # con output_sr il minimo e' 1 campione (1/output_sr), non 1ms (issue #17)
    lo, hi = bounds.bounds_for("grain.duration", output_sr=48000)
    assert lo == 1.0 / 48000
    assert hi == 10.0


def test_bounds_output_sr_ignored_for_other_paths():
    # output_sr non tocca i parametri senza bound dinamico
    assert bounds.bounds_for("density", output_sr=48000) == (0.01, 4000.0)
    assert bounds.bounds_for("pitch.semitones", output_sr=48000) == (-36.0, 36.0)


def test_span():
    assert bounds.span("distribution") == 1.0
    assert bounds.span("pitch.semitones") == 72.0
    assert bounds.span("non.esiste") is None


def test_volume_ceiling_patched():
    # il tetto engine (+12 dB) e' alzato a runtime da engine_bridge
    from granstudies.engine_bridge import VOLUME_MAX_DB
    from pge.parameters.parameter_definitions import get_parameter_definition

    assert bounds.bounds_for("volume") == (-120.0, VOLUME_MAX_DB)
    # il patch vale anche per il parser dell'engine, non solo per bounds.py
    assert get_parameter_definition("volume").max_val == VOLUME_MAX_DB
    assert bounds.clamp("volume", 999) == VOLUME_MAX_DB
