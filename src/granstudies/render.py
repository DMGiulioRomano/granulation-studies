"""Batch: scrittura varianti YAML e rendering audio + partitura PDF.

Le due responsabilita' sono separate apposta: ``write_variants`` materializza
gli YAML (che l'utente puo' ispezionare/modificare a mano), ``render_variants``
li renderizza in audio e partitura. Cosi' il loop di studio resta trasparente.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import yaml

from . import engine_bridge
from .study_spec import StudySpec
from .sweep import Variant, generate_variants


def write_variants(spec: StudySpec, out_dir: str) -> List[str]:
    """Genera lo sweep e scrive un file YAML per variante in ``out_dir``.

    Returns: lista dei path YAML scritti (ordinati come lo sweep).
    """
    variants = generate_variants(spec)
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []
    for v in variants:
        path = os.path.join(out_dir, f"{v.name}.yml")
        doc = v.to_document(spec)
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
        written.append(path)
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

    manifest: List[Dict[str, Any]] = []
    for fname in sorted(os.listdir(variant_dir)):
        if not fname.endswith((".yml", ".yaml")):
            continue
        name = os.path.splitext(fname)[0]
        yaml_path = os.path.join(variant_dir, fname)
        audio_path = os.path.join(audio_dir, f"{name}.aif")

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
            engine_bridge.score_pdf(yaml_path, pdf_path, samples_dir=samples_dir)
            entry["score"] = pdf_path
        manifest.append(entry)
    return manifest
