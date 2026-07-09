"""Strategy di X: la sequenza dei *tempi* dei breakpoint, normalizzati in [0, 1].

Due sole forme, riconosciute dalla *presenza* nel blocco ``stack:`` (niente piu'
nome-strategy): l'asse **assente** dal blocco usa ``linear`` (tempi equispaziati,
la Y possiede ``n``); l'asse **presente** con una banda ``base``/``range`` usa
``walk`` (i tempi emergono dalla frequenza, la X possiede ``n``). Le tre cose
restano ortogonali: il generatore di Y decide i valori, la strategy di X i tempi,
``interpolation`` la curva tra i breakpoint. Attenzione alle due "linear": la
strategy-X ``linear`` (tempi equispaziati) non c'entra con l'interpolation
``linear`` (retta tra due punti) — si puo' avere una X accelerando con
interpolation step.

Consumata solo dal processo ``stack``: lo sweep possiede la sua X via
plateau/transition e non passa di qui.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .value_generators import Threshold, _band_sampler

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


def walk(
    duration: float,
    base: Threshold,
    range: Threshold = 0.0,
    seed: int = 0,
    distribution: str = "uniform",
    drift: Dict[str, Any] | None = None,
) -> List[float]:
    """Tempi di breakpoint generati da una *frequenza di generazione* (camminata).

    La X possiede ``n``: non si dichiara, emerge dalla frequenza integrata
    sulla durata (``n ~ int f(t) dt``). Meccanica: dal punto corrente ``t`` si
    pesca ``f`` nella banda ``[base(t), base(t) + range(t)]`` (Hz sulla durata
    reale in secondi); il punto successivo cade a ``t + 1/f``; si ripete finche'
    si supera la fine. I tempi sono poi normalizzati in ``[0, 1]``.

    ``base``/``range`` sono inviluppi mobili nelle stesse forme della banda di Y
    (scalare | ``[a, b]`` | ``[[t, v], ...]`` | ``{type, points, curve}``);
    il pescaggio della frequenza e' lo stesso della banda di Y
    (``_band_sampler``, modulo condiviso X/Y): ``distribution`` governa come si
    pesca (``uniform`` | ``gaussian``), ``drift`` la rende un random walk
    correlato — ``step`` letto sul tempo reale normalizzato, il dominio di
    ``base``/``range`` in questo registro. ``range`` assente (0) = banda
    collassata: la camminata segue ``base`` deterministicamente (il ``seed``
    non influisce sui tempi). Deterministico via ``seed``. Guardie: frequenza
    non positiva -> errore (passo infinito, nessun punto); piu' di
    ``MAX_POINTS`` punti -> errore.
    """
    if duration <= 0:
        raise ValueError(f"walk-X: duration deve essere > 0 (ricevuta {duration})")
    sample = _band_sampler(base, range, seed, distribution, drift, "walk-X")
    times: List[float] = [0.0]
    t = 0.0  # secondi reali
    while True:
        f = sample(t / duration)
        if f <= 0:
            raise ValueError(
                f"walk-X: frequenza non positiva ({f}) a t={t:.3f}s — "
                "la banda base/range deve restare > 0."
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
                f"walk-X: oltre {MAX_POINTS} breakpoint — banda base troppo alta "
                f"per duration={duration}s."
            )


def x_owns_n(cfg: Dict[str, Any] | None) -> bool:
    """True se l'asse ha una camminata-X nel blocco ``stack:`` (possiede ``n``).

    Nel modello piatto non c'e' piu' un nome-strategy: la *presenza* di una entry
    con ``base`` sotto ``stack.<asse>`` marca la camminata (la X possiede n, i
    tempi emergono dalla frequenza). Assenza dal blocco = linear (n dalla Y).
    """
    return isinstance(cfg, dict) and "base" in cfg


def resolve_x(cfg: Dict[str, Any] | None, n: int) -> List[float]:
    """Risolve i tempi equispaziati (``linear``) quando la Y possiede ``n``.

    Nel modello piatto ``linear`` e' l'assenza dell'asse dal blocco ``stack:``:
    ``cfg`` assente/vuoto -> ``linear(n)``. Una entry con ``base`` e' invece una
    camminata (possiede n): non risolvibile con un ``n`` esterno -> errore.
    """
    if not cfg:
        return linear(n)
    if x_owns_n(cfg):
        raise ValueError(
            "strategy-X: la camminata (banda 'base') possiede n (i tempi emergono "
            "dalla frequenza): non risolvibile con un n dalla Y."
        )
    raise ValueError(
        f"strategy-X: entry stack senza 'base' {sorted(cfg)} — una entry sotto "
        "'stack:' e' una camminata e richiede 'base' (frequenza in Hz)."
    )
