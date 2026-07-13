"""Processo ``versions``: repliche dello stack concatenate nel tempo.

Il quarto blocco accanto ad ``axes``/``stack``/``sweep``: dichiara variabili
(vocabolario dei generatori Y: ``values`` / ``ramp`` / banda con ``n``) i cui
valori vengono iniettati negli scope ``let`` dei nodi-expr del documento. Ogni
combinazione (prodotto cartesiano lessicografico nell'ordine di dichiarazione,
prima variabile esterna/lenta) genera una *versione*: la replica completa
degli stream dello stack — envelope, camminate e seed identici — con l'onset
scalato di ``k * duration`` e lo ``stream_id`` suffissato con i valori della
combinazione. Le versioni si ascoltano cosi' in cascata dentro un unico
documento engine, senza rimappare nessun envelope: ogni stream conserva il
proprio ``time_mode: normalized`` sulla propria durata, e l'engine dimensiona
il buffer su ``max(onset + duration)``.

Il blocco richiede ``stack:`` (versions e' un modificatore del processo
stack, l'output resta ``yaml/stack/stack.yml``) e ``duration:`` top-level.
Una variabile deve essere referenziata da almeno un'espressione del documento
(guardia anti-refuso); il default dichiarato nel ``let`` (es. ``d: 0``) tiene
lo studio valido anche senza il blocco, e viene ombreggiato dall'iniezione.
"""
from __future__ import annotations

import ast
import copy
import itertools
from typing import Any, Dict, List, Optional

from .errors import ErrCtx
from .expr import is_expr_node
from .stack import build_stack_stream
from .study_spec import resolve_streams
from .sweep import _fmt
from .value_generators import expand_params, band, ramp, stable_seed, y_generator
from .yaml_builder import build_multi_document
from .yaml_loc import Locations

# Nomi che il sistema fornisce gia' agli scope expr (``i``/``n`` dello spread,
# le costanti): una variabile di versions con questi nomi sarebbe ambigua.
_RESERVED_NAMES = frozenset({"i", "n", "pi", "e"})


def _expr_names(text: Any) -> frozenset:
    """I nomi referenziati da un'espressione (vuoto se non parsabile: gli
    errori di sintassi emergono alla valutazione, con il loro contesto)."""
    if not isinstance(text, str):
        return frozenset()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return frozenset()
    return frozenset(
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    )


def _referenced_names(node: Any) -> set:
    """Tutti i nomi referenziati dai nodi-expr di una struttura (ricorsivo)."""
    names: set = set()
    if is_expr_node(node):
        names |= _expr_names(node.get("expr"))
    if isinstance(node, dict):
        for v in node.values():
            names |= _referenced_names(v)
    elif isinstance(node, list):
        for v in node:
            names |= _referenced_names(v)
    return names


def parse_versions(
    data: Dict[str, Any], locs: Locations | None = None
) -> Dict[str, List[Any]]:
    """Valida il blocco ``versions:`` e risolve i valori di ogni variabile.

    Ritorna ``{nome: [valori]}`` nell'ordine di dichiarazione. Ogni variabile
    e' un generatore Y (``values``/``ramp``/banda **con** ``n``: qui non c'e'
    coupling con una X, il conteggio va dichiarato). Una banda senza ``seed``
    deriva ``stable_seed("<study>:versions:<nome>")``: deterministico tra run,
    variabili diverse decorrelate da sole.
    """
    ctx = ErrCtx(locs=locs)
    raw = data.get("versions")
    if not isinstance(raw, dict) or not raw:
        raise ctx.err(
            "versions: serve un dict non vuoto {variabile: generatore}.",
            key=("versions",),
            hint="es. 'versions: {d: {values: [1, 2, 3]}}'.",
        )
    sid = data.get("study_id") or "study"
    referenced = _referenced_names(
        {k: v for k, v in data.items() if k != "versions"}
    )
    out: Dict[str, List[Any]] = {}
    for name, cfg in raw.items():
        key = ("versions", name)
        if name in _RESERVED_NAMES:
            raise ctx.err(
                f"versions: '{name}' e' un nome riservato degli scope expr "
                f"({', '.join(sorted(_RESERVED_NAMES))}).",
                key=key,
                hint="scegli un altro nome per la variabile.",
            )
        if not isinstance(cfg, dict):
            raise ctx.err(
                f"versions: la variabile '{name}' deve avere un generatore "
                f"(dict), trovato {cfg!r}.",
                key=key,
                hint="dichiara 'values', 'ramp' o una banda ('base'/'range'/'n').",
            )
        with ctx.wrapping(key=key):
            gen_key, params = y_generator(cfg)
        seed = stable_seed(f"{sid}:versions:{name}")
        with ctx.wrapping(key=key):
            if gen_key == "values":
                values: List[Any] = list(params)
            elif gen_key == "ramp":
                values = ramp(**expand_params(params, seed=seed))
            else:  # band
                if "n" not in params:
                    raise ctx.err(
                        f"versions: la banda della variabile '{name}' richiede "
                        "'n' (qui non c'e' una camminata-X a possedere il "
                        "conteggio).",
                        key=key,
                    )
                band_params = dict(params)
                band_params.setdefault("seed", seed)
                values = band(
                    **expand_params(band_params, seed=band_params["seed"])
                )
        if not values:
            raise ctx.err(
                f"versions: la variabile '{name}' non genera nessun valore.",
                key=key,
            )
        if name not in referenced:
            raise ctx.err(
                f"versions: la variabile '{name}' non e' referenziata da "
                "nessuna espressione del documento.",
                key=key,
                hint=f"usala in un nodo-expr (es. \"expr: 'env + {name}'\") "
                "oppure toglila dal blocco.",
            )
        out[name] = values
    return out


def version_combos(vars: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Prodotto cartesiano lessicografico delle variabili.

    L'ordine di dichiarazione conta: la prima variabile e' esterna (lenta),
    l'ultima interna (veloce) — come gli ``orderings`` dello sweep.
    """
    names = list(vars)
    return [
        dict(zip(names, picked))
        for picked in itertools.product(*(vars[n] for n in names))
    ]


def inject_combo(data: Dict[str, Any], combo: Dict[str, Any]) -> Dict[str, Any]:
    """Copia del documento con i valori della combinazione iniettati nei ``let``.

    L'iniezione tocca solo i nodi-expr la cui espressione *nomina* la
    variabile: un ``let`` che non la referenzia resta intatto (nessun nome
    fantasma negli scope altrui). Il valore iniettato ombreggia il default
    dichiarato nel ``let`` — e' il punto del meccanismo.
    """
    out = copy.deepcopy(data)
    _inject(out, combo)
    return out


def _inject(node: Any, combo: Dict[str, Any]) -> None:
    if is_expr_node(node):
        names = _expr_names(node.get("expr"))
        relevant = {k: v for k, v in combo.items() if k in names}
        if relevant:
            let = node.get("let")
            if not isinstance(let, dict):
                let = {}
                node["let"] = let
            let.update(relevant)
    if isinstance(node, dict):
        for v in node.values():
            _inject(v, combo)
    elif isinstance(node, list):
        for v in node:
            _inject(v, combo)


def generate_versions_document(
    data: Dict[str, Any],
    study_id: str | None = None,
    locs: Locations | None = None,
    *,
    output_sr: Optional[int] = 48000,
) -> Dict[str, Any]:
    """Il documento engine multi-stream con le versioni concatenate.

    Per ogni combinazione: iniezione nello scope, risoluzione degli stream
    (``resolve_streams``, il parse di sempre), costruzione via
    ``build_stack_stream`` — identica allo stack — poi onset scalato di
    ``k * duration`` e ``stream_id`` suffissato con l'etichetta della
    combinazione (``fermo__d=1``). La durata documento e' ``N * duration``.
    """
    sid = study_id or data.get("study_id") or "study"
    ctx = ErrCtx(locs=locs)
    if "stack" not in data:
        raise ctx.err(
            "versions: richiede il blocco 'stack:' (versions e' un "
            "modificatore del processo stack).",
            key=("versions",),
            hint="aggiungi 'stack: {}' (anche vuoto) al documento.",
        )
    duration = data.get("duration")
    if duration is None:
        raise ctx.err(
            "versions: serve 'duration:' top-level (la durata di ogni "
            "versione, su cui gli onset vengono scalati).",
            key=("versions",),
            hint="aggiungi 'duration: <secondi>' al livello top del documento.",
        )
    vars = parse_versions(data, locs=locs)
    combos = version_combos(vars)
    base_data = {k: v for k, v in data.items() if k != "versions"}

    built: List[Dict[str, Any]] = []
    for k, combo in enumerate(combos):
        label = "__".join(f"{name}={_fmt(v)}" for name, v in combo.items())
        data_k = inject_combo(base_data, combo)
        for spec in resolve_streams(data_k, sid, locs=locs):
            s = build_stack_stream(spec, output_sr=output_sr)
            s["stream_id"] = f"{s['stream_id']}__{label}"
            onset = s.get("onset") or 0
            s["onset"] = onset + k * duration
            built.append(s)
    return build_multi_document(
        built,
        title=f"{sid} :: stack :: versions",
        seed=data.get("seed"),
        duration=len(combos) * duration,
    )
