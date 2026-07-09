"""Parsing e validazione di ``study.yml`` (la definizione di uno studio).

Uno studio fissa uno stream *base* e un insieme di *assi* (i parametri sotto
osservazione). Ogni asse ha un path YAML, un valore di baseline e una lista di
valori di test. Lo sweep combinatorio (vedi ``sweep.py``) muove gli assi a
ordini crescenti (1 alla volta, a coppie, ...).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

from . import bounds as bounds_mod
from . import yaml_loc
from .errors import ErrCtx, SpecError
from .spread import expand_spreads
from .value_generators import (
    Y_GENERATOR_KEYS,
    band,
    expand_params,
    ramp,
    stable_seed,
    y_generator,
)
from .x_strategies import X_UNITS, x_owns_n

# Chiavi che marcano il generatore Y di un asse (values | ramp | base): la
# presenza di ``base`` marca la banda piatta. Mutuamente esclusive.
_GENERATOR_KEYS = Y_GENERATOR_KEYS
# Chiavi della banda piatta che accompagnano ``base`` (viaggiano con essa,
# vanno rimosse insieme quando uno stream cambia generatore su quell'asse).
_BAND_KEYS = frozenset({"base", "range", "n", "seed", "distribution", "drift"})


@dataclass(frozen=True)
class Axis:
    """Un parametro sotto studio."""

    name: str
    path: str
    baseline: float
    values: List[float]
    interpolation: str = "linear"   # linear | cubic | step
    # Config grezza del generatore Y ({chiave: params}): serve al processo
    # stack, che risolve i valori al momento dell'assemblaggio (coupling con la
    # strategy-X, seed risolti per precedenza).
    generator: Dict[str, Any] = field(default_factory=dict)

    def defers_n(self) -> bool:
        """True se la Y non possiede ``n`` (banda senza ``n``): i valori emergono
        dalla camminata-X in stack, non si enumerano al parse."""
        params = self.generator.get("band")
        return isinstance(params, dict) and "n" not in params


# Chiavi riservate sotto ``axes:`` che non descrivono un asse ma vocabolario Y
# condiviso: ``interpolation`` (curva di Y, default di studio) e ``seed``
# (seed-Y globale, default per ogni banda di Y senza seed proprio). Il timing
# (plateau/transition) e' proprieta' del processo sweep e vive sotto ``sweep:``.
_AXES_RESERVED_KEYS = ("interpolation", "seed")


@dataclass(frozen=True)
class StudySpec:
    study_id: str
    title: str | None
    seed: int | None
    duration: float | None
    samples_dir: str | None
    base: Dict[str, Any]
    axes: List[Axis]
    orders: List[int]
    orderings: List[List[str]] = field(default_factory=list)
    mode: str = "discrete"          # discrete | envelope | both
    plateau: float = 5.0            # secondi per plateau (ascolto stabile)
    transition: float = 5.0         # secondi per transizione tra plateau
    interpolation: str = "linear"   # linear | cubic
    stream_id: str | None = None    # sotto-cartella per versionare gli output
    # Processo stack: config X per-asse (None = blocco ``stack:`` assente), i
    # due seed globali (seed-Y in axes, seed-X in stack) e l'unita' globale
    # della camminata (``stack.unit``), override-abili per-stream via il
    # deep-merge di ``resolve_streams``.
    stack: Dict[str, Any] | None = None
    stack_seed: int | None = None
    stack_unit: str | None = None
    axes_seed: int | None = None

    def axis(self, name: str) -> Axis:
        for ax in self.axes:
            if ax.name == name:
                return ax
        raise KeyError(name)

    def _seed_key(self) -> str:
        return self.stream_id or self.study_id

    def resolved_y_seed(self) -> int:
        """Seed-Y di default per questo stream (il per-asse vince comunque).

        Precedenza: ``axes.seed`` globale, altrimenti auto-derivazione stabile
        dall'id dello stream — gli stream impilati si decorrelano di default.
        Il salt ``:y`` separa il dominio da quello X: senza, Y e X con lo stesso
        seed auto-derivato pescherebbero la stessa sequenza uniforme.
        """
        if self.axes_seed is not None:
            return self.axes_seed
        return stable_seed(f"{self._seed_key()}:y")

    def resolved_x_seed(self) -> int:
        """Seed-X di default per questo stream (il per-asse vince comunque)."""
        if self.stack_seed is not None:
            return self.stack_seed
        return stable_seed(f"{self._seed_key()}:x")

    def resolved_x_unit(self) -> str:
        """Unita' della camminata-X per questo stream (il per-asse vince comunque).

        Stessa catena del seed: ``stack.<asse>.unit`` > ``stack.unit`` globale
        (per-stream via deep-merge) > default ``hz`` (retrocompatibile).
        """
        return self.stack_unit or "hz"


def _validate(spec: StudySpec, ctx: ErrCtx) -> None:
    if not spec.axes:
        raise ctx.err(
            "Lo studio deve definire almeno un asse in 'axes'.", key=("axes",)
        )
    n = len(spec.axes)
    for order in spec.orders:
        if order < 0 or order > n:
            raise ctx.err(
                f"order {order} fuori range: con {n} assi gli ordini validi "
                f"sono 0..{n}.",
                key=("sweep", "orders"),
            )
    axis_names = {ax.name for ax in spec.axes}
    for ordering in spec.orderings:
        unknown = set(ordering) - axis_names
        if unknown:
            raise ctx.err(
                f"orderings: assi sconosciuti {sorted(unknown)}",
                key=("sweep", "orderings"),
                hint=f"gli assi dichiarati sono {sorted(axis_names)}.",
            )
        dupes = [n for n in ordering if ordering.count(n) > 1]
        if dupes:
            raise ctx.err(
                f"orderings: assi duplicati {sorted(set(dupes))}",
                key=("sweep", "orderings"),
            )
    seen = set()
    for ax in spec.axes:
        if ax.name in seen:
            raise ctx.err(f"Asse duplicato: {ax.name}", key=("axes", ax.name))
        seen.add(ax.name)
        if not ax.values and not ax.defers_n():
            raise ctx.err(
                f"Asse '{ax.name}' senza valori di test.",
                key=("axes", ax.name),
                axis=ax.name,
                hint="dichiara 'values', 'ramp' o una banda ('base'/'range'/'n').",
            )
        # Avviso non bloccante: valori fuori bounds engine vengono poi clampati.
        for v in list(ax.values) + [ax.baseline]:
            b = bounds_mod.bounds_for(ax.path)
            if b is not None:
                lo, hi = b
                if (lo is not None and v < lo) or (hi is not None and v > hi):
                    raise ctx.err(
                        f"Asse '{ax.name}' valore {v} fuori bounds {b} "
                        f"per il path '{ax.path}'.",
                        key=("axes", ax.name),
                        axis=ax.name,
                        hint=f"i valori (e il baseline) devono stare in {b}.",
                    )


def _resolve_baseline(
    name: str, cfg: Dict[str, Any], defaults: Dict[str, Any] | None, ctx: ErrCtx
):
    """Risolve il ``baseline`` di un asse: esplicito o dal default engine.

    Single source of truth: se ``baseline`` e' omesso, lo si legge dal default
    dello schema engine via ``path``. I path ``pitch.*`` (unit-driven, nessun
    default) e i parametri con ``default=None`` (es. ``density``) richiedono un
    baseline esplicito.
    """
    if "baseline" in cfg:
        return cfg["baseline"]
    path = cfg["path"]
    if path == "pitch" or path.startswith("pitch."):
        raise ctx.err(
            f"Asse '{name}': path '{path}' e' unit-driven (pitch), "
            f"'baseline' e' obbligatorio.",
            key=("axes", name),
            axis=name,
            hint=f"aggiungi 'baseline:' all'asse '{name}'.",
        )
    if defaults is None:
        from .engine_bridge import parameter_defaults

        defaults = parameter_defaults()
    if path not in defaults or defaults[path] is None:
        raise ctx.err(
            f"Asse '{name}': nessun default engine per il path '{path}', "
            f"'baseline' e' obbligatorio.",
            key=("axes", name),
            axis=name,
            hint=f"aggiungi 'baseline:' all'asse '{name}'.",
        )
    return defaults[path]


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _replace_generators(merged: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Se un override sceglie un generatore per un asse, rimpiazza quello ereditato.

    Il deep-merge conserva le chiavi della base: un asse con ``values`` di base a
    cui lo stream aggiunge ``ramp`` finirebbe con entrambe (collisione). Coerente
    con la semantica "le liste rimpiazzano": il marcatore-generatore dell'override
    vince, si tolgono gli altri ereditati su quello stesso asse. Passare a
    ``values``/``ramp`` toglie anche le chiavi della banda (``base``/``range``/
    ``n``/``seed``); passare a ``base`` toglie ``values``/``ramp``.

    Lato ``stack`` (camminata-X): un override che porta ``base`` diventa/aggiorna
    la camminata via deep-merge; per riportare un asse a ``linear`` lo stream
    annulla l'entry (``stack: {asse: null}``), gestito in ``_stack_config``.
    """
    ov_axes = override.get("axes") or {}
    merged_axes = merged.get("axes") or {}
    for name, ov in ov_axes.items():
        if not isinstance(ov, dict):
            continue
        chosen = _GENERATOR_KEYS & ov.keys()
        ax = merged_axes.get(name)
        if len(chosen) != 1 or not isinstance(ax, dict):
            continue
        (marker,) = chosen
        for k in _GENERATOR_KEYS - chosen:      # via gli altri marcatori
            ax.pop(k, None)
        if marker in ("values", "ramp"):        # via le chiavi della banda
            for k in _BAND_KEYS:
                ax.pop(k, None)


def resolve_streams(
    data: Dict[str, Any],
    study_id: str | None = None,
    locs: yaml_loc.Locations | None = None,
) -> List["StudySpec"]:
    """Ritorna una lista di StudySpec, uno per stream.

    Se ``streams:`` è assente, ritorna un singolo spec senza stream_id.
    Le entry-spread vengono espanse in entry ordinarie prima del merge
    (``spread.expand_spreads``): da qui in poi ogni stream, generato o
    scritto a mano, e' un override come gli altri. Con ``locs`` gli errori
    di parse portano file e riga; la rete di sicurezza sotto etichetta con
    lo stream anche i ``ValueError`` nudi non ancora migrati a ``SpecError``.
    """
    sid = study_id or data.get("study_id") or "study"
    streams = data.get("streams")
    if not streams:
        return [parse_study_spec(data, sid, locs=locs)]
    streams = expand_spreads(streams, locs)
    result = []
    for stream_id, override in streams.items():
        merged = _deep_merge(data, override or {})
        _replace_generators(merged, override or {})
        merged.pop("streams", None)
        merged.setdefault("sweep", {})["stream_id"] = stream_id
        try:
            result.append(parse_study_spec(merged, sid, locs=locs))
        except SpecError:
            raise
        except ValueError as e:
            raise SpecError(
                str(e),
                stream=stream_id,
                source=locs.source if locs else None,
            ) from e
    return result


def _stack_config(
    data: Dict[str, Any], ctx: ErrCtx
) -> tuple[Dict[str, Any] | None, int | None, str | None]:
    """Estrae dal documento il blocco ``stack:``: (config per-asse, seed-X
    globale, unit globale della camminata).

    Schema piatto: ``seed`` e ``unit`` sono le chiavi riservate; ogni altra
    chiave e' un nome d'asse -> camminata-X (banda ``base``/``range``/``seed``,
    piu' ``unit``/``distribution``/``drift`` come nella banda di Y). La
    *presenza* dell'asse marca la camminata; l'assenza dal blocco = ``linear``.
    Una entry annullata (``asse: null``, utile per riportare a linear in uno
    stream) viene scartata. Blocco assente -> (None, None, None); ``curve`` va
    dentro l'Env di ``base``/``range``, non come chiave dell'entry.
    """
    if "stack" not in data:
        return None, None, None
    raw = dict(data.get("stack") or {})
    seed = raw.pop("seed", None)
    unit = raw.pop("unit", None)
    if unit is not None and unit not in X_UNITS:
        opts = " | ".join(sorted(X_UNITS))
        raise ctx.err(
            f"stack: unit '{unit}' non ammessa ({opts}).",
            key=("stack", "unit"),
            hint="'hz' = banda in frequenza di generazione, 's' = banda in "
            "periodo (secondi tra breakpoint).",
        )
    raw = {name: xcfg for name, xcfg in raw.items() if xcfg is not None}
    for name, xcfg in raw.items():
        if isinstance(xcfg, dict) and ("rand" in xcfg or "cps" in xcfg):
            raise ctx.err(
                f"stack: asse '{name}', i wrapper 'rand:'/'cps:' non esistono "
                "piu': dichiara la camminata piatta (base/range/seed diretti).",
                key=("stack", name),
                axis=name,
                hint="es. 'rand: {cps: {base, range}}' -> 'base: ...', 'range: ...'.",
            )
        if not isinstance(xcfg, dict) or "base" not in xcfg:
            raise ctx.err(
                f"stack: asse '{name}' deve avere una camminata con 'base' "
                f"(banda in Hz, o in secondi con 'unit: s'), trovato {xcfg!r}.",
                key=("stack", name),
                axis=name,
                hint="un asse assente dal blocco 'stack:' resta 'linear' (n dalla Y).",
            )
        extra = set(xcfg) - {"base", "range", "seed", "unit", "distribution", "drift"}
        if extra:
            raise ctx.err(
                f"stack: asse '{name}', chiavi non ammesse {sorted(extra)} "
                "(solo base/range/seed/unit/distribution/drift).",
                key=("stack", name),
                axis=name,
                hint="'curve' va dentro l'Env di base/range, non come chiave dell'entry.",
            )
        if "unit" in xcfg and xcfg["unit"] not in X_UNITS:
            opts = " | ".join(sorted(X_UNITS))
            raise ctx.err(
                f"stack: asse '{name}', unit '{xcfg['unit']}' non ammessa ({opts}).",
                key=("stack", name),
                axis=name,
                hint="'hz' = banda in frequenza di generazione, 's' = banda in "
                "periodo (secondi tra breakpoint).",
            )
    return raw, seed, unit


def parse_study_spec(
    data: Dict[str, Any],
    study_id: str | None = None,
    locs: yaml_loc.Locations | None = None,
) -> StudySpec:
    """Costruisce uno ``StudySpec`` da un dict gia' caricato.

    ``locs`` (opzionale) sono le posizioni delle chiavi nel file d'origine
    (``yaml_loc``): con esse gli errori portano file e riga. Il documento puo'
    essere il merge di una stream: lo ``stream_id`` in ``sweep:`` guida sia
    l'etichetta degli errori sia il lookup override-first delle righe.
    """
    axes_raw = data.get("axes") or {}
    # Risolve i default engine una sola volta, solo se serve (lazy).
    _defaults_cache: Dict[str, Any] | None = None
    needs_defaults = any(
        k not in _AXES_RESERVED_KEYS and isinstance(v, dict) and "baseline" not in v
        for k, v in axes_raw.items()
    )
    if needs_defaults:
        from .engine_bridge import parameter_defaults

        _defaults_cache = parameter_defaults()

    sweep_cfg = data.get("sweep") or {}
    ctx = ErrCtx(locs=locs, stream=sweep_cfg.get("stream_id") or None)
    if "combine" in sweep_cfg:
        raise ctx.err(
            "sweep.combine non esiste piu': lo sweep fa solo il prodotto "
            "cartesiano.",
            key=("sweep", "combine"),
            hint="l'accoppiamento degli assi (ex parallel) vive nel processo "
            "stack — stessa strategy-X e stesso n.",
        )
    stack_axes, stack_seed, stack_unit = _stack_config(data, ctx)
    axes_seed = axes_raw.get("seed")
    sid = study_id or data.get("study_id") or "study"
    seed_key = sweep_cfg.get("stream_id") or sid
    # Default per le bande di Y senza seed proprio (precedenza: per-asse >
    # axes.seed globale > auto-derivazione per-stream).
    default_y_seed = axes_seed if axes_seed is not None else stable_seed(f"{seed_key}:y")

    study_interpolation = axes_raw.get("interpolation", "linear")
    axes: List[Axis] = []
    for name, cfg in axes_raw.items():
        if name in _AXES_RESERVED_KEYS:
            continue
        if not isinstance(cfg, dict):
            hint = (
                "'plateau'/'transition' vivono in 'sweep:', non in 'axes:'."
                if name in ("plateau", "transition")
                else "un asse e' un dict con 'path' e un generatore Y."
            )
            raise ctx.err(
                f"Asse '{name}': config non valida ({cfg!r}), serve un dict.",
                key=("axes", name),
                axis=name,
                hint=hint,
            )
        if "path" not in cfg:
            raise ctx.err(
                f"Asse '{name}': manca 'path' (il parametro engine da muovere).",
                key=("axes", name),
                axis=name,
                hint="es. 'path: density' o 'path: grain.duration'.",
            )
        # Generatore Y riconosciuto dalla forma (values | ramp | base): chiave
        # canonica values|ramp|band, con i parametri della banda raccolti piatti.
        with ctx.wrapping(key=("axes", name), axis=name):
            gen_key, gen_params = y_generator(cfg)
        x_cfg = (stack_axes or {}).get(name)
        defers = gen_key == "band" and "n" not in gen_params
        if defers:
            # n-ownership, verso X: solo la camminata-X 'base' puo' possedere n.
            if not x_owns_n(x_cfg):
                raise ctx.err(
                    f"Asse '{name}': banda senza 'n' richiede la camminata-X "
                    "'base' nel blocco 'stack:' (e' la X a possedere n).",
                    key=("axes", name),
                    axis=name,
                    hint=f"dichiara 'n' nella banda (axes.{name}.n) oppure la "
                    f"camminata sotto 'stack: {{{name}: {{base: ...}}}}'.",
                )
            values: List[float] = []
        else:
            # n-ownership, verso Y: con la camminata-X la Y non puo' contare i valori.
            if x_owns_n(x_cfg):
                raise ctx.err(
                    f"Asse '{name}': la camminata-X 'base' possiede n, ma il "
                    f"generatore Y '{gen_key}' enumera i valori.",
                    key=("stack", name),
                    axis=name,
                    hint=f"usa la banda senza 'n' su axes.{name}, oppure togli "
                    f"la camminata-X (stack.{name}).",
                )
            # Seam sweep/Y dei generatori annidati: i nodi dentro gli Env
            # (base/range della banda, step del ramp) si compilano in
            # breakpoint qui, col seed effettivo gia' risolto.
            with ctx.wrapping(key=("axes", name), axis=name):
                if gen_key == "values":
                    values = list(gen_params)
                elif gen_key == "ramp":
                    params = expand_params(gen_params, seed=default_y_seed)
                    values = ramp(**params)
                else:  # band con n: la Y possiede il conteggio
                    params = dict(gen_params)
                    params.setdefault("seed", default_y_seed)
                    values = band(**expand_params(params, seed=params["seed"]))
        axes.append(
            Axis(
                name=name,
                path=cfg["path"],
                baseline=_resolve_baseline(name, cfg, _defaults_cache, ctx),
                values=values,
                interpolation=cfg.get("interpolation", study_interpolation),
                generator={gen_key: gen_params},
            )
        )
    if stack_axes:
        axis_names = {ax.name for ax in axes}
        unknown = set(stack_axes) - axis_names
        if unknown:
            raise ctx.err(
                f"stack: assi sconosciuti {sorted(unknown)}.",
                key=("stack",),
                hint=f"gli assi dichiarati in 'axes:' sono {sorted(axis_names)}.",
            )
    if stack_axes is not None and data.get("duration") is None:
        raise ctx.err(
            "stack: serve 'duration:' top-level (la durata condivisa su cui "
            "il processo normalizza i tempi).",
            key=("stack",),
            hint="aggiungi 'duration: <secondi>' al livello top del documento.",
        )
    orders = list(sweep_cfg.get("orders", list(range(1, len(axes) + 1))))
    orderings = [list(o) for o in sweep_cfg.get("orderings", [])]
    spec = StudySpec(
        study_id=sid,
        title=data.get("title"),
        seed=data.get("seed"),
        duration=data.get("duration"),
        samples_dir=data.get("samples_dir"),
        base=dict(data.get("base") or {}),
        axes=axes,
        orders=orders,
        orderings=orderings,
        mode=sweep_cfg.get("mode", "discrete"),
        plateau=float(sweep_cfg.get("plateau", 5.0)),
        transition=float(sweep_cfg.get("transition", 5.0)),
        interpolation=axes_raw.get("interpolation", "linear"),
        stream_id=sweep_cfg.get("stream_id") or None,
        stack=stack_axes,
        stack_seed=stack_seed,
        stack_unit=stack_unit,
        axes_seed=axes_seed,
    )
    _validate(spec, ctx)
    return spec


def load_study_spec(path: str) -> StudySpec:
    """Carica e valida ``study.yml`` da disco (con posizioni per gli errori)."""
    data, locs = yaml_loc.load(path)
    study_id = data.get("study_id") or os.path.basename(os.path.dirname(os.path.abspath(path)))
    return parse_study_spec(data, study_id=study_id, locs=locs)
