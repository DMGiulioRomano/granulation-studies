"""Generazione combinatoria delle varianti: OAT -> fattoriale completo.

Per ogni ordine k richiesto si prendono tutte le combinazioni di k assi e, per
ciascuna, il prodotto cartesiano dei loro valori di test; gli assi non
selezionati restano alla baseline. Ogni variante e' *completamente* specificata
(tutti gli assi hanno un valore), cosi' le varianti sono direttamente
confrontabili. L'ordine 0 (tutte le baseline) e' la variante di riferimento.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Dict, List

from . import bounds as bounds_mod
from .study_spec import StudySpec
from .yaml_builder import build_document


def _fmt(value: Any) -> str:
    """Formatta un valore per il nome file: niente zeri di coda inutili."""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return repr(value).rstrip("0").rstrip(".")
    return str(value)


@dataclass(frozen=True)
class Variant:
    name: str
    order: int
    moved: List[str]              # nomi degli assi mossi rispetto alla baseline
    values: Dict[str, float]      # nome asse -> valore (tutti gli assi)

    def overrides(self, spec: StudySpec) -> Dict[str, float]:
        """path YAML -> valore clampato ai bounds engine, per ogni asse."""
        out: Dict[str, float] = {}
        for ax in spec.axes:
            out[ax.path] = bounds_mod.clamp(ax.path, self.values[ax.name])
        return out

    def to_document(self, spec: StudySpec) -> Dict[str, Any]:
        base = dict(spec.base)
        base.setdefault("stream_id", "stream")  # l'engine lo richiede
        return build_document(
            base,
            self.overrides(spec),
            title=f"{spec.study_id} :: {self.name}",
            seed=spec.seed,
            duration=spec.duration,
        )


def _name(order: int, moved_values: Dict[str, float]) -> str:
    if not moved_values:
        return "o0__baseline"
    parts = [f"{ax}={_fmt(v)}" for ax, v in sorted(moved_values.items())]
    return f"o{order}__" + "__".join(parts)


def generate_variants(spec: StudySpec) -> List[Variant]:
    """Enumera le varianti per gli ordini richiesti, deduplicando per valori."""
    baseline = {ax.name: ax.baseline for ax in spec.axes}
    seen_vectors: set = set()
    variants: List[Variant] = []

    for order in sorted(set(spec.orders)):
        if order == 0:
            vec = tuple(sorted(baseline.items()))
            if vec not in seen_vectors:
                seen_vectors.add(vec)
                variants.append(Variant("o0__baseline", 0, [], dict(baseline)))
            continue

        for combo in itertools.combinations(spec.axes, order):
            value_lists = [ax.values for ax in combo]
            for picked in itertools.product(*value_lists):
                values = dict(baseline)
                moved_values: Dict[str, float] = {}
                for ax, val in zip(combo, picked):
                    values[ax.name] = val
                    moved_values[ax.name] = val
                vec = tuple(sorted(values.items()))
                if vec in seen_vectors:
                    continue
                seen_vectors.add(vec)
                variants.append(
                    Variant(
                        name=_name(order, moved_values),
                        order=order,
                        moved=[ax.name for ax in combo],
                        values=values,
                    )
                )
    return variants
