import pytest

from granstudies import bounds


def test_bounds_from_engine_registry():
    # density: [0.01, 4000] dal registry dell'engine
    lo, hi = bounds.bounds_for("density")
    assert lo == 0.01 and hi == 4000.0


def test_bounds_nested_path():
    # Senza output_sr esplicito vale comunque il floor dinamico dell'engine
    # (1 campione), non il fallback statico di 1 ms.
    lo, hi = bounds.bounds_for("grain.duration")
    assert lo == 1 / bounds.default_output_sr()
    assert hi == 10.0


def test_bounds_pitch_dall_engine():
    assert bounds.bounds_for("pitch.semitones") == (-36.0, 36.0)
    assert bounds.bounds_for("pitch.cents") == (-3600.0, 3600.0)
    # pitch.ratio prima non era mappato: nessun bound, nessuna validazione.
    assert bounds.bounds_for("pitch.ratio") == (0.001, 8.0)
    assert bounds.bounds_for("pitch.inesistente") is None


def test_bounds_path_dagli_schema_engine():
    # Path che la vecchia tabella a mano non copriva.
    assert bounds.bounds_for("pointer.loop_dur") == (0.005, None)
    assert "grain.reverse" in bounds.known_paths()


def test_bounds_unknown_path():
    assert bounds.bounds_for("non.esiste") is None


def test_clamp_within_and_outside():
    assert bounds.clamp("density", 50) == 50
    assert bounds.clamp("density", -5) == 0.01
    assert bounds.clamp("density", 99999) == 4000.0
    # path sconosciuto: no-op
    assert bounds.clamp("non.esiste", 12345) == 12345


def test_bounds_grain_duration_dynamic_output_sr():
    # con output_sr il minimo e' il floor dinamico dell'engine: 1 campione
    lo, hi = bounds.bounds_for("grain.duration", output_sr=48000)
    assert lo == 1 / 48000
    assert hi == 10.0


def test_bounds_output_sr_ignored_for_other_paths():
    # output_sr non tocca i parametri senza bound dinamico
    assert bounds.bounds_for("density", output_sr=48000) == (0.01, 4000.0)
    assert bounds.bounds_for("pitch.semitones", output_sr=48000) == (-36.0, 36.0)


def test_grain_duration_factor_per_unita():
    assert bounds.grain_duration_factor(None) == 1.0
    assert bounds.grain_duration_factor("seconds") == 1.0
    assert bounds.grain_duration_factor("milliseconds") == 0.001
    assert bounds.grain_duration_factor("samples", 48000) == 1 / 48000


def test_grain_duration_factor_samples_pretende_output_sr():
    # 'samples' e' l'unica unita' che dipende dal sample rate
    with pytest.raises(ValueError, match="output_sr"):
        bounds.grain_duration_factor("samples")
    assert bounds.grain_duration_factor("milliseconds") == 0.001


def test_grain_duration_factor_unita_sconosciuta():
    with pytest.raises(ValueError, match="sconosciuta"):
        bounds.grain_duration_factor("frames")


def test_clamp_grain_duration_in_millisecondi():
    # bounds in secondi [1/48000, 10] -> in ms
    lo_ms = 1 / 48000 * 1000
    assert bounds.clamp(
        "grain.duration", 50, output_sr=48000, unit="milliseconds"
    ) == 50
    assert bounds.clamp(
        "grain.duration", 0.0001, output_sr=48000, unit="milliseconds"
    ) == pytest.approx(lo_ms)
    assert bounds.clamp(
        "grain.duration", 99999, output_sr=48000, unit="milliseconds"
    ) == pytest.approx(10_000.0)


def test_clamp_grain_duration_in_campioni():
    assert bounds.clamp(
        "grain.duration", 50, output_sr=48000, unit="samples"
    ) == 50
    assert bounds.clamp(
        "grain.duration", 1, output_sr=48000, unit="samples"
    ) == pytest.approx(1)


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


def test_bounds_pitch_coincidono_con_value_bounds_per_ogni_unita():
    # Parita' sull'intero vocabolario dell'engine, non solo sulle tre unita'
    # che il test sopra nomina: un preset nuovo entra da solo.
    from granstudies.engine_bridge import pitch_bounds, pitch_units

    assert {"semitones", "cents", "ratio"} <= pitch_units()
    for u in pitch_units():
        vb = pitch_bounds(u)
        assert bounds.bounds_for(f"pitch.{u}") == (vb.min_val, vb.max_val), u
        assert f"pitch.{u}" in bounds.known_paths()


def test_path_della_vecchia_tabella_restano_noti():
    # Derivare la mappa dagli schema non deve far perdere la validazione a
    # nessun path che la tabella a mano copriva.
    vecchi = {
        "density", "distribution", "fill_factor", "grain.duration", "pan",
        "volume", "pointer.speed_ratio", "pointer.deviation", "scatter",
        "num_voices", "pitch.semitones", "pitch.cents",
    }
    assert vecchi <= bounds.known_paths()
    assert all(bounds.bounds_for(p) is not None for p in vecchi)


def test_bounds_read_direction_dagli_schema_engine():
    # Issue #68: la tabella a mano non conosceva grain.read_direction.
    assert bounds.bounds_for("grain.read_direction") == (-1, 1)


def test_violation_none_dentro_i_bounds_o_su_path_sconosciuto():
    assert bounds.violation("density", 50) is None
    assert bounds.violation("pitch.ratio", 1.0) is None
    assert bounds.violation("non.esiste", 1e9) is None


def test_violation_confronta_nell_unita_e_ritorna_secondi():
    b = bounds.bounds_for("grain.duration")
    assert bounds.violation("grain.duration", 20.0) == b
    assert bounds.violation("grain.duration", 50, unit="milliseconds") is None
    assert bounds.violation("grain.duration", 20_000, unit="milliseconds") == b
    assert bounds.violation("grain.duration", 1, unit="samples") is None
    assert bounds.violation("grain.duration", 0.5, unit="samples") == b
    # l'unita' vale solo per grain.duration: altrove e' ignorata
    assert bounds.violation("density", 50, unit="milliseconds") is None


@pytest.mark.parametrize(
    "path, value, unit",
    [
        ("density", 50, None),
        ("density", -5, None),
        ("grain.duration", 1e-6, None),
        ("grain.duration", 0.01, None),
        ("grain.duration", 0.5, "samples"),
        ("grain.duration", 20_000, "milliseconds"),
        ("pitch.ratio", 20, None),
        ("pitch.ratio", 0.5, None),
        ("pointer.loop_dur", 0.001, None),
        ("pointer.loop_dur", 0.001, "normalized"),
    ],
)
def test_violation_e_clamp_concordano(path, value, unit):
    # Un solo punto di confronto: clamp sposta un valore se e solo se
    # violation lo dichiara fuori.
    fuori = bounds.violation(path, value, unit=unit) is not None
    assert fuori == (bounds.clamp(path, value, unit=unit) != value)


def test_loop_normalized_non_si_confronta_coi_bounds_in_secondi():
    # loop_dur ha un minimo di 0.005 s, ma sotto 'loop_unit: normalized' il
    # valore e' una frazione della durata del sample, che qui non si conosce:
    # 0.003 di un file di 10 s sono 0.03 s, ammessi dall'engine.
    assert bounds.violation("pointer.loop_dur", 0.003, unit="normalized") is None
    assert bounds.clamp("pointer.loop_dur", 0.003, unit="normalized") == 0.003
    # in secondi (esplicito, alias storico o assente = default) il minimo vale
    for u in (None, "seconds", "absolute"):
        assert bounds.violation("pointer.loop_dur", 0.003, unit=u) == (0.005, None)
        assert bounds.clamp("pointer.loop_dur", 0.003, unit=u) == 0.005


def test_declared_unit_legge_la_chiave_giusta_per_path():
    doc = {
        "grain": {"duration_unit": "milliseconds"},
        "pointer": {"loop_unit": "normalized"},
    }
    assert bounds.declared_unit("grain.duration", doc) == "milliseconds"
    for k in ("start", "loop_start", "loop_end", "loop_dur"):
        assert bounds.declared_unit(f"pointer.{k}", doc) == "normalized"
    assert bounds.declared_unit("density", doc) is None
    assert bounds.declared_unit("pointer.speed_ratio", doc) is None
    assert bounds.declared_unit("grain.duration", {}) is None


def test_categorical_domain_e_il_catalogo_finestre_dell_engine():
    # Nessuna tabella copiata: il dominio di grain.envelope e' il catalogo
    # dell'engine, alias compresi.
    dom = bounds.categorical_domain("grain.envelope")
    from pge.controllers.window_registry import WindowRegistry

    assert dom == frozenset(WindowRegistry.all_names())
    assert {"hanning", "expodec", "triangle"} <= dom
    assert bounds.categorical_domain("density") is None
    assert bounds.categorical_domain("non.esiste") is None


def test_path_categoriale_fuori_dal_confronto_bounds():
    # Il registry da' a grain.envelope bounds (0, 0) che non descrivono un
    # nome: violation e clamp (l'unico confronto) non li applicano.
    assert bounds.violation("grain.envelope", "expodec") is None
    assert bounds.clamp("grain.envelope", "expodec") == "expodec"
