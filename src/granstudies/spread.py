"""Espansione delle entry-spread di ``streams:`` (macro-forma).

Una entry di ``streams:`` con la chiave riservata ``spread`` non descrive un
solo stream ma ne genera ``n``, distribuendo i valori di uno o piu' parametri
(path puntati nel documento, es. ``base.pointer.start``) secondo una strategy
del vocabolario Y (``values`` / ``ramp`` / banda ``base``). E' l'asse mancante
del sistema: Y distribuisce valori nel tempo (micro-forma), la camminata-X
distribuisce i tempi, spread distribuisce valori nella popolazione di stream
(macro-forma) — stesso vocabolario, asse diverso.

Puro pre-processing: ``resolve_streams`` chiama ``expand_spreads`` prima del
loop di deep-merge, tutto il resto della pipeline vede entry ordinarie. Lo
``study.yml`` sorgente non viene mai riscritto.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .errors import ErrCtx
from .value_generators import band, expand_params, ramp, stable_seed, y_generator
from .yaml_loc import Locations

# Chiavi ammesse nel blocco ``spread:``.
_SPREAD_KEYS = frozenset({"n", "over"})

# Default iniettato nei generati quando l'entry non dichiara ``sweep:``: gli
# stream di uno spread vivono solo nello stack (ascolto verticale), non
# moltiplicano le varianti di sweep.
_SWEEP_OFF = {"orders": [], "orderings": []}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Stessa semantica del deep-merge di ``study_spec`` (copia locale: e'
    ``study_spec`` a importare questo modulo, non viceversa)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _deep_set(target: Dict[str, Any], dotted: str, value: Any) -> None:
    """Imposta ``value`` al path puntato, creando i dict intermedi.

    Un intermedio non-dict viene rimpiazzato: la strategy vince sull'override
    comune, come l'override vince sulla base nel deep-merge delle stream.
    """
    keys = dotted.split(".")
    node = target
    for k in keys[:-1]:
        if not isinstance(node.get(k), dict):
            node[k] = {}
        node = node[k]
    node[keys[-1]] = value


def _strategy(name: str, path: str, cfg: Any, ctx: ErrCtx) -> tuple:
    """(marcatore canonico, params) della strategy di un path di ``over``."""
    key = ("spread", "over", path)
    if not isinstance(cfg, dict):
        raise ctx.err(
            f"spread: il path '{path}' deve avere una strategy (dict), "
            f"trovato {cfg!r}.",
            key=key,
            hint="dichiara 'values', 'ramp' o una banda ('base'/'range'/'seed').",
        )
    with ctx.wrapping(
        key=key,
        hint="ogni path di 'over' vuole esattamente una strategy tra "
        "'values', 'ramp' e banda ('base').",
    ):
        return y_generator(cfg)


def _ramp_form(path: str, params: Dict[str, Any], ctx: ErrCtx) -> str:
    """Forma del ramp di uno spread: ``full`` | ``step`` | ``stop``.

    ``{start, stop, step}`` e' il ramp pieno degli assi (possiede il
    conteggio); le forme parziali lasciano ``n`` allo spread: ``{start, step}``
    e' la progressione aritmetica (l'offset additivo), ``{start, stop}`` la
    suddivisione lineare in ``n`` punti.
    """
    key = ("spread", "over", path)
    extra = set(params) - {"start", "stop", "step"}
    if extra:
        raise ctx.err(
            f"spread: ramp sul path '{path}', chiavi non ammesse "
            f"{sorted(extra)} (solo start/stop/step).",
            key=key,
        )
    if "start" not in params:
        raise ctx.err(
            f"spread: ramp sul path '{path}' senza 'start'.",
            key=key,
        )
    has_stop, has_step = "stop" in params, "step" in params
    if has_stop and has_step:
        return "full"
    if has_step:
        return "step"
    if has_stop:
        return "stop"
    raise ctx.err(
        f"spread: ramp sul path '{path}' con solo 'start' — serve almeno "
        "'step' (progressione aritmetica) o 'stop' (suddivisione su n).",
        key=key,
    )


def _owned_count(
    name: str, path: str, marker: str, params: Any, ctx: ErrCtx
) -> int | None:
    """Conteggio posseduto dalla strategy, se lo possiede.

    ``values`` possiede la propria lunghezza; il ramp pieno la sua griglia;
    la banda solo se dichiara ``n`` proprio. Le forme parziali di ramp e la
    banda senza ``n`` lasciano il conteggio allo spread.
    """
    if marker == "values":
        return len(params)
    if marker == "ramp" and _ramp_form(path, params, ctx) == "full":
        return len(_ramp_full(name, path, params, ctx))
    if marker == "band" and "n" in params:
        return params["n"]
    return None


def _ramp_full(
    name: str, path: str, params: Dict[str, Any], ctx: ErrCtx
) -> List[float]:
    """Griglia del ramp pieno, con i nodi-generatore di ``step`` gia' espansi."""
    with ctx.wrapping(key=("spread", "over", path)):
        seed = stable_seed(f"{name}:spread:{path}")
        return ramp(**expand_params(params, seed=seed))


def _resolve_n(
    name: str, spread: Dict[str, Any], strategies: Dict[str, tuple], ctx: ErrCtx
) -> int:
    """``n`` effettivo dello spread: esplicito e conteggi posseduti coincidono."""
    counts: Dict[str, int] = {}
    if "n" in spread:
        counts["spread.n"] = spread["n"]
    for path, (marker, params) in strategies.items():
        owned = _owned_count(name, path, marker, params, ctx)
        if owned is not None:
            counts[path] = owned
    if not counts:
        raise ctx.err(
            "spread: 'n' non derivabile — nessuna strategy possiede il "
            "conteggio.",
            key=("spread",),
            hint="dichiara 'n:' nel blocco spread, oppure una strategy che "
            "possiede il conteggio ('values' o 'ramp' completo).",
        )
    values = set(counts.values())
    if len(values) != 1:
        dettaglio = ", ".join(f"{k}={v}" for k, v in counts.items())
        raise ctx.err(
            f"spread: conteggi discordi ({dettaglio}) — 'n' e le strategy "
            "devono coincidere (valori appaiati per indice, niente prodotto "
            "cartesiano).",
            key=("spread",),
        )
    (n,) = values
    if not isinstance(n, int) or n < 1:
        raise ctx.err(
            f"spread: 'n' deve essere un intero >= 1 (ricevuto {n!r}).",
            key=("spread", "n"),
        )
    return n


def _strategy_values(
    name: str, path: str, marker: str, params: Any, n: int, ctx: ErrCtx
) -> List[Any]:
    """Gli ``n`` valori della strategy, uno per stream generato.

    Il seed di default (banda senza ``seed``, nodi-generatore negli Env) e'
    ``stable_seed(f"{nome}:spread:{path}")``: deterministico tra run, e path
    diversi della stessa spread si decorrelano da soli.
    """
    if marker == "values":
        return list(params)
    key = ("spread", "over", path)
    if marker == "ramp":
        form = _ramp_form(path, params, ctx)
        if form == "full":
            return _ramp_full(name, path, params, ctx)
        start = params["start"]
        if form == "step":
            step = params["step"]
            if not isinstance(step, (int, float)):
                raise ctx.err(
                    f"spread: ramp sul path '{path}', senza 'stop' il passo "
                    f"deve essere scalare (ricevuto {step!r}).",
                    key=key,
                    hint="per un passo-Env dichiara anche 'stop' (ramp pieno).",
                )
            return [round(start + step * i, 9) for i in range(n)]
        stop = params["stop"]  # form == "stop": suddivisione lineare su n
        if n == 1:
            return [round(start, 9)]
        return [round(start + (stop - start) * i / (n - 1), 9) for i in range(n)]
    # banda: n dello spread, seed esplicito o derivato per-path.
    band_params = {k: v for k, v in params.items() if k != "n"}
    band_params.setdefault("seed", stable_seed(f"{name}:spread:{path}"))
    with ctx.wrapping(key=key):
        return band(n=n, **expand_params(band_params, seed=band_params["seed"]))


def _validate_spread(name: str, spread: Any, ctx: ErrCtx) -> Dict[str, Any]:
    if not isinstance(spread, dict):
        raise ctx.err(
            f"spread: serve un dict con 'over' (e opzionalmente 'n'), "
            f"trovato {spread!r}.",
            key=("spread",),
        )
    extra = set(spread) - _SPREAD_KEYS
    if extra:
        raise ctx.err(
            f"spread: chiavi non ammesse {sorted(extra)} (solo n/over).",
            key=("spread",),
            hint="le strategy vivono sotto 'over: {path: strategy}'.",
        )
    over = spread.get("over")
    if not isinstance(over, dict) or not over:
        raise ctx.err(
            "spread: 'over' obbligatorio e non vuoto ({path: strategy}).",
            key=("spread",),
            hint="es. \"over: {base.pointer.start: {ramp: {start: 0.1, "
            "step: 0.1}}}\".",
        )
    return over


def _expand_entry(
    name: str, entry: Dict[str, Any], locs: Locations | None
) -> Dict[str, Dict[str, Any]]:
    """Espande una entry-spread nel dict ``{nome generato: override}``."""
    ctx = ErrCtx(locs=locs, stream=name)
    spread = entry["spread"]
    over = _validate_spread(name, spread, ctx)
    strategies = {path: _strategy(name, path, cfg, ctx) for path, cfg in over.items()}
    n = _resolve_n(name, spread, strategies, ctx)
    per_path = {
        path: _strategy_values(name, path, marker, params, n, ctx)
        for path, (marker, params) in strategies.items()
    }

    proto = {k: v for k, v in entry.items() if k != "spread"}
    width = len(str(n))
    generated: Dict[str, Dict[str, Any]] = {}
    for i in range(n):
        override = copy.deepcopy(proto)
        for path, values in per_path.items():
            _deep_set(override, path, values[i])
        if "sweep" not in override:
            override["sweep"] = copy.deepcopy(_SWEEP_OFF)
        generated[f"{name}_{i + 1:0{width}d}"] = override
    return generated


def expand_spreads(
    streams: Dict[str, Any], locs: Locations | None = None
) -> Dict[str, Any]:
    """Espande le entry-spread di ``streams:`` in entry ordinarie.

    Le entry senza ``spread`` passano invariate; l'ordine del documento e'
    preservato (i generati compaiono al posto della loro entry). Con ``locs``
    gli errori portano file e riga (lookup override-first dentro
    ``streams.<nome>``).
    """
    expanded: Dict[str, Any] = {}
    for name, entry in streams.items():
        if not isinstance(entry, dict) or "spread" not in entry:
            expanded[name] = entry
            continue
        expanded.update(_expand_entry(name, entry, locs))
    return expanded
