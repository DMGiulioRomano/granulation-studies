"""Genera file di sessione Sonic Visualiser (.sv) dai YAML di variante envelope.

Il file .sv prodotto apre direttamente SV con l'audio e i pannelli envelope
già configurati. Layout disponibili:
  multi  — un pannello per ogni parametro (Y scale indipendenti, default)
  single — tutti gli envelope in un pannello unico sotto la waveform

Con ``markers=True`` (default) aggiunge un layer ``timeinstants`` con un marker
all'inizio di ogni plateau (confine di stato), replicato in ogni pane come linea
verticale di riferimento e navigabile in SV con PgUp/PgDown.

Formato: XML bzip2, struttura <data><model/><dataset/><layer/></data><display><view/></display>.
"""
from __future__ import annotations

import bz2
import os
import xml.etree.ElementTree as ET
from typing import Any, List, Literal, Tuple

# Plot style per tipo di interpolazione dell'envelope.
# I valori sono gli interi dell'enum PlotStyle di TimeValueLayer (svgui),
# serializzati come stringa nell'attributo plotStyle del layer.
#   "3" = PlotLines        -> spezzata di segmenti retti tra i breakpoint
#   "7" = PlotCubicHermite -> curva cubica monotona (Fritsch-Carlson)
_PLOT_STYLE_BY_TYPE = {
    "linear": "3",
    "cubic": "7",
}
_PLOT_STYLE_DEFAULT = "3"  # fallback prudente: segmenti retti

_COLOURS = [
    ("#ff8800", "Orange"),
    ("#00ccff", "Bright Blue"),
    ("#00ff00", "Green"),
    ("#ff00ff", "Magenta"),
    ("#ffff00", "Yellow"),
]

Layout = Literal["multi", "single"]


_ENVELOPE_TYPES = {"linear", "cubic"}


def _find_envelopes(obj: Any, prefix: str = "") -> List[Tuple[str, List, str]]:
    """Walk ricorsivo: [(path_dotted, points, type)] per ogni envelope (linear o cubic)."""
    if isinstance(obj, dict):
        if obj.get("type") in _ENVELOPE_TYPES and "points" in obj:
            return [(prefix.lstrip("."), obj["points"], obj["type"])]
        results = []
        for k, v in obj.items():
            results.extend(_find_envelopes(v, f"{prefix}.{k}"))
        return results
    return []


def _plateau_starts(envelopes: List[Tuple[str, List, str]]) -> List[float]:
    """Tempi normalizzati (ordinati, dedup) di inizio di ogni plateau.

    I breakpoint envelope arrivano in coppie ``[t_start, v], [t_end, v]`` per
    plateau (vedi ``envelope_sweep.envelope_breakpoints``): l'inizio di ogni
    plateau e' quindi il punto a indice pari, mentre gli indici dispari chiudono
    il plateau prima della transizione. Non ci si puo' basare sull'uguaglianza dei
    valori per riconoscerli, perche' plateau consecutivi possono condividere lo
    stesso valore su un asse (es. l'asse esterno del prodotto cartesiano resta
    fermo per piu' plateau). Gli envelope di una stessa variante condividono la
    griglia temporale, percio' i ``t_start`` coincidono: li uniamo e dedup.
    """
    starts = set()
    for _path, points, _type in envelopes:
        for i in range(0, len(points), 2):
            starts.add(round(float(points[i][0]), 6))
    return sorted(starts)


def _sample_rate(audio_path: str) -> int:
    import soundfile as sf
    return sf.info(audio_path).samplerate


def _build_sv_xml(audio_path: str, sample_rate: int, duration_sec: float,
                  envelopes: List[Tuple[str, List, str]], layout: Layout,
                  markers: bool = True,
                  markers_scope: Literal["all", "waveform"] = "waveform") -> bytes:
    root = ET.Element("sv")
    data = ET.SubElement(root, "data")

    end_frame = round(duration_sec * sample_rate)

    ET.SubElement(data, "model", {
        "id": "0", "name": os.path.basename(audio_path),
        "sampleRate": str(sample_rate), "start": "0", "end": str(end_frame),
        "type": "wavefile", "file": audio_path, "mainModel": "true",
    })
    ET.SubElement(data, "playparameters", {
        "mute": "false", "pan": "0", "gain": "1", "clipId": "", "model": "0",
    })
    ET.SubElement(data, "layer", {
        "id": "1", "type": "timeruler", "name": "Ruler", "model": "0",
        "colourName": "White", "colour": "#ffffff", "darkBackground": "true",
    })
    ET.SubElement(data, "layer", {
        "id": "2", "type": "waveform", "name": "Waveform", "model": "0",
        "gain": "1", "showMeans": "1", "greyscale": "1", "channelMode": "0",
        "channel": "-1", "scale": "0", "middleLineHeight": "0.5",
        "aggressive": "0", "autoNormalize": "0", "oversampling": "1",
        "colourName": "Bright Blue", "colour": "#1e96ff", "darkBackground": "true",
    })
    # Spectrogram: finestra 8192, overlap 75% (windowHopLevel=3), tutti i canali
    # mixati, colore White on Black (colourScheme=2 in ColourMapper.cpp), scala
    # lineare in frequenza (frequencyScale=0).
    ET.SubElement(data, "layer", {
        "id": "3", "type": "spectrogram", "name": "Spectrogram", "model": "0",
        "channel": "-1",
        "windowSize": "8192", "windowHopLevel": "3",
        "colourScheme": "2", "colourRotation": "0",
        "gain": "1", "threshold": "-80",
        "minFrequency": "0", "maxFrequency": "0",
        "frequencyScale": "0", "binDisplay": "0",
        "normalizeColumns": "0", "normalizeVisibleArea": "0",
        "darkBackground": "true",
    })

    # Modelli + dataset + layer per ogni envelope
    layer_ids: List[Tuple[str, str, str]] = []  # (layer_id, model_id, path)
    next_id = 4
    for i, (path, points, env_type) in enumerate(envelopes):
        model_id = str(next_id);    next_id += 1
        dataset_id = str(next_id);  next_id += 1
        layer_id = str(next_id);    next_id += 1

        ET.SubElement(data, "model", {
            "id": model_id, "name": path,
            "sampleRate": str(sample_rate), "type": "sparse",
            "dimensions": "2", "resolution": "1",
            "notifyOnAdd": "true", "dataset": dataset_id,
        })
        ds = ET.SubElement(data, "dataset", {"id": dataset_id, "dimensions": "2"})
        for t_norm, value in points:
            frame = str(round(t_norm * duration_sec * sample_rate))
            ET.SubElement(ds, "point", {"frame": frame, "value": str(value), "label": ""})

        colour, colour_name = _COLOURS[i % len(_COLOURS)]
        plot_style = _PLOT_STYLE_BY_TYPE.get(env_type, _PLOT_STYLE_DEFAULT)
        ET.SubElement(data, "layer", {
            "id": layer_id, "type": "timevalues", "name": path, "model": model_id,
            "plotStyle": plot_style, "verticalScale": "0",
            "colourName": colour_name, "colour": colour, "darkBackground": "true",
        })
        layer_ids.append((layer_id, model_id, path))

    # Layer marker: un time instant all'inizio di ogni plateau (confini degli
    # stati). Modello 1D sparse; etichetta = indice plateau (1-based). Viene
    # poi referenziato in ogni pane, cosi' le linee verticali sono allineate su
    # waveform ed envelope e la navigazione PgUp/PgDown ci salta sopra.
    marker_ref: Tuple[str, str] | None = None
    plateau_starts = _plateau_starts(envelopes) if markers else []
    if plateau_starts:
        marker_model_id = str(next_id);    next_id += 1
        marker_dataset_id = str(next_id);  next_id += 1
        marker_layer_id = str(next_id);    next_id += 1

        ET.SubElement(data, "model", {
            "id": marker_model_id, "name": "Plateau markers",
            "sampleRate": str(sample_rate), "type": "sparse",
            "dimensions": "1", "resolution": "1",
            "notifyOnAdd": "true", "dataset": marker_dataset_id,
        })
        # Mute esplicito: un modello sparse e' audibile di default e SV
        # sintetizza un click percussivo a ogni instant durante il playback.
        # Senza questo, ogni marker produrrebbe un "click" udibile.
        ET.SubElement(data, "playparameters", {
            "mute": "true", "pan": "0", "gain": "1",
            "clipId": "", "model": marker_model_id,
        })
        mds = ET.SubElement(data, "dataset", {"id": marker_dataset_id, "dimensions": "1"})
        for idx, t_norm in enumerate(plateau_starts, start=1):
            frame = str(round(t_norm * duration_sec * sample_rate))
            ET.SubElement(mds, "point", {"frame": frame, "label": str(idx)})
        ET.SubElement(data, "layer", {
            "id": marker_layer_id, "type": "timeinstants", "name": "Plateau markers",
            "model": marker_model_id, "plotStyle": "0",  # PlotInstants
            "colourName": "White", "colour": "#ffffff", "darkBackground": "true",
        })
        marker_ref = (marker_layer_id, marker_model_id)

    # Display
    display = ET.SubElement(root, "display")
    ET.SubElement(display, "window", {"width": "1728", "height": "1057"})

    n_panes = 1 + (1 if layout == "single" else len(envelopes))
    pane_height = str(max(150, 912 // n_panes))

    def _pane(parent):
        return ET.SubElement(parent, "view", {
            "centre": "0", "zoom": "1024", "deepZoom": "1",
            "followPan": "1", "followZoom": "1", "tracking": "page",
            "type": "pane", "centreLineVisible": "1", "height": pane_height,
        })

    def _ruler_layer(pane):
        ET.SubElement(pane, "layer", {
            "id": "1", "type": "timeruler", "name": "Ruler",
            "model": "0", "visible": "true",
        })

    def _marker_layer(pane, *, waveform_pane: bool = False):
        if marker_ref is None:
            return
        if markers_scope == "waveform" and not waveform_pane:
            return
        layer_id, model_id = marker_ref
        ET.SubElement(pane, "layer", {
            "id": layer_id, "type": "timeinstants", "name": "Plateau markers",
            "model": model_id, "visible": "true",
        })

    waveform_pane = _pane(display)
    _ruler_layer(waveform_pane)
    ET.SubElement(waveform_pane, "layer", {
        "id": "3", "type": "spectrogram", "name": "Spectrogram",
        "model": "0", "visible": "true",
    })
    ET.SubElement(waveform_pane, "layer", {
        "id": "2", "type": "waveform", "name": "Waveform",
        "model": "0", "visible": "true",
    })
    _marker_layer(waveform_pane, waveform_pane=True)

    if layout == "single":
        env_pane = _pane(display)
        _ruler_layer(env_pane)
        for layer_id, model_id, path in layer_ids:
            ET.SubElement(env_pane, "layer", {
                "id": layer_id, "type": "timevalues", "name": path,
                "model": model_id, "visible": "true",
            })
        _marker_layer(env_pane)
    else:  # multi
        for layer_id, model_id, path in layer_ids:
            pane = _pane(display)
            _ruler_layer(pane)
            ET.SubElement(pane, "layer", {
                "id": layer_id, "type": "timevalues", "name": path,
                "model": model_id, "visible": "true",
            })
            _marker_layer(pane)

    ET.SubElement(root, "selections")

    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE sonic-visualiser>\n'
    xml_bytes += ET.tostring(root, encoding="unicode").encode("utf-8")
    return bz2.compress(xml_bytes)


def variant_to_sv(variant_yaml_path: str, audio_path: str, out_path: str,
                  layout: Layout = "multi", markers: bool = True,
                  markers_scope: Literal["all", "waveform"] = "waveform") -> str:
    """Legge un variant YAML + audio, scrive un file .sv pronto per SV.

    Con ``markers=True`` (default) aggiunge un layer ``timeinstants`` con un
    marker all'inizio di ogni plateau. ``markers_scope`` controlla in quali
    pane appaiono: ``"all"`` (default) li replica in ogni pane, ``"waveform"``
    li mostra solo nel pane della forma d'onda.
    """
    import yaml

    with open(variant_yaml_path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    duration = float(doc.get("duration", 1.0))
    streams = doc.get("streams", [])
    envelopes = _find_envelopes(streams[0]) if streams else []

    sr = _sample_rate(audio_path)
    compressed = _build_sv_xml(os.path.abspath(audio_path), sr, duration,
                               envelopes, layout, markers=markers,
                               markers_scope=markers_scope)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(compressed)
    return out_path
