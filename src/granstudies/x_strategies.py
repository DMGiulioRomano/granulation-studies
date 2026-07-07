"""Strategy di X: la sequenza dei *tempi* dei breakpoint, normalizzati in [0, 1].

Registry gemello di ``value_generators.GENERATORS``, ma per l'asse X. Le tre
cose restano ortogonali: il generatore di Y (``values``/``ramp``/``rand``)
decide i valori, la strategy di X decide i tempi, ``interpolation`` la curva
tra i breakpoint. Attenzione alle due "linear": la strategy-X ``linear``
(tempi equispaziati) non c'entra con l'interpolation ``linear`` (retta tra due
punti) — si puo' avere una X accelerando con interpolation step.

Consumata solo dal processo ``stack``: lo sweep possiede la sua X via
plateau/transition e non passa di qui. Aggiungere una strategy = una funzione
pura + una riga in ``X_STRATEGIES``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


def linear(n: int) -> List[float]:
    """``n`` tempi equispaziati in ``[0, 1]``: ``t_i = i / (n - 1)``.

    E' il default quando l'asse non dichiara una strategy-X: la Y possiede
    ``n`` e i breakpoint si distribuiscono uniformi. Caso ``n == 1``: un solo
    punto a ``0.0``.
    """
    if n < 1:
        raise ValueError(f"linear: n deve essere >= 1 (ricevuto {n})")
    if n == 1:
        return [0.0]
    return [round(i / (n - 1), 9) for i in range(n)]


X_STRATEGIES: Dict[str, Callable[..., List[float]]] = {"linear": linear}


def resolve_x(cfg: Dict[str, Any] | None, n: int) -> List[float]:
    """Risolve i tempi dei breakpoint scegliendo la strategy dalla chiave.

    ``cfg`` e' il blocco X di un asse (``{nome_strategy: params}``): assente o
    vuoto ricade sul default ``linear`` senza parametri. Deve esserci al
    massimo una chiave, e deve essere una strategy registrata.
    """
    if not cfg:
        return linear(n)
    if len(cfg) != 1:
        opts = ", ".join(X_STRATEGIES)
        raise ValueError(
            f"strategy-X: serve esattamente una chiave tra {{{opts}}}, "
            f"trovate {sorted(cfg)}."
        )
    (name, params), = cfg.items()
    if name not in X_STRATEGIES:
        opts = ", ".join(X_STRATEGIES)
        raise ValueError(f"strategy-X sconosciuta '{name}': usa una tra {{{opts}}}.")
    return X_STRATEGIES[name](n=n, **(params or {}))
