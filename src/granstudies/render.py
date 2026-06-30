"""Batch: scrittura varianti YAML e rendering audio + partitura PDF.

Le due responsabilita' sono separate apposta: ``write_variants`` materializza
gli YAML (che l'utente puo' ispezionare/modificare a mano), ``render_variants``
li renderizza in audio e partitura. Cosi' il loop di studio resta trasparente.
"""
from __future__ import annotations

import os
import warnings
from typing import Any, Dict, List

import yaml

from . import engine_bridge
from .study_spec import StudySpec
from .sweep import generate_discrete_variants
from .envelope_sweep import EnvelopeVariant, generate_envelope_variants
from .yaml_builder import build_document


class _Dumper(yaml.SafeDumper):
    pass


def _list_representer(dumper: yaml.SafeDumper, data: list) -> yaml.Node:
    flow = bool(data and isinstance(data[0], list))
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_Dumper.add_representer(list, _list_representer)


def _dump(path: str, doc: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(doc, fh, Dumper=_Dumper, sort_keys=False, allow_unicode=True)


def _write_discrete(spec: StudySpec, out_dir: str) -> List[str]:
    """Scrive le varianti statiche (una per combinazione) in ``out_dir``."""
    variants = generate_discrete_variants(spec)
    if variants and spec.duration is None and "duration" not in spec.base:
        warnings.warn(
            "mode discrete/both senza 'base.duration': i file discrete non "
            "avranno durata definita."
        )
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []
    for v in variants:
        path = os.path.join(out_dir, f"{v.name}.yml")
        _dump(path, v.to_document(spec))
        written.append(path)
    return written


def _envelope_document(spec: StudySpec, ev: EnvelopeVariant) -> Dict[str, Any]:
    """Documento YAML di un ``EnvelopeVariant``: stream dinamico normalizzato.

    La ``base.duration`` statica (valida solo per i file discrete) viene
    sostituita dalla durata *calcolata* da ``plateau``/``transition``: e' anche
    il fattore che scala i tempi normalizzati degli envelope. Tutti i file
    envelope girano in ``time_mode: normalized`` e gli assi mossi diventano
    envelope.
    """
    duration = ev.duration(spec)
    base = dict(spec.base)
    base.setdefault("stream_id", "stream")
    base["time_mode"] = "normalized"
    base["duration"] = duration
    return build_document(
        base,
        ev.overrides(spec),
        title=f"{spec.study_id} :: {ev.name}",
        seed=spec.seed,
        duration=duration,
        envelope_time_mode="normalized",
        envelope_type=spec.interpolation,
    )


def _write_envelope(spec: StudySpec, out_dir: str) -> List[str]:
    """Scrive le varianti envelope (una per combinazione di assi) in ``out_dir``."""
    variants = generate_envelope_variants(spec)
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []
    for ev in variants:
        path = os.path.join(out_dir, f"{ev.name}.yml")
        _dump(path, _envelope_document(spec, ev))
        written.append(path)
    return written


def write_variants(spec: StudySpec, out_dir: str) -> List[str]:
    """Genera lo sweep e scrive i file YAML in sotto-cartelle per modalita'.

    A seconda di ``spec.mode`` materializza ``out_dir/discrete/`` (varianti
    statiche), ``out_dir/envelope/`` (stream dinamici) o entrambi (``both``).

    Returns: lista dei path YAML scritti (discrete prima, poi envelope).
    """
    sub = spec.stream_id or ""
    written: List[str] = []
    if spec.mode in ("discrete", "both"):
        d = os.path.join(out_dir, "discrete", sub) if sub else os.path.join(out_dir, "discrete")
        written += _write_discrete(spec, d)
    if spec.mode in ("envelope", "both"):
        e = os.path.join(out_dir, "envelope", sub) if sub else os.path.join(out_dir, "envelope")
        written += _write_envelope(spec, e)
    return written


def render_variants(
    variant_dir: str,
    audio_dir: str,
    score_dir: str | None,
    samples_dir: str,
    output_sr: int = 48000,
) -> List[Dict[str, Any]]:
    """Renderizza ogni YAML in ``variant_dir`` -> audio (e PDF se ``score_dir``).

    Returns: manifest, una entry per variante con i path prodotti.
    """
    os.makedirs(audio_dir, exist_ok=True)
    if score_dir:
        os.makedirs(score_dir, exist_ok=True)

    # Discende ricorsivamente: ``variant_dir`` puo' contenere ``discrete/`` e
    # ``envelope/`` (vedi ``write_variants``). I sotto-path vengono rispecchiati
    # nelle cartelle audio/score, cosi' i due set restano separati.
    yaml_files: List[str] = []
    for root, _, files in os.walk(variant_dir):
        for fname in files:
            if fname.endswith((".yml", ".yaml")):
                yaml_files.append(os.path.join(root, fname))
    yaml_files.sort()

    manifest: List[Dict[str, Any]] = []
    for yaml_path in yaml_files:
        rel = os.path.relpath(yaml_path, variant_dir)
        name = os.path.splitext(rel)[0]
        audio_path = os.path.join(audio_dir, f"{name}.aif")
        os.makedirs(os.path.dirname(os.path.abspath(audio_path)), exist_ok=True)

        generated = engine_bridge.render(
            yaml_path, audio_path, samples_dir=samples_dir, output_sr=output_sr
        )
        entry: Dict[str, Any] = {
            "name": name,
            "yaml": yaml_path,
            "audio": generated[0] if generated else None,
        }
        if score_dir:
            pdf_path = os.path.join(score_dir, f"{name}.pdf")
            os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
            engine_bridge.score_pdf(yaml_path, pdf_path, samples_dir=samples_dir)
            entry["score"] = pdf_path
        manifest.append(entry)
    return manifest
