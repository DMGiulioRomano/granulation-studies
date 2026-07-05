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
    """Scrive lo YAML solo se il contenuto e' cambiato.

    L'mtime del file resta fermo quando la variante e' identica: e' il segnale
    che ``render_variants`` usa per saltare i render gia' aggiornati.
    """
    text = yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            if fh.read() == text:
                return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


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
        envelope_types=ev.envelope_types(spec),
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


def _render_one(
    yaml_path: str,
    audio_path: str,
    pdf_path: str | None,
    samples_dir: str,
    output_sr: int,
) -> str:
    """Renderizza una singola variante (worker per il pool di processi)."""
    engine_bridge.render(
        yaml_path, audio_path, samples_dir=samples_dir, output_sr=output_sr
    )
    if pdf_path:
        engine_bridge.score_pdf(yaml_path, pdf_path, samples_dir=samples_dir)
    return audio_path


def _is_up_to_date(target: str, source: str) -> bool:
    return os.path.exists(target) and os.path.getmtime(target) >= os.path.getmtime(source)


def render_variants(
    variant_dir: str,
    audio_dir: str,
    score_dir: str | None,
    samples_dir: str,
    output_sr: int = 48000,
    force: bool = False,
    jobs: int | None = None,
) -> List[Dict[str, Any]]:
    """Renderizza ogni YAML in ``variant_dir`` -> audio (e PDF se ``score_dir``).

    Incrementale: una variante il cui audio (e PDF) e' piu' recente dello YAML
    viene saltata (``force=True`` per rirenderizzare tutto). Le varianti da
    fare girano in parallelo su un pool di processi (``jobs``, default
    min(8, cpu)); ogni render dell'engine e' mono-core e indipendente.

    Returns: manifest, una entry per variante con i path prodotti e il flag
    ``skipped``.
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
    pending: List[tuple] = []
    for yaml_path in yaml_files:
        rel = os.path.relpath(yaml_path, variant_dir)
        name = os.path.splitext(rel)[0]
        # Se il path ha 3 componenti (mode/stream_id/variant), aggiungo
        # il nome dello stream al basename per distinguerli in SV.
        parts = name.split(os.sep)
        if len(parts) >= 3:
            audio_basename = f"{parts[-2]}_{parts[-1]}"
        else:
            audio_basename = parts[-1]
        audio_path = os.path.join(audio_dir, *parts[:-1], audio_basename + ".aif")
        pdf_path = os.path.join(score_dir, f"{name}.pdf") if score_dir else None

        entry: Dict[str, Any] = {"name": name, "yaml": yaml_path, "audio": audio_path}
        if pdf_path:
            entry["score"] = pdf_path
        entry["skipped"] = (
            not force
            and _is_up_to_date(audio_path, yaml_path)
            and (pdf_path is None or _is_up_to_date(pdf_path, yaml_path))
        )
        manifest.append(entry)
        if entry["skipped"]:
            continue
        os.makedirs(os.path.dirname(os.path.abspath(audio_path)), exist_ok=True)
        if pdf_path:
            os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
        pending.append((yaml_path, audio_path, pdf_path, samples_dir, output_sr))

    if pending:
        # ponytail: cap a 8 worker, una variante lunga puo' tenere in RAM
        # l'intero buffer audio; alzare con jobs= se la memoria lo consente.
        workers = jobs or min(8, os.cpu_count() or 1, len(pending))
        if workers == 1:
            for args in pending:
                _render_one(*args)
        else:
            from concurrent.futures import ProcessPoolExecutor, as_completed

            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_render_one, *args) for args in pending]
                for fut in as_completed(futures):
                    fut.result()
    return manifest
