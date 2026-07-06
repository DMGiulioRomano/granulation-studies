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
from .value_generators import GENERATORS, resolve as resolve_values

# Chiavi che scelgono come popolare i valori di un asse: mutuamente esclusive.
_GENERATOR_KEYS = frozenset({"values", *GENERATORS})


@dataclass(frozen=True)
class Axis:
    """Un parametro sotto studio."""

    name: str
    path: str
    baseline: float
    values: List[float]
    interpolation: str = "linear"   # linear | cubic | step


# Chiavi riservate sotto ``axes:`` che non descrivono un asse ma il timing
# degli envelope (vedi ``envelope_sweep``). Restano a livello study per garantire
# comparabilita' tra i file generati.
_AXES_RESERVED_KEYS = ("plateau", "transition", "interpolation")


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
    orderings: List[List[str]] = field(default_factory=list)
    mode: str = "discrete"          # discrete | envelope | both
    combine: str = "cartesian"      # cartesian (prodotto) | parallel (zip)
    plateau: float = 5.0            # secondi per plateau (ascolto stabile)
    transition: float = 5.0         # secondi per transizione tra plateau
    interpolation: str = "linear"   # linear | cubic
    stream_id: str | None = None    # sotto-cartella per versionare gli output

    def axis(self, name: str) -> Axis:
        for ax in self.axes:
            if ax.name == name:
                return ax
        raise KeyError(name)


def _validate(spec: StudySpec) -> None:
    if not spec.axes:
        raise ValueError("Lo studio deve definire almeno un asse in 'axes'.")
    if spec.combine not in ("cartesian", "parallel"):
        raise ValueError(
            f"sweep.combine '{spec.combine}' non valido: usa 'cartesian' o 'parallel'."
        )
    n = len(spec.axes)
    for order in spec.orders:
        if order < 0 or order > n:
            raise ValueError(
                f"order {order} fuori range: con {n} assi gli ordini validi "
                f"sono 0..{n}."
            )
    axis_names = {ax.name for ax in spec.axes}
    for ordering in spec.orderings:
        unknown = set(ordering) - axis_names
        if unknown:
            raise ValueError(f"orderings: assi sconosciuti {sorted(unknown)}")
        dupes = [n for n in ordering if ordering.count(n) > 1]
        if dupes:
            raise ValueError(f"orderings: assi duplicati {sorted(set(dupes))}")
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


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _replace_generators(merged: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Se un override sceglie un generatore per un asse, rimpiazza quello ereditato.

    Il deep-merge conserva le chiavi della base: un asse con ``values`` di base a
    cui lo stream aggiunge ``ramp`` finirebbe con entrambe (collisione). Coerente
    con la semantica "le liste rimpiazzano": la chiave-generatore dell'override
    vince, si tolgono le altre ereditate su quello stesso asse.
    """
    ov_axes = override.get("axes") or {}
    merged_axes = merged.get("axes") or {}
    for name, ov in ov_axes.items():
        if not isinstance(ov, dict):
            continue
        chosen = _GENERATOR_KEYS & ov.keys()
        ax = merged_axes.get(name)
        if chosen and isinstance(ax, dict):
            for k in _GENERATOR_KEYS - chosen:
                ax.pop(k, None)


def resolve_streams(data: Dict[str, Any], study_id: str | None = None) -> List["StudySpec"]:
    """Ritorna una lista di StudySpec, uno per stream.

    Se ``streams:`` è assente, ritorna un singolo spec senza stream_id.
    """
    sid = study_id or data.get("study_id") or "study"
    streams = data.get("streams")
    if not streams:
        return [parse_study_spec(data, sid)]
    result = []
    for stream_id, override in streams.items():
        merged = _deep_merge(data, override or {})
        _replace_generators(merged, override or {})
        merged.pop("streams", None)
        merged.setdefault("sweep", {})["stream_id"] = stream_id
        result.append(parse_study_spec(merged, sid))
    return result


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

    study_interpolation = axes_raw.get("interpolation", "linear")
    axes: List[Axis] = []
    for name, cfg in axes_raw.items():
        if name in _AXES_RESERVED_KEYS:
            continue
        axes.append(
            Axis(
                name=name,
                path=cfg["path"],
                baseline=_resolve_baseline(name, cfg, _defaults_cache),
                values=resolve_values(cfg),
                interpolation=cfg.get("interpolation", study_interpolation),
            )
        )
    sweep_cfg = data.get("sweep") or {}
    orders = list(sweep_cfg.get("orders", list(range(1, len(axes) + 1))))
    orderings = [list(o) for o in sweep_cfg.get("orderings", [])]
    spec = StudySpec(
        study_id=study_id or data.get("study_id") or "study",
        title=data.get("title"),
        seed=data.get("seed"),
        duration=data.get("duration"),
        samples_dir=data.get("samples_dir"),
        base=dict(data.get("base") or {}),
        axes=axes,
        orders=orders,
        orderings=orderings,
        mode=sweep_cfg.get("mode", "discrete"),
        combine=sweep_cfg.get("combine", "cartesian"),
        plateau=float(axes_raw.get("plateau", 5.0)),
        transition=float(axes_raw.get("transition", 5.0)),
        interpolation=axes_raw.get("interpolation", "linear"),
        stream_id=sweep_cfg.get("stream_id") or None,
    )
    _validate(spec)
    return spec


def load_study_spec(path: str) -> StudySpec:
    """Carica e valida ``study.yml`` da disco."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    study_id = data.get("study_id") or os.path.basename(os.path.dirname(os.path.abspath(path)))
    return parse_study_spec(data, study_id=study_id)
