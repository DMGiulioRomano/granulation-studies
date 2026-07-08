"""Generatori di valori d'asse.

Un asse di uno studio elenca i valori di test. Il generatore si riconosce dalla
*forma* delle chiavi (non piu' da un nome-wrapper): ``values`` (lista esplicita),
``ramp`` (griglia aritmetica) o ``base`` (la banda ``[base, base+range]``, piatta
sull'asse). ``y_generator`` estrae la chiave canonica e i parametri; ogni
generatore e' una funzione pura ``**params -> List[float]`` (niente stato).
"""
from __future__ import annotations

import math
import random
import zlib
from typing import Any, Dict, List, Sequence, Union

Threshold = Union[float, Sequence[float], Dict[str, Any]]

# La banda ha un parametro YAML che si chiama ``range``: alias del builtin per
# l'uso interno.
_range = range


def stable_seed(key: str) -> int:
    """Seed deterministico da una chiave testuale (es. l'id di uno stream).

    ``hash()`` di Python e' salato per processo (PYTHONHASHSEED): inutilizzabile
    per il ciclo rigenera-e-confronta. CRC32 e' stabile tra run e macchine, e
    resta stabile al riordino/rinomina degli altri stream.
    """
    return zlib.crc32(key.encode("utf-8"))


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


def _interp_breakpoints(
    pts: Sequence[Sequence[float]], frac: float, kind: str = "linear", curve: float = 1.0
) -> float:
    """Soglia su ``[[t, v], ...]`` (t in ``[0, 1]``) al punto ``frac``, con hold
    fuori dai bordi. ``kind``: ``linear`` (rampa tra i punti) o ``step`` (tieni
    il valore sinistro, salta al breakpoint).

    ``curve`` piega la frazione locale del segmento prima di interpolare
    (``u' = u^k``): ``1`` = lineare (default), ``> 1`` parte lento e accelera in
    coda, ``< 1`` parte ripido e si appiattisce. Agisce solo sulla rampa
    (``kind == linear``): con ``step`` non c'e' rampa da piegare. Un ``curve``
    non positivo e' un errore di configurazione (potenza degenere)."""
    if curve <= 0:
        raise ValueError(f"curve deve essere > 0 (ricevuto {curve}).")
    pts = sorted(pts, key=lambda p: p[0])
    if frac <= pts[0][0]:
        return pts[0][1]
    if frac >= pts[-1][0]:
        return pts[-1][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= frac <= t1:
            if kind == "step":
                return v0
            if t1 == t0:
                return v0
            u = (frac - t0) / (t1 - t0)
            if curve != 1.0:
                u = u ** curve
            return v0 + (v1 - v0) * u
    return pts[-1][1]  # irraggiungibile: frac e' tra primo e ultimo t


def _threshold_at(spec: Threshold, frac: float) -> float:
    """Soglia (base o range) al punto ``frac`` in ``[0, 1]`` della sequenza.

    E' un envelope di secondo ordine (una banda che genera valori). Forme:
    scalare -> costante; ``[a, b]`` (due scalari) -> lineare ``a -> b``;
    ``[[t, v], ...]`` -> breakpoint temporizzati (linear); ``{type, points, curve}``
    -> breakpoint con ``type`` d'interpolazione esplicito (``linear`` | ``step``)
    ed eventuale ``curve`` (piega non lineare ``u^k`` del segmento). ``curve`` con
    ``type: step`` e' un errore: step non ha rampa da piegare.
    """
    if isinstance(spec, dict):
        kind = spec.get("type", "linear")
        curve = spec.get("curve", 1.0)
        if kind == "step" and curve != 1.0:
            raise ValueError(
                "curve non ha effetto con 'type: step' (nessuna rampa da piegare): "
                "usa 'type: linear' o togli 'curve'."
            )
        return _interp_breakpoints(spec["points"], frac, kind, curve)
    if not isinstance(spec, (list, tuple)):
        return spec
    if all(isinstance(p, (list, tuple)) for p in spec):
        return _interp_breakpoints(spec, frac)
    a, b = spec  # shorthand [a, b] == [[0, a], [1, b]]
    return a + (b - a) * frac


def _band_at(base: Threshold, spread: Threshold, frac: float, where: str) -> tuple:
    """Banda ``[lo, hi]`` al punto ``frac``: ``lo = base(frac)``,
    ``hi = lo + range(frac)``. Stessa semantica della banda di X."""
    lo = _threshold_at(base, frac)
    hi = lo + _threshold_at(spread, frac)
    if hi < lo:
        raise ValueError(f"{where}: range negativo a frac={frac} (banda [{lo}, {hi}])")
    return lo, hi


def band(n: int, base: Threshold, range: Threshold = 0.0, seed: int = 0) -> List[float]:
    """``n`` valori casuali entro una banda ``[base, base + range]`` mobile.

    ``base``/``range`` scalari = banda fissa; ``[a, b]`` = banda che scorre/si
    allarga linearmente lungo la sequenza. Il valore al passo ``i`` e' estratto
    uniformemente nella banda a quel punto; ``range`` omesso (0) = banda
    collassata, la sequenza segue ``base`` deterministicamente. Deterministico
    via ``seed`` (stesso seed -> stessa sequenza), requisito del ciclo
    rigenera-e-confronta.
    """
    if n < 1:
        raise ValueError(f"band: n deve essere >= 1 (ricevuto {n})")
    rng = random.Random(seed)
    out: List[float] = []
    for i in _range(n):
        frac = i / (n - 1) if n > 1 else 0.0
        lo, hi = _band_at(base, range, frac, "band")
        out.append(round(rng.uniform(lo, hi), 9))
    return out


def band_at(
    fracs: Sequence[float], base: Threshold, range: Threshold = 0.0, seed: int = 0
) -> List[float]:
    """Un valore casuale nella banda ``[base, base + range]`` per ogni ``frac``.

    Variante di ``band`` per il coupling con la X-walk (stack): quando la X
    possiede ``n``, la banda va campionata al tempo *reale* ``t_i`` di ogni
    breakpoint, non all'indice ``i/(n-1)``. La Y non possiede ``n``: pesca un
    valore per ogni punto che la X ha creato. Deterministico via ``seed``.
    """
    if not fracs:
        raise ValueError("band_at: serve almeno un frac (lista vuota).")
    rng = random.Random(seed)
    out: List[float] = []
    for frac in fracs:
        lo, hi = _band_at(base, range, frac, "band_at")
        out.append(round(rng.uniform(lo, hi), 9))
    return out


# Le chiavi che marcano il generatore Y di un asse (mutuamente esclusive): la
# lista esplicita ``values``, la griglia ``ramp``, e ``base`` (la banda piatta —
# non piu' un wrapper ``rand:``, ma la coppia base/range direttamente sull'asse).
Y_GENERATOR_KEYS = frozenset({"values", "ramp", "base"})

# Chiavi che accompagnano ``base`` nella banda piatta (viaggiano con essa).
_BAND_KEYS = frozenset({"base", "range", "n", "seed"})


def y_generator(cfg: Dict[str, Any]) -> tuple:
    """(chiave canonica, params) del generatore Y di un asse piatto.

    Riconosce il generatore dalla *forma*: esattamente una tra ``values``,
    ``ramp``, ``base``. La chiave canonica restituita e' ``values`` | ``ramp`` |
    ``band``; per la banda raccoglie ``base``/``range``/``n``/``seed`` (le chiavi
    piatte dell'asse) in un dict. Zero o piu' di un marcatore e' errore.
    """
    if "rand" in cfg:
        raise ValueError(
            "il wrapper 'rand:' non esiste piu': dichiara la banda piatta "
            "(base/range/n/seed direttamente sull'asse). Es. 'rand: {n, base, "
            "range}' -> 'n: ...', 'base: ...', 'range: ...'."
        )
    markers = [k for k in cfg if k in Y_GENERATOR_KEYS]
    if len(markers) != 1:
        opts = ", ".join(sorted(Y_GENERATOR_KEYS))
        raise ValueError(
            f"asse: serve esattamente una chiave-generatore tra {{{opts}}}, "
            f"trovate {sorted(markers) or 'nessuna'}."
        )
    marker = markers[0]
    if marker == "values":
        return "values", list(cfg["values"])
    if marker == "ramp":
        return "ramp", dict(cfg["ramp"])
    return "band", {k: cfg[k] for k in _BAND_KEYS if k in cfg}


def resolve(cfg: Dict[str, Any]) -> List[float]:
    """Risolve la lista di valori di un asse scegliendo il generatore dalla forma.

    Le chiavi-generatore sono ``values`` (lista esplicita), ``ramp`` (griglia) e
    ``base`` (banda piatta). Deve essercene esattamente una. La banda richiede
    ``n`` quando e' la Y a possedere il conteggio (fuori dal coupling con X-walk).
    """
    key, params = y_generator(cfg)
    if key == "values":
        return params
    if key == "ramp":
        return ramp(**params)
    if "n" not in params:
        raise ValueError(
            "banda: 'n' obbligatorio quando la Y possiede il conteggio "
            "(omesso solo con la X-walk nel blocco 'stack:')."
        )
    return band(**params)
