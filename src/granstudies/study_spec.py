"""Parsing e validazione di ``study.yml`` (la definizione di uno studio).

Uno studio fissa uno stream *base* e un insieme di *assi* (i parametri sotto
osservazione). Ogni asse ha un path YAML, un valore di baseline e una lista di
valori di test. Lo sweep combinatorio (vedi ``sweep.py``) muove gli assi a
ordini crescenti (1 alla volta, a coppie, ...).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

from . import bounds as bounds_mod


@dataclass(frozen=True)
class Axis:
    """Un parametro sotto studio."""

    name: str
    path: str
    baseline: float
    values: List[float]


# Chiavi riservate sotto ``axes:`` che non descrivono un asse ma il timing
# degli envelope (vedi ``envelope_sweep``). Restano a livello study per garantire
# comparabilita' tra i file generati.
_AXES_RESERVED_KEYS = ("plateau", "transition")


@dataclass(frozen=True)
class StudySpec:
    study_id: str
    title: str | None
    seed: int | None
    duration: float | None
    samples_dir: str | None
    base: Dict[str, Any]
    axes: List[Axis]
    orders: List[int]
    mode: str = "discrete"          # discrete | envelope | both
    plateau: float = 5.0            # secondi per plateau (ascolto stabile)
    transition: float = 5.0         # secondi per transizione tra plateau

    def axis(self, name: str) -> Axis:
        for ax in self.axes:
            if ax.name == name:
                return ax
        raise KeyError(name)


def _validate(spec: StudySpec) -> None:
    if not spec.axes:
        raise ValueError("Lo studio deve definire almeno un asse in 'axes'.")
    n = len(spec.axes)
    for order in spec.orders:
        if order < 0 or order > n:
            raise ValueError(
                f"order {order} fuori range: con {n} assi gli ordini validi "
                f"sono 0..{n}."
            )
    seen = set()
    for ax in spec.axes:
        if ax.name in seen:
            raise ValueError(f"Asse duplicato: {ax.name}")
        seen.add(ax.name)
        if not ax.values:
            raise ValueError(f"Asse '{ax.name}' senza valori di test.")
        # Avviso non bloccante: valori fuori bounds engine vengono poi clampati.
        for v in list(ax.values) + [ax.baseline]:
            b = bounds_mod.bounds_for(ax.path)
            if b is not None:
                lo, hi = b
                if (lo is not None and v < lo) or (hi is not None and v > hi):
                    raise ValueError(
                        f"Asse '{ax.name}' valore {v} fuori bounds {b} "
                        f"per il path '{ax.path}'."
                    )


def _resolve_baseline(name: str, cfg: Dict[str, Any], defaults: Dict[str, Any] | None):
    """Risolve il ``baseline`` di un asse: esplicito o dal default engine.

    Single source of truth: se ``baseline`` e' omesso, lo si legge dal default
    dello schema engine via ``path``. I path ``pitch.*`` (unit-driven, nessun
    default) e i parametri con ``default=None`` (es. ``density``) richiedono un
    baseline esplicito.
    """
    if "baseline" in cfg:
        return cfg["baseline"]
    path = cfg["path"]
    if path == "pitch" or path.startswith("pitch."):
        raise ValueError(
            f"Asse '{name}': path '{path}' e' unit-driven (pitch), "
            f"'baseline' e' obbligatorio."
        )
    if defaults is None:
        from .engine_bridge import parameter_defaults

        defaults = parameter_defaults()
    if path not in defaults or defaults[path] is None:
        raise ValueError(
            f"Asse '{name}': nessun default engine per il path '{path}', "
            f"'baseline' e' obbligatorio."
        )
    return defaults[path]


def parse_study_spec(data: Dict[str, Any], study_id: str | None = None) -> StudySpec:
    """Costruisce uno ``StudySpec`` da un dict gia' caricato."""
    axes_raw = data.get("axes") or {}
    # Risolve i default engine una sola volta, solo se serve (lazy).
    _defaults_cache: Dict[str, Any] | None = None
    needs_defaults = any(
        k not in _AXES_RESERVED_KEYS and isinstance(v, dict) and "baseline" not in v
        for k, v in axes_raw.items()
    )
    if needs_defaults:
        from .engine_bridge import parameter_defaults

        _defaults_cache = parameter_defaults()

    axes: List[Axis] = []
    for name, cfg in axes_raw.items():
        if name in _AXES_RESERVED_KEYS:
            continue
        axes.append(
            Axis(
                name=name,
                path=cfg["path"],
                baseline=_resolve_baseline(name, cfg, _defaults_cache),
                values=list(cfg["values"]),
            )
        )
    sweep_cfg = data.get("sweep") or {}
    orders = list(sweep_cfg.get("orders", list(range(1, len(axes) + 1))))
    spec = StudySpec(
        study_id=study_id or data.get("study_id") or "study",
        title=data.get("title"),
        seed=data.get("seed"),
        duration=data.get("duration"),
        samples_dir=data.get("samples_dir"),
        base=dict(data.get("base") or {}),
        axes=axes,
        orders=orders,
        mode=sweep_cfg.get("mode", "discrete"),
        plateau=float(axes_raw.get("plateau", 5.0)),
        transition=float(axes_raw.get("transition", 5.0)),
    )
    _validate(spec)
    return spec


def load_study_spec(path: str) -> StudySpec:
    """Carica e valida ``study.yml`` da disco."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    study_id = data.get("study_id") or os.path.basename(os.path.dirname(os.path.abspath(path)))
    return parse_study_spec(data, study_id=study_id)
