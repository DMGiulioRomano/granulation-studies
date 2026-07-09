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


# Tetto anti-runaway per la rampa a passo Env: un passo che collassa verso lo
# zero genererebbe una griglia enorme. Stessa filosofia di MAX_POINTS in
# x_strategies (errore di configurazione, non caso d'uso).
MAX_RAMP_POINTS = 10_000


def ramp(start: float, stop: float, step: Threshold) -> List[float]:
    """Rampa aritmetica da ``start`` a ``stop`` a passo ``step``.

    Direzione dedotta da ``start``/``stop`` (discendente se ``start > stop``).

    ``step`` scalare (``> 0``): griglia a passo costante, conteggio intero
    anti-drift — il numero di gradini si ricava con ``floor(round(distanza/step))``
    cosi' un ``stop`` che cade sulla griglia e' incluso senza deriva float, e uno
    che non ci cade non viene mai oltrepassato.

    ``step`` Env (le forme di ``_threshold_at``): passo mobile — accelerando
    (``[10, 1]``: i passi si stringono) o ritardando. ``step`` e' funzione del
    *progresso in valore* ``|v - start| / |stop - start|`` (l'indice non e' noto
    a priori); ``n`` emerge dall'integrazione. Un passo non positivo in
    qualunque punto e' errore (loop infinito); tetto ``MAX_RAMP_POINTS``.
    """
    if isinstance(step, (int, float)):
        if step <= 0:
            raise ValueError(f"ramp: step deve essere > 0 (ricevuto {step})")
        n = math.floor(round(abs(stop - start) / step, 9))
        sign = 1.0 if stop >= start else -1.0
        return [round(start + sign * step * i, 9) for i in range(n + 1)]
    span = abs(stop - start)
    if span == 0:
        return [round(start, 9)]
    sign = 1.0 if stop >= start else -1.0
    out: List[float] = [round(start, 9)]
    v = float(start)
    while True:
        frac = abs(v - start) / span
        s = _threshold_at(step, frac)
        if s <= 0:
            raise ValueError(
                f"ramp: step non positivo ({s}) al progresso {frac:.3f} — "
                "l'Env di step deve restare > 0."
            )
        v += sign * s
        if abs(v - start) > span + 1e-9:
            return out
        out.append(round(v, 9))
        if len(out) > MAX_RAMP_POINTS:
            raise ValueError(
                f"ramp: oltre {MAX_RAMP_POINTS} punti — l'Env di step e' "
                "troppo piccolo per la distanza start/stop."
            )


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


# Le distribuzioni di pescaggio dentro la banda (issue #16). ``uniform`` e' il
# comportamento storico; ``gaussian`` concentra sul centro banda.
_DISTRIBUTIONS = frozenset({"uniform", "gaussian"})


def _draw(rng: random.Random, lo: float, hi: float, distribution: str) -> float:
    """Un pescaggio dentro ``[lo, hi]`` secondo ``distribution``.

    ``uniform``: come sempre. ``gaussian``: media al centro banda, sigma
    ``(hi - lo) / 6`` (i bordi cadono a 3 sigma), clamp ai bordi — la coda
    fuori banda (~0.3%) si appiattisce sull'estremo invece di uscire.
    """
    if distribution == "uniform":
        return rng.uniform(lo, hi)
    mu = (lo + hi) / 2.0
    sigma = (hi - lo) / 6.0
    if sigma == 0:
        return mu
    return min(max(rng.gauss(mu, sigma), lo), hi)


def _check_distribution(distribution: str, where: str) -> None:
    if distribution not in _DISTRIBUTIONS:
        opts = " | ".join(sorted(_DISTRIBUTIONS))
        raise ValueError(
            f"{where}: distribution '{distribution}' non ammessa ({opts})."
        )


def band(
    n: int,
    base: Threshold,
    range: Threshold = 0.0,
    seed: int = 0,
    distribution: str = "uniform",
) -> List[float]:
    """``n`` valori casuali entro una banda ``[base, base + range]`` mobile.

    ``base``/``range`` scalari = banda fissa; ``[a, b]`` = banda che scorre/si
    allarga linearmente lungo la sequenza. Il valore al passo ``i`` e' estratto
    nella banda a quel punto secondo ``distribution`` (``uniform`` |
    ``gaussian``, vedi ``_draw``); ``range`` omesso (0) = banda collassata, la
    sequenza segue ``base`` deterministicamente. Deterministico via ``seed``
    (stesso seed -> stessa sequenza), requisito del ciclo rigenera-e-confronta.
    """
    if n < 1:
        raise ValueError(f"band: n deve essere >= 1 (ricevuto {n})")
    _check_distribution(distribution, "band")
    rng = random.Random(seed)
    out: List[float] = []
    for i in _range(n):
        frac = i / (n - 1) if n > 1 else 0.0
        lo, hi = _band_at(base, range, frac, "band")
        out.append(round(_draw(rng, lo, hi, distribution), 9))
    return out


def band_at(
    fracs: Sequence[float],
    base: Threshold,
    range: Threshold = 0.0,
    seed: int = 0,
    distribution: str = "uniform",
) -> List[float]:
    """Un valore casuale nella banda ``[base, base + range]`` per ogni ``frac``.

    Variante di ``band`` per il coupling con la X-walk (stack): quando la X
    possiede ``n``, la banda va campionata al tempo *reale* ``t_i`` di ogni
    breakpoint, non all'indice ``i/(n-1)``. La Y non possiede ``n``: pesca un
    valore per ogni punto che la X ha creato. Deterministico via ``seed``;
    ``distribution`` come in ``band``.
    """
    if not fracs:
        raise ValueError("band_at: serve almeno un frac (lista vuota).")
    _check_distribution(distribution, "band_at")
    rng = random.Random(seed)
    out: List[float] = []
    for frac in fracs:
        lo, hi = _band_at(base, range, frac, "band_at")
        out.append(round(_draw(rng, lo, hi, distribution), 9))
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


# --- generatori annidati: un nodo-generatore dentro un Env si compila in ---------
# --- breakpoint (docs/plans/nested-generators.md) ---------------------------------

# Guardia di profondita' della ricorsione: oltre 3 livelli le config sono gia'
# illeggibili, 8 e' puro margine anti-degenerazione (alias YAML ricorsivi).
MAX_ENV_DEPTH = 8

# Chiavi ammesse accanto al marcatore in un nodo: la curva del mini-asse.
_NODE_SHAPE_KEYS = frozenset({"type", "curve"})


def is_generator_node(spec: Any) -> bool:
    """True se ``spec`` e' un nodo-generatore annidabile in un ``Env``.

    Il nodo parla la stessa grammatica piatta dell'asse: dict con almeno un
    marcatore tra ``Y_GENERATOR_KEYS`` (``values`` | ``ramp`` | ``base``). Le
    forme statiche di un ``Env`` non collidono: ``{type, points, curve}`` non
    contiene marcatori, le liste restano liste.
    """
    return isinstance(spec, dict) and any(k in Y_GENERATOR_KEYS for k in spec)


def expand_env(spec: Threshold, *, seed: int, path: str, depth: int = 0) -> Threshold:
    """Compila un nodo-generatore in una forma statica di ``Env`` (breakpoint).

    I valori del nodo si stendono su tempi equispaziati ``t_i = i/(n-1)`` (X
    implicita lineare, come la X-linear degli assi). Con ``type``/``curve`` nel
    nodo la resa e' la forma dict ``{type, points, curve}``; senza, la lista
    ``[[t, v], ...]``. Le forme statiche passano invariate. Ricorsivo: gli
    ``Env`` dentro il nodo (``base``/``range``/``step``) accettano a loro volta
    nodi, fino a ``MAX_ENV_DEPTH``.

    ``seed`` e' il seed effettivo del generatore padre; una banda annidata senza
    ``seed`` proprio deriva ``stable_seed(f"{seed}:{path}")`` (``path`` e' il
    percorso locale dal padre, es. ``base`` o ``range.step``): ``base`` e
    ``range`` si decorrelano da soli, un seed esplicito congela il sottoalbero.
    """
    if not is_generator_node(spec):
        return spec
    if depth >= MAX_ENV_DEPTH:
        raise ValueError(
            f"{path}: profondita' di annidamento oltre {MAX_ENV_DEPTH} — "
            "config degenere (alias YAML ricorsivo?)."
        )
    node = dict(spec)
    kind = node.pop("type", None)
    curve = node.pop("curve", None)
    if kind not in (None, "linear", "step"):
        raise ValueError(
            f"{path}: type '{kind}' non ammesso in un Env (linear | step); "
            "per la piega non lineare del segmento usa 'curve'."
        )
    key, params = y_generator(node)
    if key == "values":
        values = list(params)
    elif key == "ramp":
        params = expand_params(params, seed=seed, path=path, depth=depth + 1)
        values = ramp(**params)
    else:  # banda annidata (chiave canonica 'band')
        if "n" not in params:
            raise ValueError(
                f"{path}: banda annidata senza 'n' — dentro un Env non c'e' "
                "coupling X/Y, il nodo deve produrre da solo la sua lista."
            )
        eff_seed = params.get("seed", stable_seed(f"{seed}:{path}"))
        params = expand_params(params, seed=eff_seed, path="", depth=depth + 1)
        params["seed"] = eff_seed
        values = band(**params)
    n = len(values)
    points = [[round(i / (n - 1), 9) if n > 1 else 0.0, v] for i, v in enumerate(values)]
    if kind is None and curve is None:
        return points
    out: Dict[str, Any] = {"type": kind or "linear", "points": points}
    if curve is not None:
        out["curve"] = curve
    try:
        _threshold_at(out, 0.0)  # valida subito curve/type (errore col path)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return out


def expand_params(
    params: Dict[str, Any], *, seed: int, path: str = "", depth: int = 0
) -> Dict[str, Any]:
    """Espande i nodi-generatore nei parametri di un generatore (walk generico).

    Cammina il dict senza schema per-strategia: ogni valore che e' un nodo
    (``base``/``range`` di banda e camminata, ``step`` di ramp, e ogni parametro
    Env futuro) si compila in breakpoint; il resto passa invariato. Da chiamare
    alle seam, col seed effettivo gia' risolto (il ``path`` accumulato entra
    nella derivazione del seed dei nodi figli).
    """
    out: Dict[str, Any] = {}
    for k, v in params.items():
        sub = f"{path}.{k}" if path else k
        out[k] = expand_env(v, seed=seed, path=sub, depth=depth)
    return out
