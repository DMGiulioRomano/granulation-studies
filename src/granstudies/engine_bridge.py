"""Ponte verso PythonGranularEngine (incluso come submodule in ``engine/``).

L'engine non e' un pacchetto installabile: si usa inserendo ``engine/src`` in
``sys.path`` (stesso pattern di ``engine/src/main.py``). Questo modulo isola
quella dipendenza e offre due operazioni di alto livello — ``render`` (YAML ->
audio NumPy) e ``score_pdf`` (YAML -> partitura) — piu' l'accesso ai bounds dei
parametri, single source of truth condivisa con l'engine.
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
    """Disattiva il logging su console dell'engine, file su ``log_dir``."""
    from shared.logger import configure_clip_logger, configure_engine_logger

    configure_clip_logger(
        enabled=False, console_enabled=False, file_enabled=False
    )
    configure_engine_logger(yaml_name="granstudies", log_dir=log_dir)


def _patch_sample_path(samples_dir: str) -> str:
    """Reindirizza il lookup dei sample dell'engine verso ``samples_dir``.

    L'engine risolve i sample tramite la costante di modulo ``PATHSAMPLES``
    (``./refs/``), letta a runtime sia in ``shared.utils`` che in
    ``rendering.score_visualizer``. La riscriviamo per puntare al corpus dello
    studio senza modificare il submodule. Ritorna il path con separatore finale.
    """
    base = samples_dir if samples_dir.endswith(os.sep) else samples_dir + os.sep
    import shared.utils as _utils

    _utils.PATHSAMPLES = base
    try:
        import rendering.score_visualizer as _sv

        _sv.PATHSAMPLES = base
    except Exception:
        pass
    return base


def load_generator(
    yaml_path: str,
    samples_dir: Optional[str] = None,
    log_dir: Optional[str] = None,
):
    """Carica un Generator dell'engine con streams gia' materializzati."""
    _ensure_engine_on_path()
    _silence_loggers(log_dir or os.path.join(REPO_ROOT, "generated", ".logs"))
    if samples_dir:
        _patch_sample_path(samples_dir)
    from engine.generator import Generator

    gen = Generator(str(yaml_path))
    gen.load_yaml()
    gen.create_elements()
    return gen


def render(
    yaml_path: str,
    output_path: str,
    samples_dir: str,
    output_sr: int = 48000,
    per_stream: bool = False,
    use_cache: bool = False,
    cache_dir: Optional[str] = None,
) -> List[str]:
    """Renderizza un YAML in audio con il renderer NumPy.

    Replica la costruzione del renderer NumPy di ``main._build_renderer`` ma con
    la directory dei sample configurabile (``samples/`` invece di ``refs/``).

    ``per_stream``: STEMS mode (un file per stream, engine/src/main.py
    ``--per-stream``) invece del MIX unico di default. ``use_cache`` attiva il
    caching incrementale per-stream dell'engine (``StreamCacheManager``): solo
    gli stream con fingerprint cambiato vengono ri-renderizzati. Ha effetto
    solo in combinazione con ``per_stream`` (e' l'unico caso con build
    incrementale per stream, vedi engine ``main.py``).

    Returns: lista dei path audio generati (1 elemento in MIX mode, N in
    STEMS mode).
    """
    _ensure_engine_on_path()
    gen = load_generator(yaml_path, samples_dir=samples_dir)

    from rendering.renderer_factory import RendererFactory
    from rendering.sample_registry import SampleRegistry
    from rendering.numpy_window_registry import NumpyWindowRegistry
    from rendering.audio_format import DEFAULT_FORMAT
    from rendering.rendering_engine import RenderingEngine
    from rendering.render_mode import StemsRenderMode, MixRenderMode
    from rendering.naming_strategy import DefaultNamingStrategy

    base_path = samples_dir if samples_dir.endswith(os.sep) else samples_dir + os.sep
    table_map = gen.ftable_manager.get_all_tables()
    sample_reg = SampleRegistry(base_path=base_path)
    window_reg = NumpyWindowRegistry()
    for _, (ftype, name) in table_map.items():
        if ftype == "sample":
            sample_reg.load(name)

    cache_manager = None
    if use_cache:
        from rendering.stream_cache_manager import StreamCacheManager

        yaml_basename = os.path.splitext(os.path.basename(yaml_path))[0]
        cdir = cache_dir or "cache"
        os.makedirs(cdir, exist_ok=True)
        cache_path = os.path.join(cdir, f"{yaml_basename}.json")
        cache_manager = StreamCacheManager(cache_path=cache_path)

    renderer = RendererFactory.create(
        "numpy",
        sample_registry=sample_reg,
        window_registry=window_reg,
        table_map=table_map,
        output_sr=output_sr,
        cache_manager=cache_manager,
        stream_data_map=gen.stream_data_map,
        audio_format=DEFAULT_FORMAT,
    )
    engine = RenderingEngine(
        renderer, naming_strategy=DefaultNamingStrategy(ext=DEFAULT_FORMAT.extension)
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    mode = StemsRenderMode() if per_stream else MixRenderMode()
    return engine.render(streams=gen.streams, output_path=output_path, mode=mode)


def score_pdf(
    yaml_path: str,
    pdf_path: str,
    samples_dir: Optional[str] = None,
    config: Optional[dict] = None,
) -> str:
    """Esporta la partitura grafica (PDF) di un YAML via ScoreVisualizer."""
    gen = load_generator(yaml_path, samples_dir=samples_dir)
    from rendering.score_visualizer import ScoreVisualizer

    cfg = {
        "page_duration": 15.0,
        "show_static_params": False,
        "show_voice_offsets": False,
        "envelope_filter": None,
        "magnify_auto": False,
        "magnify_targets": [],
    }
    if config:
        cfg.update(config)
    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
    viz = ScoreVisualizer(gen, config=cfg)
    viz.export_pdf(str(pdf_path))
    return pdf_path


def parameter_bounds() -> dict:
    """Ritorna il registry ``GRANULAR_PARAMETERS`` dell'engine."""
    _ensure_engine_on_path()
    from parameters.parameter_definitions import GRANULAR_PARAMETERS

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
    from parameters.parameter_schema import ALL_SCHEMAS

    out: dict = {}
    for schema in ALL_SCHEMAS.values():
        for spec in schema:
            out[spec.yaml_path] = spec.default
    return out
