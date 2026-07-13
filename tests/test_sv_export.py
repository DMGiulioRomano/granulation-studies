import bz2
import xml.etree.ElementTree as ET

from granstudies.envelope_sweep import envelope_breakpoints
from granstudies.sv_export import _plateau_starts, _build_sv_xml, _find_envelopes


def _parse(compressed: bytes) -> ET.Element:
    xml = bz2.decompress(compressed).decode("utf-8")
    return ET.fromstring(xml)


# --- _find_envelopes -----------------------------------------------------------

def test_find_envelopes_recognizes_step():
    doc = {"grain": {"duration": {"type": "step",
                                  "points": [[0.0, 5], [0.5, 50]],
                                  "time_mode": "normalized"}}}
    assert _find_envelopes(doc) == [("grain.duration", [[0.0, 5], [0.5, 50]], "step")]


# --- _plateau_starts -----------------------------------------------------------

def test_plateau_starts_one_envelope():
    points = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    # [[0,5],[.2,5],[.4,50],[.6,50],[.8,400],[1,400]] -> inizi: 0.0, 0.4, 0.8
    assert _plateau_starts([("density", points, "linear", 0.0, 1.0)]) == [0.0, 0.4, 0.8]


def test_plateau_starts_dedup_synchronized_envelopes():
    # Due assi mossi insieme: stessa griglia temporale -> stessi t_start, dedup.
    a = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    b = envelope_breakpoints([0.01, 0.05, 0.2], plateau=5, transition=5)
    starts = _plateau_starts([("density", a, "linear", 0.0, 1.0), ("grain.duration", b, "linear", 0.0, 1.0)])
    assert starts == [0.0, 0.4, 0.8]


def test_plateau_starts_repeated_value_not_merged():
    # Valori consecutivi uguali (asse esterno fermo): vanno comunque contati
    # come plateau distinti -> 4 inizi, non 3.
    points = envelope_breakpoints([5, 5, 50, 400], plateau=5, transition=5)
    assert len(_plateau_starts([("density", points, "linear", 0.0, 1.0)])) == 4


def test_plateau_starts_single_value():
    points = envelope_breakpoints([42], plateau=5, transition=5)  # [[0,42],[1,42]]
    assert _plateau_starts([("density", points, "linear", 0.0, 1.0)]) == [0.0]


def test_plateau_starts_step_one_marker_per_value():
    # Geometria step: un solo punto per valore -> ogni punto e' un inizio-gradino.
    pts = envelope_breakpoints([5, 50, 400], plateau=5, transition=5, step=True)
    assert _plateau_starts([("density", pts, "step", 0.0, 1.0)]) == [0.0, 0.333333, 0.666667]


# --- plotStyle per tipo --------------------------------------------------------

def test_step_layer_uses_stepped_plot_style():
    # SV (fork): enum PlotStyle -> Stepped = 8. Il layer timevalues dell'envelope
    # step dev'essere disegnato a scalini, non a segmenti obliqui.
    pts = envelope_breakpoints([5, 50, 400], plateau=5, transition=5, step=True)
    xml = _parse(_build_sv_xml("/x.wav", 1000, 15.0, [("density", pts, "step", 0.0, 15.0)], "multi"))
    tv = [l for l in xml.findall("./data/layer") if l.get("type") == "timevalues"]
    assert len(tv) == 1
    assert tv[0].get("plotStyle") == "8"


def test_per_breakpoint_envelope_uses_per_breakpoint_plot_style():
    # SV (fork): enum PlotStyle -> PerBreakpoint = 9. Envelope con almeno un
    # punto [t, v, type] (sintassi per-punto del motore): il layer va disegnato
    # col nuovo stile misto, non con quello globale del type di envelope.
    pts = [[0.0, 5, "step"], [0.4, 50, "cubic"], [1.0, 400]]
    xml = _parse(_build_sv_xml("/x.wav", 1000, 10.0, [("density", pts, "linear", 0.0, 10.0)], "multi",
                               markers=False))
    tv = [l for l in xml.findall("./data/layer") if l.get("type") == "timevalues"]
    assert len(tv) == 1
    assert tv[0].get("plotStyle") == "9"


def test_per_breakpoint_points_emit_type_as_label():
    # Il type per-punto viaggia nella label del <point>: e' il canale che
    # TimeValueLayer::PlotPerBreakpoint legge per scegliere l'interpolazione
    # del segmento che parte dal punto. Punti senza type -> label vuota.
    pts = [[0.0, 5, "step"], [0.4, 50, "cubic"], [1.0, 400]]
    xml = _parse(_build_sv_xml("/x.wav", 1000, 10.0, [("density", pts, "linear", 0.0, 10.0)], "multi",
                               markers=False))
    ds = xml.findall("./data/dataset")
    assert len(ds) == 1
    points = ds[0].findall("point")
    assert [p.get("label") for p in points] == ["step", "cubic", ""]
    assert [p.get("value") for p in points] == ["5", "50", "400"]
    assert [p.get("frame") for p in points] == ["0", "4000", "10000"]


def test_uniform_envelope_keeps_global_plot_style():
    # Senza punti a 3 elementi il comportamento resta quello di prima:
    # plotStyle dal type dell'envelope, label vuote.
    pts = [[0.0, 5], [1.0, 400]]
    xml = _parse(_build_sv_xml("/x.wav", 1000, 10.0, [("density", pts, "cubic", 0.0, 10.0)], "multi",
                               markers=False))
    tv = [l for l in xml.findall("./data/layer") if l.get("type") == "timevalues"]
    assert tv[0].get("plotStyle") == "7"
    ds = xml.findall("./data/dataset")[0]
    assert [p.get("label") for p in ds.findall("point")] == ["", ""]


def test_stems_builder_handles_per_breakpoint_points():
    from granstudies.sv_export import _build_sv_xml_stems
    import os, tempfile

    pts = [[0.0, 5, "step"], [1.0, 50]]
    with tempfile.NamedTemporaryFile(suffix=".aif") as fh:
        stems = [("base", fh.name, 1000, 10.0, [("density", pts, "linear")])]
        xml = _parse(_build_sv_xml_stems(stems))

    tv = [l for l in xml.findall("./data/layer") if l.get("type") == "timevalues"]
    assert len(tv) == 1
    assert tv[0].get("plotStyle") == "9"
    ds = xml.findall("./data/dataset")[0]
    assert [p.get("label") for p in ds.findall("point")] == ["step", ""]


# --- marker layer nel .sv ------------------------------------------------------

def _envelopes(duration=25.0):
    pts = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    return [("density", pts, "linear", 0.0, duration)]


def test_markers_emitted_in_data_and_every_pane():
    sr, duration = 1000, 25.0  # 3*5 + 2*5; frame = t_norm * duration * sr
    xml = _parse(_build_sv_xml("/x.wav", sr, duration, _envelopes(), "multi",
                               markers_scope="all"))

    inst_models = [m for m in xml.findall("./data/model") if m.get("dimensions") == "1"]
    assert len(inst_models) == 1

    ds_id = inst_models[0].get("dataset")
    ds = next(d for d in xml.findall("./data/dataset") if d.get("id") == ds_id)
    pts = ds.findall("point")
    assert [p.get("frame") for p in pts] == ["0", "10000", "20000"]
    assert [p.get("label") for p in pts] == ["1", "2", "3"]  # plateau 1-based

    # Il modello marker dev'essere mutato, altrimenti SV suona un click a
    # ogni instant durante il playback.
    pp = [p for p in xml.findall("./data/playparameters")
          if p.get("model") == inst_models[0].get("id")]
    assert len(pp) == 1 and pp[0].get("mute") == "true"

    data_layer = [l for l in xml.findall("./data/layer") if l.get("type") == "timeinstants"]
    assert len(data_layer) == 1
    marker_id = data_layer[0].get("id")

    # scope=all: marker in ogni pane (waveform + un pane envelope = 2 pane).
    panes = xml.findall("./display/view")
    assert len(panes) == 2
    for pane in panes:
        ids = [l.get("id") for l in pane.findall("layer") if l.get("type") == "timeinstants"]
        assert ids == [marker_id]


def test_markers_scope_waveform():
    # Default: marker solo nel pane waveform (primo), non nei pane envelope.
    xml = _parse(_build_sv_xml("/x.wav", 1000, 25.0, _envelopes(), "multi"))
    data_layer = [l for l in xml.findall("./data/layer") if l.get("type") == "timeinstants"]
    assert len(data_layer) == 1
    marker_id = data_layer[0].get("id")

    panes = xml.findall("./display/view")
    assert len(panes) == 2
    waveform_ids = [l.get("id") for l in panes[0].findall("layer") if l.get("type") == "timeinstants"]
    envelope_ids = [l.get("id") for l in panes[1].findall("layer") if l.get("type") == "timeinstants"]
    assert waveform_ids == [marker_id]
    assert envelope_ids == []


def test_spectrogram_in_waveform_pane():
    xml = _parse(_build_sv_xml("/x.wav", 1000, 25.0, _envelopes(), "multi"))
    # Layer spectrogram definito in data
    spec_layers = [l for l in xml.findall("./data/layer") if l.get("type") == "spectrogram"]
    assert len(spec_layers) == 1
    sl = spec_layers[0]
    assert sl.get("windowSize") == "8192"
    assert sl.get("windowHopLevel") == "3"
    assert sl.get("colourScheme") == "2"
    assert sl.get("frequencyScale") == "0"
    assert sl.get("channel") == "-1"

    # Presente nel pane waveform (primo pane)
    waveform_pane = xml.findall("./display/view")[0]
    pane_spec = [l for l in waveform_pane.findall("layer") if l.get("type") == "spectrogram"]
    assert len(pane_spec) == 1


def test_markers_disabled():
    xml = _parse(_build_sv_xml("/x.wav", 1000, 25.0, _envelopes(), "multi", markers=False))
    assert [l for l in xml.findall("./data/layer") if l.get("type") == "timeinstants"] == []
    for pane in xml.findall("./display/view"):
        assert pane.findall("layer[@type='timeinstants']") == []


# --- stack: envelope multi-stream ---------------------------------------------

def test_stack_envelopes_prefixes_stream_id_and_skips_scalars():
    from granstudies.sv_export import _stack_envelopes
    doc = {"streams": [
        {"stream_id": "base",
         "density": {"type": "step", "points": [[0.0, 5], [1.0, 50]]},
         "grain": {"duration": 0.004}},          # scalare -> nessun envelope
        {"stream_id": "voce_b",
         "density": {"type": "cubic", "points": [[0.0, 10], [1.0, 20]]}},
        {"stream_id": "drone",
         "density": 8, "grain": {"duration": 0.05}},  # tutto scalare -> niente
    ]}
    envs = _stack_envelopes(doc)
    paths = [p for p, _pts, _t, _onset, _dur in envs]
    assert paths == ["base/density", "voce_b/density"]


def test_multi_groups_envelopes_by_stream_prefix():
    # Path con prefisso stream/ (export stack): gli assi di uno stream finiscono
    # nello stesso pane; stream diversi in pane diversi.
    envs = [
        ("a/density", [[0.0, 5], [1.0, 50]], "step", 0.0, 10.0),
        ("a/grain.duration", [[0.0, 0.001], [1.0, 0.01]], "linear", 0.0, 10.0),
        ("b/density", [[0.0, 10], [1.0, 20]], "cubic", 0.0, 10.0),
    ]
    xml = _parse(_build_sv_xml("/x.wav", 1000, 10.0, envs, "multi", markers=False))
    panes = xml.findall("./display/view")
    env_panes = panes[1:]  # il primo e' waveform
    names = [[l.get("name") for l in p.findall("layer[@type='timevalues']")] for p in env_panes]
    assert names == [["a/density", "a/grain.duration"], ["b/density"]]


def test_stack_envelopes_carry_stream_onset_and_duration():
    # study_versions_test: 3 versioni concatenate, ognuna con la propria
    # durata (20s) e onset (0/20/40) diversi dalla durata totale dello
    # stack (60s). I punti normalizzati [0,1] di ogni stream vanno riportati
    # sull'asse assoluto come onset + t_norm*duration_stream, non contro la
    # durata totale del documento (bug: prima schiacciava/spostava tutto).
    from granstudies.sv_export import _stack_envelopes
    doc = {
        "duration": 60,
        "streams": [
            {"stream_id": "fermo__d=1", "onset": 0, "duration": 20,
             "density": {"type": "linear", "points": [[0.0, 1], [1.0, 2]]}},
            {"stream_id": "fermo__d=2", "onset": 20, "duration": 20,
             "density": {"type": "linear", "points": [[0.0, 1], [1.0, 2]]}},
        ],
    }
    envs = _stack_envelopes(doc)
    assert [(onset, dur) for _p, _pts, _t, onset, dur in envs] == [(0.0, 20.0), (20.0, 20.0)]

    xml = _parse(_build_sv_xml("/x.wav", 1000, 60.0, envs, "multi", markers=False))
    datasets = xml.findall("./data/dataset")
    frames_first = [p.get("frame") for p in datasets[0].findall("point")]
    frames_second = [p.get("frame") for p in datasets[1].findall("point")]
    # t_norm=1.0: primo stream -> (0 + 1*20)*1000 = 20000; secondo -> (20 + 1*20)*1000 = 40000
    assert frames_first == ["0", "20000"]
    assert frames_second == ["20000", "40000"]


def test_multi_without_prefix_is_one_pane_per_envelope():
    # Path sweep (senza '/'): comportamento invariato, un pane per envelope.
    envs = [("density", [[0.0, 5]], "step", 0.0, 10.0), ("grain.duration", [[0.0, 0.001]], "linear", 0.0, 10.0)]
    xml = _parse(_build_sv_xml("/x.wav", 1000, 10.0, envs, "multi", markers=False))
    env_panes = xml.findall("./display/view")[1:]
    assert len(env_panes) == 2
