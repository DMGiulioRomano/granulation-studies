"""Modalita' ``envelope`` dello sweep: stream dinamici a plateau in cascata.

A differenza dello sweep ``discrete`` (un file statico per combinazione), la
modalita' envelope produce **un** file per combinazione di assi, in cui i
parametri attraversano tutte le permutazioni dei valori tramite breakpoint
temporali sincronizzati. Ogni combinazione occupa un *plateau* (ascolto stabile)
e si raggiunge la successiva via una *transition* lineare.

I tempi sono normalizzati in ``[0, 1]`` (``time_mode: normalized`` sullo stream);
la ``duration`` reale dello stream e' calcolata da ``plateau``/``transition``.

Vedi issue #2 (granulation-studies) per le decisioni di design.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Dict, List

from . import bounds as bounds_mod
from .study_spec import Axis, StudySpec


def envelope_breakpoints(
    values: List[float], plateau: float, transition: float, *, step: bool = False
) -> List[List[float]]:
    """Breakpoint normalizzati ``[[t, v], ...]`` per una sequenza di plateau.

    Con ``step=True`` (envelope ``type: step``) plateau e transizione collassano:
    l'engine tiene ogni valore fino al breakpoint successivo e poi salta netto,
    quindi il doppio punto per plateau e' ridondante. Si emette **un solo punto
    per valore**, equispaziato in ``[0, 1]`` (``t_i = i / N``); l'ultimo valore
    e' tenuto fino a fine stream dall'engine. La durata reale (un ``transition``
    per gradino) e' governata da ``EnvelopeVariant.duration``.

    Per ``N = len(values)`` plateau, ogni plateau occupa ``W_plateau`` e ogni
    transizione ``W_transition`` della durata totale normalizzata::

        total        = N * plateau + (N - 1) * transition
        W_plateau    = plateau / total
        W_transition = transition / total

    Il plateau ``i`` (0-indexed) va da ``t_start = i * (W_plateau + W_transition)``
    a ``t_end = t_start + W_plateau``; la transizione verso il plateau successivo
    avviene nel gap tra ``t_end`` e il ``t_start`` del prossimo (interpolazione
    lineare a carico dell'engine).

    Caso ``N == 1``: unico plateau costante ``[[0, v], [1, v]]``.
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [[0.0, values[0]], [1.0, values[0]]]

    if step:
        return [[round(i / n, 6), v] for i, v in enumerate(values)]

    total = n * plateau + (n - 1) * transition
    w_plateau = plateau / total
    w_transition = transition / total
    step = w_plateau + w_transition

    points: List[List[float]] = []
    for i, v in enumerate(values):
        t_start = i * step
        t_end = t_start + w_plateau
        points.append([round(t_start, 6), v])
        points.append([round(t_end, 6), v])
    # L'ultimo t_end deve cadere esattamente su 1.0 (no deriva float).
    points[-1][0] = 1.0
    points[0][0] = 0.0
    return points


def cartesian_combinations(axes: List[Axis]) -> List[Dict[str, float]]:
    """Prodotto cartesiano lessicografico dei valori degli assi.

    Restituisce la lista ordinata di combinazioni ``{nome_asse: valore}``: il
    primo asse e' fisso per un blocco di ``N`` valori, poi cambia (come in un
    contatore posizionale). Per 2 assi da 3 valori -> 9 combinazioni.
    """
    value_lists = [ax.values for ax in axes]
    combos: List[Dict[str, float]] = []
    for picked in itertools.product(*value_lists):
        combos.append({ax.name: val for ax, val in zip(axes, picked)})
    return combos


@dataclass(frozen=True)
class EnvelopeVariant:
    """Una combinazione di assi mossi insieme tramite envelope sincronizzati.

    A differenza di ``Variant`` (statica, ``values: Dict[str, float]``), qui i
    valori sono una *sequenza* di combinazioni (i plateau) e gli assi mossi
    diventano envelope a breakpoint, non scalari.
    """

    name: str
    order: int
    moved: List[str]                          # nomi degli assi mossi
    combinations: List[Dict[str, float]]      # plateau in ordine lessicografico

    def overrides(self, spec: StudySpec) -> Dict[str, Any]:
        """path YAML -> envelope (assi mossi) o scalare baseline (assi fermi).

        Gli assi mossi condividono la stessa griglia temporale (breakpoint
        sincronizzati): in ogni plateau assumono insieme i valori della
        combinazione corrente. Gli assi fermi restano scalari al baseline.
        Tutti i valori sono clampati ai bounds engine.
        """
        moved_set = set(self.moved)
        step = spec.interpolation == "step"
        out: Dict[str, Any] = {}
        for ax in spec.axes:
            if ax.name in moved_set:
                seq = [
                    bounds_mod.clamp(ax.path, combo[ax.name])
                    for combo in self.combinations
                ]
                out[ax.path] = envelope_breakpoints(
                    seq, spec.plateau, spec.transition, step=step
                )
            else:
                out[ax.path] = bounds_mod.clamp(ax.path, ax.baseline)
        return out

    def duration(self, spec: StudySpec) -> float:
        """Durata reale dello stream.

        Envelope a plateau: ``N*plateau + (N-1)*transition``. In modalita' step
        (``interpolation: step``) plateau/transizione collassano in un unico
        gradino per valore: ``N*transition``.
        """
        n = len(self.combinations)
        if n == 0:
            return 0.0
        if spec.interpolation == "step":
            return n * spec.transition
        return n * spec.plateau + (n - 1) * spec.transition


def _name(order: int, moved: List[str]) -> str:
    return f"e{order}__" + "__".join(moved)


def generate_envelope_variants(spec: StudySpec) -> List[EnvelopeVariant]:
    """Enumera gli ``EnvelopeVariant`` per gli ordini richiesti.

    Un file per ogni combinazione di ``k`` assi (``k`` = ordine), con i loro
    valori attraversati nel prodotto cartesiano lessicografico. L'ordine 0 (tutte
    le baseline) non produce envelope (nessun asse mosso).
    """
    variants: List[EnvelopeVariant] = []

    # Orderings espliciti: generano varianti indipendentemente da orders.
    explicit_keys: set = set()
    for ordering in spec.orderings:
        axes_ordered = [spec.axis(n) for n in ordering]
        moved = [ax.name for ax in axes_ordered]
        key = tuple(moved)
        explicit_keys.add(key)
        variants.append(
            EnvelopeVariant(
                name=_name(len(moved), moved),
                order=len(moved),
                moved=moved,
                combinations=cartesian_combinations(axes_ordered),
            )
        )

    for order in sorted(set(spec.orders)):
        if order <= 0:
            continue
        for combo in itertools.combinations(spec.axes, order):
            moved = [ax.name for ax in combo]
            if tuple(moved) in explicit_keys:
                continue  # ponytail: già emessa come ordering esplicito
            combinations = cartesian_combinations(list(combo))
            variants.append(
                EnvelopeVariant(
                    name=_name(order, moved),
                    order=order,
                    moved=moved,
                    combinations=combinations,
                )
            )
    return variants
