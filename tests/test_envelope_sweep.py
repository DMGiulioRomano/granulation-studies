from granstudies.study_spec import parse_study_spec
from granstudies.envelope_sweep import (
    envelope_breakpoints,
    cartesian_combinations,
    EnvelopeVariant,
    generate_envelope_variants,
)


def _spec(orders, plateau=5, transition=5):
    return parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {
                "plateau": plateau,
                "transition": transition,
                "density": {"path": "density", "baseline": 20, "values": [5, 50, 400]},
                "grain_duration": {
                    "path": "grain.duration",
                    "baseline": 0.05,
                    "values": [0.01, 0.05, 0.2],
                },
                "pan": {"path": "pan", "baseline": 0.0, "values": [-1.0, 0.0, 1.0]},
            },
            "sweep": {"mode": "envelope", "orders": orders},
        }
    )


# --- envelope_breakpoints ------------------------------------------------------

def test_breakpoints_o1_three_values():
    bp = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    assert bp == [
        [0.0, 5],
        [0.2, 5],
        [0.4, 50],
        [0.6, 50],
        [0.8, 400],
        [1.0, 400],
    ]


def test_breakpoints_single_value():
    bp = envelope_breakpoints([42], plateau=5, transition=5)
    assert bp == [[0.0, 42], [1.0, 42]]


def test_breakpoints_times_monotonic_and_normalized():
    bp = envelope_breakpoints([1, 2, 3, 4], plateau=3, transition=7)
    times = [t for t, _ in bp]
    assert times == sorted(times)
    assert times[0] == 0.0
    assert times[-1] == 1.0


# --- cartesian_combinations ----------------------------------------------------

def test_cartesian_two_axes_lexicographic():
    spec = _spec([2])
    combos = cartesian_combinations([spec.axis("density"), spec.axis("grain_duration")])
    assert len(combos) == 9
    # ordine lessicografico: il primo asse e' fisso per un blocco di N valori
    assert combos[0] == {"density": 5, "grain_duration": 0.01}
    assert combos[1] == {"density": 5, "grain_duration": 0.05}
    assert combos[2] == {"density": 5, "grain_duration": 0.2}
    assert combos[3] == {"density": 50, "grain_duration": 0.01}
    assert combos[8] == {"density": 400, "grain_duration": 0.2}


# --- generate_envelope_variants ------------------------------------------------

def test_naming_o1():
    variants = generate_envelope_variants(_spec([1]))
    names = {v.name for v in variants}
    assert "e1__density" in names
    assert "e1__grain_duration" in names
    assert "e1__pan" in names


def test_naming_o2():
    variants = generate_envelope_variants(_spec([2]))
    names = {v.name for v in variants}
    assert "e2__density__grain_duration" in names


def test_file_counts_per_order():
    # 3 assi: o1 -> C(3,1)=3 file, o2 -> C(3,2)=3, o3 -> C(3,3)=1
    assert len(generate_envelope_variants(_spec([1]))) == 3
    assert len(generate_envelope_variants(_spec([2]))) == 3
    assert len(generate_envelope_variants(_spec([3]))) == 1


def test_combinations_count_o1():
    v = generate_envelope_variants(_spec([1]))[0]
    assert len(v.combinations) == 3       # N valori dell'asse


def test_duration_o1():
    v = generate_envelope_variants(_spec([1]))[0]
    # N=3, plateau=transition=5 -> 3*5 + 2*5 = 25
    assert v.duration(_spec([1])) == 25


def test_duration_o2():
    spec = _spec([2])
    v = next(x for x in generate_envelope_variants(spec) if x.order == 2)
    # N=9 -> 9*5 + 8*5 = 85
    assert v.duration(spec) == 85


def test_duration_o3_full():
    spec = _spec([3])
    v = generate_envelope_variants(spec)[0]
    # N=27 -> 27*5 + 26*5 = 265
    assert v.duration(spec) == 265


def test_duration_o4_with_four_axes():
    spec = parse_study_spec(
        {
            "study_id": "s",
            "base": {"sample": "x.wav"},
            "axes": {
                "plateau": 5,
                "transition": 5,
                "a": {"path": "density", "baseline": 20, "values": [5, 50, 400]},
                "b": {"path": "grain.duration", "baseline": 0.05, "values": [0.01, 0.05, 0.2]},
                "c": {"path": "pan", "baseline": 0.0, "values": [-1.0, 0.0, 1.0]},
                "d": {"path": "volume", "baseline": -6, "values": [-12, -6, 0]},
            },
            "sweep": {"mode": "envelope", "orders": [4]},
        }
    )
    variants = generate_envelope_variants(spec)
    assert len(variants) == 1
    v = variants[0]
    assert len(v.combinations) == 81
    # N=81 -> 81*5 + 80*5 = 805
    assert v.duration(spec) == 805


# --- EnvelopeVariant.overrides -------------------------------------------------

def test_overrides_o2_synchronized_and_fixed_axes():
    spec = _spec([2])
    v = next(x for x in generate_envelope_variants(spec) if x.name == "e2__density__grain_duration")
    ov = v.overrides(spec)

    # i due assi mossi -> breakpoint (liste), sincronizzati su 9 plateau
    assert isinstance(ov["density"], list)
    assert isinstance(ov["grain.duration"], list)
    assert len(ov["density"]) == 18          # 2 breakpoint per plateau, 9 plateau
    assert len(ov["grain.duration"]) == 18

    # la sequenza dei valori density (un valore per plateau) segue il prodotto
    density_seq = [ov["density"][i][1] for i in range(0, 18, 2)]
    assert density_seq == [5, 5, 5, 50, 50, 50, 400, 400, 400]
    grain_seq = [ov["grain.duration"][i][1] for i in range(0, 18, 2)]
    assert grain_seq == [0.01, 0.05, 0.2, 0.01, 0.05, 0.2, 0.01, 0.05, 0.2]

    # l'asse non mosso (pan) resta scalare al baseline
    assert ov["pan"] == 0.0


def test_overrides_o1_only_one_envelope():
    spec = _spec([1])
    v = next(x for x in generate_envelope_variants(spec) if x.name == "e1__density")
    ov = v.overrides(spec)
    assert isinstance(ov["density"], list)
    assert ov["grain.duration"] == 0.05      # fermo al baseline
    assert ov["pan"] == 0.0


# --- orderings espliciti -------------------------------------------------------

def _spec_orderings(orderings):
    return parse_study_spec({
        "study_id": "s",
        "base": {"sample": "x.wav"},
        "axes": {
            "plateau": 5, "transition": 5,
            "density": {"path": "density", "baseline": 20, "values": [5, 50, 400]},
            "grain_duration": {"path": "grain.duration", "baseline": 0.05, "values": [0.01, 0.05, 0.2]},
            "pan": {"path": "pan", "baseline": 0.0, "values": [-1.0, 0.0, 1.0]},
        },
        "sweep": {"mode": "envelope", "orders": [3], "orderings": orderings},
    })


def test_orderings_produce_correct_names():
    spec = _spec_orderings([
        ["density", "grain_duration", "pan"],
        ["grain_duration", "density", "pan"],
    ])
    variants = generate_envelope_variants(spec)
    names = [v.name for v in variants]
    assert "e3__density__grain_duration__pan" in names
    assert "e3__grain_duration__density__pan" in names


def test_orderings_outer_axis_is_slowest():
    # Con [grain_duration, density, pan]: grain_duration è outer -> la sua sequenza
    # nei plateau ripete ogni len(density)*len(pan) = 9 passi.
    spec = _spec_orderings([["grain_duration", "density", "pan"]])
    v = generate_envelope_variants(spec)[0]
    ov = v.overrides(spec)
    gd_seq = [ov["grain.duration"][i][1] for i in range(0, len(ov["grain.duration"]), 2)]
    # outer axis: blocchi da 9 con lo stesso valore
    assert gd_seq[:9] == [0.01] * 9
    assert gd_seq[9:18] == [0.05] * 9
    density_seq = [ov["density"][i][1] for i in range(0, len(ov["density"]), 2)]
    # middle axis: blocchi da 3 (pan è inner, cicla più veloce)
    assert density_seq[:3] == [5, 5, 5]
    assert density_seq[3:6] == [50, 50, 50]


def test_orderings_no_duplicate_with_combinations():
    # Se un ordering coincide con la combinazione lessicografica, non deve comparire due volte.
    spec = _spec_orderings([["density", "grain_duration", "pan"]])
    variants = generate_envelope_variants(spec)
    names = [v.name for v in variants]
    assert names.count("e3__density__grain_duration__pan") == 1
