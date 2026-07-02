import os

import yaml

from granstudies.study_spec import parse_study_spec
from granstudies import render as render_mod
from granstudies.render import render_variants, write_variants


def _spec(mode):
    return parse_study_spec(
        {
            "study_id": "s",
            "base": {
                "sample": "x.wav",
                "duration": 6,
                "time_mode": "normalized",
                "grain": {"envelope": "hanning"},
            },
            "axes": {
                "plateau": 5,
                "transition": 5,
                "density": {"path": "density", "baseline": 20, "values": [5, 50, 400]},
                "grain_duration": {
                    "path": "grain.duration",
                    "baseline": 0.05,
                    "values": [0.01, 0.05, 0.2],
                },
            },
            "sweep": {"mode": mode, "orders": [1, 2]},
        }
    )


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _find(written, suffix):
    return next(p for p in written if p.endswith(suffix))


def test_write_discrete_goes_into_discrete_subdir(tmp_path):
    written = write_variants(_spec("discrete"), str(tmp_path))
    assert written
    assert all((os.sep + "discrete" + os.sep) in p for p in written)
    assert not os.path.isdir(tmp_path / "envelope")


def test_discrete_file_uses_base_duration(tmp_path):
    written = write_variants(_spec("discrete"), str(tmp_path))
    doc = _load(written[0])
    # base.duration finisce nello stream (file discrete statici)
    assert doc["streams"][0]["duration"] == 6


def test_write_envelope_goes_into_envelope_subdir(tmp_path):
    written = write_variants(_spec("envelope"), str(tmp_path))
    assert written
    assert all((os.sep + "envelope" + os.sep) in p for p in written)
    assert not os.path.isdir(tmp_path / "discrete")


def test_envelope_file_structure(tmp_path):
    written = write_variants(_spec("envelope"), str(tmp_path))
    doc = _load(_find(written, "e1__density.yml"))
    stream = doc["streams"][0]
    assert stream["time_mode"] == "normalized"
    # density e' l'asse mosso -> envelope wrappato
    assert stream["density"]["type"] == "linear"
    assert stream["density"]["time_mode"] == "normalized"
    assert isinstance(stream["density"]["points"], list)
    # grain.duration fermo al baseline (scalare)
    assert stream["grain"]["duration"] == 0.05
    # la base.duration statica e' sostituita dalla durata calcolata, sia a
    # livello stream (richiesta dall'engine, scala i tempi normalizzati) sia doc
    # N=3 -> 3*5 + 2*5 = 25
    assert stream["duration"] == 25
    assert doc["duration"] == 25


def test_envelope_o2_has_two_synchronized_envelopes(tmp_path):
    written = write_variants(_spec("envelope"), str(tmp_path))
    doc = _load(_find(written, "e2__density__grain_duration.yml"))
    stream = doc["streams"][0]
    assert stream["density"]["type"] == "linear"
    assert stream["grain"]["duration"]["type"] == "linear"
    # stessa griglia temporale (sincronizzati)
    assert (
        [t for t, _ in stream["density"]["points"]]
        == [t for t, _ in stream["grain"]["duration"]["points"]]
    )
    # N=9 -> 9*5 + 8*5 = 85
    assert doc["duration"] == 85


def test_both_mode_writes_both_sets(tmp_path):
    written = write_variants(_spec("both"), str(tmp_path))
    assert os.path.isdir(tmp_path / "discrete")
    assert os.path.isdir(tmp_path / "envelope")
    assert any((os.sep + "discrete" + os.sep) in p for p in written)
    assert any((os.sep + "envelope" + os.sep) in p for p in written)


# --- render incrementale ---------------------------------------------------

def test_dump_preserves_mtime_when_unchanged(tmp_path):
    written = write_variants(_spec("envelope"), str(tmp_path))
    past = 1_000_000_000
    for p in written:
        os.utime(p, (past, past))
    rewritten = write_variants(_spec("envelope"), str(tmp_path))
    assert sorted(rewritten) == sorted(written)
    assert all(os.path.getmtime(p) == past for p in written)


def _fake_engine_render(calls):
    def fake(yaml_path, output_path, samples_dir, output_sr=48000):
        calls.append(yaml_path)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as fh:
            fh.write("x")
        return [output_path]

    return fake


def test_render_variants_skips_up_to_date(tmp_path, monkeypatch):
    variant_dir = str(tmp_path / "variants")
    n = len(write_variants(_spec("envelope"), variant_dir))
    calls = []
    monkeypatch.setattr(render_mod.engine_bridge, "render", _fake_engine_render(calls))
    kwargs = dict(
        variant_dir=variant_dir,
        audio_dir=str(tmp_path / "audio"),
        score_dir=None,
        samples_dir="unused",
        jobs=1,
    )
    first = render_variants(**kwargs)
    assert len(calls) == n
    assert not any(e["skipped"] for e in first)
    # secondo giro: tutto aggiornato, nessun render
    second = render_variants(**kwargs)
    assert len(calls) == n
    assert all(e["skipped"] for e in second)
    # force: rirenderizza tutto
    third = render_variants(**kwargs, force=True)
    assert len(calls) == 2 * n
    assert not any(e["skipped"] for e in third)


def test_render_variants_rerenders_only_changed(tmp_path, monkeypatch):
    variant_dir = str(tmp_path / "variants")
    written = write_variants(_spec("envelope"), variant_dir)
    calls = []
    monkeypatch.setattr(render_mod.engine_bridge, "render", _fake_engine_render(calls))
    kwargs = dict(
        variant_dir=variant_dir,
        audio_dir=str(tmp_path / "audio"),
        score_dir=None,
        samples_dir="unused",
        jobs=1,
    )
    render_variants(**kwargs)
    calls.clear()
    # tocco un solo YAML -> si rirenderizza solo quello
    changed = written[0]
    now = os.path.getmtime(changed) + 10
    os.utime(changed, (now, now))
    manifest = render_variants(**kwargs)
    assert calls == [changed]
    assert sum(1 for e in manifest if not e["skipped"]) == 1


# --- confronto golden: documento YAML completo letto da disco -------------------

def _golden_spec(orders):
    # spec minimale e deterministica per confronti byte-equivalenti
    return parse_study_spec(
        {
            "study_id": "golden",
            "seed": 1988,
            "base": {
                "sample": "corpus.wav",
                "onset": 0,
                "duration": 6,
                "time_mode": "normalized",
            },
            "axes": {
                "plateau": 5,
                "transition": 5,
                "density": {"path": "density", "baseline": 20, "values": [5, 50, 400]},
                "grain_duration": {
                    "path": "grain.duration",
                    "baseline": 0.05,
                    "values": [0.01, 0.05, 0.2],
                },
            },
            "sweep": {"mode": "envelope", "orders": orders},
        }
    )


def test_golden_e1_density_full_document(tmp_path):
    # Confronta l'INTERO documento scritto (round-trip su disco) con l'atteso.
    # I breakpoint replicano l'esempio della issue: densita'=[5,50,400], 25s.
    written = write_variants(_golden_spec([1]), str(tmp_path))
    doc = _load(_find(written, "e1__density.yml"))
    assert doc == {
        "title": "golden :: e1__density",
        "seed": 1988,
        "duration": 25.0,
        "streams": [
            {
                "sample": "corpus.wav",
                "onset": 0,
                "time_mode": "normalized",
                "stream_id": "stream",
                "duration": 25.0,
                "density": {
                    "type": "linear",
                    "points": [
                        [0.0, 5],
                        [0.2, 5],
                        [0.4, 50],
                        [0.6, 50],
                        [0.8, 400],
                        [1.0, 400],
                    ],
                    "time_mode": "normalized",
                },
                "grain": {"duration": 0.05},
            }
        ],
    }


def test_golden_e2_synchronized_points_exact(tmp_path):
    # I due assi mossi devono avere ESATTAMENTE gli stessi tempi e i valori
    # del prodotto cartesiano lessicografico, su 9 plateau (85s).
    written = write_variants(_golden_spec([2]), str(tmp_path))
    doc = _load(_find(written, "e2__density__grain_duration.yml"))
    stream = doc["streams"][0]
    assert doc["duration"] == 85.0
    assert stream["duration"] == 85.0

    # tempi attesi: 9 plateau, W_plateau = W_transition = 5/85
    w = 5 / 85
    expected_times = []
    for i in range(9):
        t_start = i * (w + w)
        expected_times.append(round(t_start, 6))
        expected_times.append(round(t_start + w, 6))
    expected_times[0] = 0.0
    expected_times[-1] = 1.0

    dens_times = [t for t, _ in stream["density"]["points"]]
    grain_times = [t for t, _ in stream["grain"]["duration"]["points"]]
    assert dens_times == expected_times
    assert grain_times == expected_times

    # valori per plateau (uno ogni 2 breakpoint) = prodotto lessicografico
    dens_vals = [v for _, v in stream["density"]["points"]][0::2]
    grain_vals = [v for _, v in stream["grain"]["duration"]["points"]][0::2]
    assert dens_vals == [5, 5, 5, 50, 50, 50, 400, 400, 400]
    assert grain_vals == [0.01, 0.05, 0.2, 0.01, 0.05, 0.2, 0.01, 0.05, 0.2]
