import bz2
import xml.etree.ElementTree as ET

from granstudies.envelope_sweep import envelope_breakpoints
from granstudies.sv_export import _plateau_starts, _build_sv_xml


def _parse(compressed: bytes) -> ET.Element:
    xml = bz2.decompress(compressed).decode("utf-8")
    return ET.fromstring(xml)


# --- _plateau_starts -----------------------------------------------------------

def test_plateau_starts_one_envelope():
    points = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    # [[0,5],[.2,5],[.4,50],[.6,50],[.8,400],[1,400]] -> inizi: 0.0, 0.4, 0.8
    assert _plateau_starts([("density", points, "linear")]) == [0.0, 0.4, 0.8]


def test_plateau_starts_dedup_synchronized_envelopes():
    # Due assi mossi insieme: stessa griglia temporale -> stessi t_start, dedup.
    a = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    b = envelope_breakpoints([0.01, 0.05, 0.2], plateau=5, transition=5)
    starts = _plateau_starts([("density", a, "linear"), ("grain.duration", b, "linear")])
    assert starts == [0.0, 0.4, 0.8]


def test_plateau_starts_repeated_value_not_merged():
    # Valori consecutivi uguali (asse esterno fermo): vanno comunque contati
    # come plateau distinti -> 4 inizi, non 3.
    points = envelope_breakpoints([5, 5, 50, 400], plateau=5, transition=5)
    assert len(_plateau_starts([("density", points, "linear")])) == 4


def test_plateau_starts_single_value():
    points = envelope_breakpoints([42], plateau=5, transition=5)  # [[0,42],[1,42]]
    assert _plateau_starts([("density", points, "linear")]) == [0.0]


# --- marker layer nel .sv ------------------------------------------------------

def _envelopes():
    pts = envelope_breakpoints([5, 50, 400], plateau=5, transition=5)
    return [("density", pts, "linear")]


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
