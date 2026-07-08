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
#   "8" = Stepped          -> sample-and-hold, salto netto al breakpoint successivo
# (7 e 8 esistono solo nel fork DMGiulioRomano/svgui.)
_PLOT_STYLE_BY_TYPE = {
    "linear": "3",
    "cubic": "7",
    "step": "8",
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


_ENVELOPE_TYPES = {"linear", "cubic", "step"}


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
    for _path, points, env_type in envelopes:
        # step: un solo punto per valore (nessun doppio punto plateau), ogni
        # punto e' un inizio-gradino. linear/cubic: breakpoint a coppie
        # ``t_start, t_end`` -> gli inizi sono agli indici pari.
        stride = 1 if env_type == "step" else 2
        for i in range(0, len(points), stride):
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

    # multi: un pane per *gruppo* di envelope. Il gruppo e' la parte del path
    # prima di '/' (lo stream_id, presente solo negli export stack): cosi' gli
    # assi di uno stesso stream stanno in un pane unico. Per lo sweep i path non
    # hanno '/', quindi ogni envelope e' un gruppo a se' -> un pane per envelope,
    # identico a prima.
    from itertools import groupby

    def _group_key(item: Tuple[str, str, str]) -> str:
        return item[2].split("/", 1)[0]

    multi_groups = [list(g) for _k, g in groupby(layer_ids, key=_group_key)]

    n_panes = 1 + (1 if layout == "single" else len(multi_groups))
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
    else:  # multi: un pane per gruppo (per stream negli export stack)
        for group in multi_groups:
            pane = _pane(display)
            _ruler_layer(pane)
            for layer_id, model_id, path in group:
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


def _stack_envelopes(doc: Any) -> List[Tuple[str, List, str]]:
    """Envelope di *tutti* gli stream del documento stack, con path prefissato.

    A differenza del singolo file sweep (un solo stream), il documento stack
    collassa N stream sommati in un audio: per non confonderli nei pannelli, il
    path di ogni envelope e' prefissato dallo stream_id (``base/density``). Gli
    assi scalari non producono envelope, quindi restano fuori.
    """
    out: List[Tuple[str, List, str]] = []
    for stream in doc.get("streams", []):
        sid = stream.get("stream_id", "stream")
        for path, points, env_type in _find_envelopes(stream):
            out.append((f"{sid}/{path}", points, env_type))
    return out


def _build_sv_xml_stems(stems: List[Tuple[str, str, int, float, List[Tuple[str, List, str]]]]) -> bytes:
    """Un pane per stem: waveform + spectrogram + tutti i suoi envelope insieme.

    ``stems``: lista di (stream_id, audio_path_assoluto, sample_rate, duration_sec, envelopes).
    Ogni stem ha il proprio model audio (i file stem sono resi con onset
    relativo a 0, v. ``StemsRenderMode``), cosi' ognuno mantiene la propria
    durata e sample rate.
    """
    root = ET.Element("sv")
    data = ET.SubElement(root, "data")

    display = ET.SubElement(root, "display")
    ET.SubElement(display, "window", {"width": "1728", "height": "1057"})

    n_panes = len(stems)
    pane_height = str(max(150, 912 // max(n_panes, 1)))

    def _pane():
        return ET.SubElement(display, "view", {
            "centre": "0", "zoom": "1024", "deepZoom": "1",
            "followPan": "1", "followZoom": "1", "tracking": "page",
            "type": "pane", "centreLineVisible": "1", "height": pane_height,
        })

    next_id = 0
    for stream_index, (stream_id, audio_path, sr, duration, envelopes) in enumerate(stems):
        wave_model_id = str(next_id); next_id += 1
        spec_layer_id = str(next_id); next_id += 1
        wave_layer_id = str(next_id); next_id += 1
        end_frame = round(duration * sr)

        # SV usa il mainModel come riferimento del transport (durata, sample
        # rate, play/pausa): senza uno, la barra spaziatrice non ha nulla da
        # suonare. Il primo stem fa da main; gli altri restano playparameters
        # non mutati, cosi' vengono comunque mixati in playback.
        ET.SubElement(data, "model", {
            "id": wave_model_id, "name": os.path.basename(audio_path),
            "sampleRate": str(sr), "start": "0", "end": str(end_frame),
            "type": "wavefile", "file": audio_path,
            "mainModel": "true" if stream_index == 0 else "false",
        })
        ET.SubElement(data, "playparameters", {
            "mute": "false", "pan": "0", "gain": "1", "clipId": "", "model": wave_model_id,
        })
        ET.SubElement(data, "layer", {
            "id": spec_layer_id, "type": "spectrogram", "name": f"{stream_id} :: Spectrogram",
            "model": wave_model_id, "channel": "-1",
            "windowSize": "8192", "windowHopLevel": "3",
            "colourScheme": "2", "colourRotation": "0",
            "gain": "1", "threshold": "-80",
            "minFrequency": "0", "maxFrequency": "0",
            "frequencyScale": "0", "binDisplay": "0",
            "normalizeColumns": "0", "normalizeVisibleArea": "0",
            "darkBackground": "true",
        })
        ET.SubElement(data, "layer", {
            "id": wave_layer_id, "type": "waveform", "name": f"{stream_id} :: Waveform",
            "model": wave_model_id, "gain": "1", "showMeans": "1", "greyscale": "1",
            "channelMode": "0", "channel": "-1", "scale": "0", "middleLineHeight": "0.5",
            "aggressive": "0", "autoNormalize": "0", "oversampling": "1",
            "colourName": "Bright Blue", "colour": "#1e96ff", "darkBackground": "true",
        })

        pane = _pane()
        ET.SubElement(pane, "layer", {
            "id": "ruler_" + stream_id, "type": "timeruler", "name": "Ruler",
            "model": wave_model_id, "visible": "true",
        })
        ET.SubElement(pane, "layer", {
            "id": spec_layer_id, "type": "spectrogram", "name": f"{stream_id} :: Spectrogram",
            "model": wave_model_id, "visible": "true",
        })
        ET.SubElement(pane, "layer", {
            "id": wave_layer_id, "type": "waveform", "name": f"{stream_id} :: Waveform",
            "model": wave_model_id, "visible": "true",
        })

        for i, (path, points, env_type) in enumerate(envelopes):
            env_model_id = str(next_id); next_id += 1
            env_dataset_id = str(next_id); next_id += 1
            env_layer_id = str(next_id); next_id += 1

            ET.SubElement(data, "model", {
                "id": env_model_id, "name": f"{stream_id}/{path}",
                "sampleRate": str(sr), "type": "sparse",
                "dimensions": "2", "resolution": "1",
                "notifyOnAdd": "true", "dataset": env_dataset_id,
            })
            ds = ET.SubElement(data, "dataset", {"id": env_dataset_id, "dimensions": "2"})
            for t_norm, value in points:
                frame = str(round(t_norm * duration * sr))
                ET.SubElement(ds, "point", {"frame": frame, "value": str(value), "label": ""})

            colour, colour_name = _COLOURS[i % len(_COLOURS)]
            plot_style = _PLOT_STYLE_BY_TYPE.get(env_type, _PLOT_STYLE_DEFAULT)
            ET.SubElement(data, "layer", {
                "id": env_layer_id, "type": "timevalues", "name": f"{stream_id}/{path}",
                "model": env_model_id, "plotStyle": plot_style, "verticalScale": "0",
                "colourName": colour_name, "colour": colour, "darkBackground": "true",
            })
            ET.SubElement(pane, "layer", {
                "id": env_layer_id, "type": "timevalues", "name": f"{stream_id}/{path}",
                "model": env_model_id, "visible": "true",
            })

    ET.SubElement(root, "selections")

    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE sonic-visualiser>\n'
    xml_bytes += ET.tostring(root, encoding="unicode").encode("utf-8")
    return bz2.compress(xml_bytes)


def stack_stems_to_sv(stack_yaml_path: str, audio_dir: str, out_path: str) -> str | None:
    """.sv con un pane per stem audio (un file audio per stream), non per il mix.

    A differenza di ``stack_to_sv`` (un solo pane waveform contro l'audio
    sommato), qui ogni stream ha il proprio pane con la propria waveform +
    spectrogram + tutti i suoi envelope insieme. Richiede gli stem gia'
    renderizzati (``render --stem``, attivo di default): ``{base}__{stream_id}.aif``
    accanto al mix in ``audio_dir`` (v. ``DefaultNamingStrategy``). Ritorna
    ``None`` (senza scrivere nulla) se manca anche un solo stem.
    """
    import yaml

    with open(stack_yaml_path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    stems = []
    for stream in doc.get("streams", []):
        stream_id = stream.get("stream_id", "stream")
        audio_path = os.path.join(audio_dir, f"stack__{stream_id}.aif")
        if not os.path.exists(audio_path):
            print(f"[sv] stem mancante per '{stream_id}': {audio_path} (esegui 'render --stem')")
            return None
        duration = float(stream.get("duration", doc.get("duration", 1.0)))
        envelopes = _find_envelopes(stream)
        stems.append((stream_id, os.path.abspath(audio_path), _sample_rate(audio_path), duration, envelopes))

    compressed = _build_sv_xml_stems(stems)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(compressed)
    return out_path


def stack_to_sv(stack_yaml_path: str, audio_path: str, out_path: str,
                layout: Layout = "multi") -> str:
    """Scrive un .sv per il documento multi-stream ``stack.yml`` contro il suo audio.

    Un solo file per lo stack (gli stream sono sommati in un audio): gli envelope
    di tutti gli stream finiscono nei pannelli, path prefissato per stream. Niente
    marker di plateau: sono un concetto di sweep (griglia plateau/transition
    sincronizzata), assente in stack dove ogni asse ha la sua X.
    """
    import yaml

    with open(stack_yaml_path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    duration = float(doc.get("duration", 1.0))
    envelopes = _stack_envelopes(doc)

    sr = _sample_rate(audio_path)
    compressed = _build_sv_xml(os.path.abspath(audio_path), sr, duration,
                               envelopes, layout, markers=False)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(compressed)
    return out_path
