"""Ponte verso PythonGranularEngine (incluso come submodule in ``engine/``).

Dall'introduzione dell'API programmatica ``pge.api`` (refactor library/CLI
dell'engine, Fasi 1-4) questo modulo e' un wrapper sottile: niente piu'
replica di ``main._build_renderer`` ne' monkey-patch di ``PATHSAMPLES`` —
la directory dei sample viaggia come parametro ``samples_dir`` dell'API.

Resta ``_ensure_engine_on_path`` perche' il submodule non e' installato nel
venv: si usa inserendo ``engine/src`` in ``sys.path`` (in alternativa si
potrebbe fare ``pip install -e engine/``; decisione rimandata).
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
ENGINE_SRC = os.path.join(REPO_ROOT, "engine", "src")


def _ensure_engine_on_path() -> None:
    """Inserisce ``engine/src`` in ``sys.path`` se non gia' presente."""
    if not os.path.isdir(ENGINE_SRC):
        raise RuntimeError(
            "Submodule 'engine' non inizializzato. Esegui:\n"
            "  git submodule update --init --recursive"
        )
    if ENGINE_SRC not in sys.path:
        sys.path.insert(0, ENGINE_SRC)


def _silence_loggers(log_dir: str) -> None:
    """Disattiva il logging su console dell'engine, file su ``log_dir``.

    I ``configure_*`` sono API pubblica dell'engine: vanno chiamati prima
    di ``load_generator`` (la libreria non configura mai i logger da se').
    """
    from pge import configure_clip_logger, configure_engine_logger

    configure_clip_logger(
        enabled=False, console_enabled=False, file_enabled=False
    )
    configure_engine_logger(yaml_name="granstudies", log_dir=log_dir)


def load_generator(
    yaml_path: str,
    samples_dir: Optional[str] = None,
    log_dir: Optional[str] = None,
):
    """Carica un Generator dell'engine con streams gia' materializzati."""
    _ensure_engine_on_path()
    _silence_loggers(log_dir or os.path.join(REPO_ROOT, "generated", ".logs"))
    from pge import api

    return api.load_generator(str(yaml_path), samples_dir=samples_dir)


def render(
    yaml_path: str,
    output_path: str,
    samples_dir: str,
    output_sr: int = 48000,
    per_stream: bool = False,
    use_cache: bool = False,
    cache_dir: Optional[str] = None,
) -> List[str]:
    """Renderizza un YAML in audio con il renderer NumPy (MIX di default).

    ``per_stream``: STEMS mode (un file per stream, engine ``--per-stream``)
    invece del MIX unico di default. ``use_cache`` attiva il caching
    incrementale per-stream dell'engine (``StreamCacheManager``): solo gli
    stream con fingerprint cambiato vengono ri-renderizzati. Ha effetto solo
    in combinazione con ``per_stream`` (e' l'unico caso con build
    incrementale per stream, vedi engine ``pge/cli.py``).

    Il GC degli stem orfani resta disattivato (``run_cache_gc=False``) come
    nel bridge pre-API: questo modulo non cancella file gia' generati.

    Returns: lista dei path audio generati (1 elemento in MIX mode, N in
    STEMS mode).
    """
    gen = load_generator(yaml_path, samples_dir=samples_dir)
    from pge import api

    cache_manifest_path = None
    if use_cache:
        yaml_basename = os.path.splitext(os.path.basename(str(yaml_path)))[0]
        cdir = cache_dir or "cache"
        os.makedirs(cdir, exist_ok=True)
        cache_manifest_path = os.path.join(cdir, f"{yaml_basename}.json")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    result = api.render(
        gen,
        str(output_path),
        renderer="numpy",
        per_stream=per_stream,
        run_cache_gc=False,
        output_sr=output_sr,
        samples_dir=samples_dir,
        cache_manifest_path=cache_manifest_path,
    )
    return result.audio_paths


def score_pdf(
    yaml_path: str,
    pdf_path: str,
    samples_dir: Optional[str] = None,
    config: Optional[dict] = None,
) -> str:
    """Esporta la partitura grafica (PDF) di un YAML via ScoreVisualizer."""
    gen = load_generator(yaml_path, samples_dir=samples_dir)
    from pge import api

    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
    return api.export_score_pdf(
        gen, str(pdf_path), config=config, samples_dir=samples_dir
    )


def parameter_bounds() -> dict:
    """Ritorna il registry ``GRANULAR_PARAMETERS`` dell'engine."""
    _ensure_engine_on_path()
    from pge.parameters.parameter_definitions import GRANULAR_PARAMETERS

    return GRANULAR_PARAMETERS


def parameter_defaults() -> dict:
    """Mappa ``yaml_path -> default`` da tutti gli schema dell'engine.

    Single source of truth per i valori a riposo dei parametri: invece di
    duplicare i default nello ``study.yml``, l'asse che omette ``baseline`` lo
    risolve da qui (vedi ``study_spec.parse_study_spec``). I path con
    ``default=None`` (es. ``density``) restano fuori dalla risoluzione e
    richiedono un baseline esplicito.
    """
    _ensure_engine_on_path()
    from pge.parameters.parameter_schema import ALL_SCHEMAS

    out: dict = {}
    for schema in ALL_SCHEMAS.values():
        for spec in schema:
            out[spec.yaml_path] = spec.default
    return out
