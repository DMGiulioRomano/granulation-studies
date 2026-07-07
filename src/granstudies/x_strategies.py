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

import random
from typing import Any, Callable, Dict, List

from .value_generators import Threshold, _threshold_at

# Tetto anti-runaway: una banda di frequenza troppo alta (o una durata enorme)
# genererebbe milioni di breakpoint. Meglio un errore esplicito di un file YAML
# ingestibile: e' un errore di configurazione, non un caso d'uso.
MAX_POINTS = 10_000


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


def rand(
    duration: float,
    cps: Dict[str, Threshold],
    seed: int = 0,
) -> List[float]:
    """Tempi di breakpoint generati da una *frequenza di generazione* (rspline).

    La X possiede ``n``: non si dichiara, emerge dalla frequenza integrata
    sulla durata (``n ~ int f(t) dt``). Meccanica: dal punto corrente ``t`` si
    pesca ``f`` nella banda ``[base(t), base(t) + range(t)]`` (Hz sulla durata
    reale in secondi); il punto successivo cade a ``t + 1/f``; si ripete finche'
    si supera la fine. I tempi sono poi normalizzati in ``[0, 1]``.

    ``base``/``range`` sono inviluppi mobili nelle stesse forme della banda di
    Y-rand (scalare | ``[a, b]`` | ``[[t, v], ...]`` | ``{type, points}``),
    valutati via ``_threshold_at`` (modulo condiviso Y-rand/X-rand).
    Deterministico via ``seed``. Guardie: frequenza non positiva -> errore
    (passo infinito, nessun punto); piu' di ``MAX_POINTS`` punti -> errore.
    """
    if duration <= 0:
        raise ValueError(f"rand-X: duration deve essere > 0 (ricevuta {duration})")
    if "base" not in cps:
        raise ValueError("rand-X: 'cps.base' e' obbligatorio (frequenza in Hz).")
    base = cps["base"]
    spread = cps.get("range", 0.0)
    rng = random.Random(seed)
    times: List[float] = [0.0]
    t = 0.0  # secondi reali
    while True:
        frac = t / duration
        lo = _threshold_at(base, frac)
        hi = lo + _threshold_at(spread, frac)
        if lo > hi:
            raise ValueError(f"rand-X: range negativo a t={t:.3f}s (banda [{lo}, {hi}]).")
        f = rng.uniform(lo, hi)
        if f <= 0:
            raise ValueError(
                f"rand-X: frequenza non positiva ({f}) a t={t:.3f}s — "
                "la banda cps deve restare > 0."
            )
        t += 1.0 / f
        # Bordo con tolleranza: l'accumulo float puo' fermarsi un epsilon prima
        # della fine (es. 50 passi da 0.2 -> 9.999...8) e produrre un punto
        # spurio a ~1.0. Un punto sul bordo esatto non e' comunque un plateau.
        if t / duration >= 1.0 - 1e-9:
            return times
        times.append(round(t / duration, 9))
        if len(times) > MAX_POINTS:
            raise ValueError(
                f"rand-X: oltre {MAX_POINTS} breakpoint — banda cps troppo alta "
                f"per duration={duration}s."
            )


X_STRATEGIES: Dict[str, Callable[..., List[float]]] = {"linear": linear, "rand": rand}

# Strategy in cui e' la X a possedere ``n`` (i tempi emergono, non si contano):
# non risolvibili con un ``n`` esterno via ``resolve_x``.
_X_OWNS_N = frozenset({"rand"})


def x_owns_n(cfg: Dict[str, Any] | None) -> bool:
    """True se la strategy-X configurata possiede ``n`` (es. ``rand``).

    Decide il verso dell'accoppiamento in assemblaggio: X possiede n -> la Y
    viene campionata ai tempi generati; altrimenti n viene dalla Y e la X
    distribuisce i tempi.
    """
    if not cfg or len(cfg) != 1:
        return False
    (name,), = (tuple(cfg),)
    return name in _X_OWNS_N


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
    if name in _X_OWNS_N:
        raise ValueError(
            f"strategy-X '{name}' possiede n (i tempi emergono dalla frequenza): "
            "non risolvibile con un n dalla Y."
        )
    return X_STRATEGIES[name](n=n, **(params or {}))
