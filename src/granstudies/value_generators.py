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
from typing import Any, Callable, Dict, List


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


GENERATORS: Dict[str, Callable[..., List[float]]] = {"ramp": ramp}


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
