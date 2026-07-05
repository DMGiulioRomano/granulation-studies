"""Generatori di valori d'asse (strategy pattern).

Un asse di uno studio elenca i valori di test. Oltre alla lista esplicita
(``values: [...]``) si puo' generare la sequenza con una *strategia*: la chiave
YAML e' il nome della strategia (``ramp: {...}``) e ``GENERATORS`` fa da
registry ``nome -> funzione``. Ogni strategia e' una funzione pura
``**params -> List[float]``: niente stato, nessun factory: aggiungere una
strategia = una funzione + una riga in ``GENERATORS``.
"""
from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List, Sequence, Union

Threshold = Union[float, Sequence[float]]


def ramp(start: float, stop: float, step: float) -> List[float]:
    """Rampa aritmetica da ``start`` a ``stop`` a passo ``step`` (``> 0``).

    Direzione dedotta da ``start``/``stop`` (discendente se ``start > stop``).
    Conteggio intero anti-drift: il numero di gradini si ricava con
    ``floor(round(distanza/step))`` cosi' un ``stop`` che cade sulla griglia e'
    incluso senza deriva float, e uno che non ci cade non viene mai oltrepassato.
    """
    if step <= 0:
        raise ValueError(f"ramp: step deve essere > 0 (ricevuto {step})")
    n = math.floor(round(abs(stop - start) / step, 9))
    sign = 1.0 if stop >= start else -1.0
    return [round(start + sign * step * i, 9) for i in range(n + 1)]


def _threshold_at(spec: Threshold, frac: float) -> float:
    """Soglia (min o max) al punto ``frac`` in ``[0, 1]`` della sequenza.

    Scalare -> banda costante; ``[a, b]`` -> interpolazione lineare ``a -> b``,
    cioe' la soglia varia nel tempo lungo la griglia condivisa.
    """
    if isinstance(spec, (list, tuple)):
        a, b = spec
        return a + (b - a) * frac
    return spec


def rand(n: int, min: Threshold, max: Threshold, seed: int = 0) -> List[float]:
    """``n`` valori casuali entro una banda ``[min, max]`` eventualmente mobile.

    ``min``/``max`` scalari = banda fissa; ``[a, b]`` = banda che scorre/si
    allarga linearmente lungo la sequenza. Il valore al passo ``i`` e' estratto
    uniformemente nella banda a quel punto. Deterministico via ``seed`` (stesso
    seed -> stessa sequenza), requisito del ciclo rigenera-e-confronta.
    """
    if n < 1:
        raise ValueError(f"rand: n deve essere >= 1 (ricevuto {n})")
    rng = random.Random(seed)
    out: List[float] = []
    for i in range(n):
        frac = i / (n - 1) if n > 1 else 0.0
        lo = _threshold_at(min, frac)
        hi = _threshold_at(max, frac)
        if lo > hi:
            raise ValueError(f"rand: min ({lo}) > max ({hi}) al passo {i}")
        out.append(round(rng.uniform(lo, hi), 9))
    return out


GENERATORS: Dict[str, Callable[..., List[float]]] = {"ramp": ramp, "rand": rand}


def resolve(cfg: Dict[str, Any]) -> List[float]:
    """Risolve la lista di valori di un asse scegliendo la strategia dalla chiave.

    Le chiavi-generatore sono ``values`` (lista esplicita) e i nomi in
    ``GENERATORS`` (``ramp``, ...). Deve essercene esattamente una: zero o piu'
    di una e' un errore di configurazione.
    """
    keys = [k for k in cfg if k == "values" or k in GENERATORS]
    if len(keys) != 1:
        opts = ", ".join(["values", *GENERATORS])
        raise ValueError(
            f"asse: serve esattamente una chiave-generatore tra {{{opts}}}, "
            f"trovate {sorted(keys) or 'nessuna'}."
        )
    key = keys[0]
    if key == "values":
        return list(cfg["values"])
    return GENERATORS[key](**cfg[key])
