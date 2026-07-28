"""Manopole di documento: il blocco top-level ``let:``.

Un dizionario ``{nome: valore}`` di manopole a riposo, risolte al load del
documento e iniettate per nome in ogni nodo-expr che le referenzia — la stessa
meccanica di ``versions._inject``, un livello sopra: ``let:`` dichiara il
riposo, ``versions:``/``percorso:`` il movimento (che iniettano *dopo* e quindi
ombreggiano la manopola). L'aggancio e' il load del documento, unico choke
point comune a tutti i comandi *prima* dei rispettivi processi: agganciarlo
dentro ``resolve_streams`` sarebbe sbagliato perche' versions risolve gli
stream dopo la propria iniezione, e il riposo sovrascriverebbe il movimento.

Valori ammessi (increment 1): scalare, envelope disegnato (lista ``[[t, v],
...]`` o ``[a, b]``, forma statica di Env che ``eval_expr`` consuma tale e
quale), o nodo-expr derivato (``{expr: "..."}``) che referenzia altre manopole.
Le manopole pescate/generate (banda) sono un incremento successivo (servono
seed + ``expand_env``).
"""
from __future__ import annotations

import copy
from typing import Any, Dict

from .errors import ErrCtx
from .expr import eval_expr, is_expr_node
from .inject import expr_names as _expr_names
from .inject import inject as _inject
from .inject import referenced_names as _referenced_names
from .value_generators import (
    expand_env,
    is_compact_env,
    is_generator_node,
    stable_seed,
)
from .yaml_loc import Locations


def apply_document_let(
    data: Dict[str, Any], locs: Locations | None = None
) -> Dict[str, Any]:
    """Documento con le manopole di ``let:`` risolte e iniettate.

    Senza blocco ``let:`` e' un no-op (ritorna ``data`` invariato). Con il
    blocco: risolve i valori (scalari, envelope, derivati), controlla che ogni
    manopola sia referenziata da almeno un'espressione, li inietta negli scope
    ``let`` per nome e rimuove il blocco dal documento.
    """
    ctx = ErrCtx(locs=locs)
    # Guardia anti-ombreggiamento sui tre livelli: gira al load, prima che
    # l'iniezione consumi i nomi (documento e gruppo spariscono dopo).
    _check_shadowing(data, ctx)
    block = data.get("let")
    if block is None:
        return data
    if not isinstance(block, dict):
        raise ctx.err(
            "let: serve un dict {manopola: valore}.",
            key=("let",),
            hint="es. 'let: {g0: 4, d0: 25}'.",
        )
    out = copy.deepcopy(data)
    out.pop("let")
    if not block:
        return out

    sid = data.get("study_id") or "study"
    resolved = resolve_knobs(block, f"{sid}:let", ctx, key_prefix=("let",))
    _guard_referenced(block, resolved, out, ctx)
    _inject(out, resolved)
    return out


def resolve_knobs(
    block: Dict[str, Any],
    seed_prefix: str,
    ctx: ErrCtx,
    *,
    key_prefix: tuple = ("let",),
) -> Dict[str, Any]:
    """Risolve i valori di un blocco di manopole (documento o gruppo).

    Scalari ed envelope statici (liste) sono gia' valori di scope; una banda
    (o ``ramp``/``values``) e la forma compatta a cicli (``[pattern, 1, n_reps,
    ...]``) si compilano in envelope una volta, con seed
    ``stable_seed(f"{seed_prefix}:{nome}")`` — un pescaggio condiviso; i nodi-
    expr derivati si valutano contro le manopole gia' risolte, a fixpoint
    (l'ordine di dichiarazione non conta). ``key_prefix`` etichetta gli errori
    (``("let",)`` per il documento, ``("streams", nome, "let")`` per un gruppo).
    """
    resolved: Dict[str, Any] = {}
    pending: Dict[str, Any] = {}
    for name, val in block.items():
        if is_expr_node(val):
            pending[name] = val
        elif is_generator_node(val) or is_compact_env(val):
            with ctx.wrapping(key=key_prefix + (name,)):
                resolved[name] = expand_env(
                    val, seed=stable_seed(f"{seed_prefix}:{name}"), path=name
                )
        else:
            resolved[name] = val  # scalare o envelope statico

    progress = True
    while pending and progress:
        progress = False
        for name in list(pending):
            node = pending[name]
            scope = dict(resolved)
            scope.update(node.get("let") or {})
            if _expr_names(node["expr"]) <= set(scope) | {"pi", "e"}:
                with ctx.wrapping(key=key_prefix + (name,)):
                    resolved[name] = eval_expr(node["expr"], scope)
                del pending[name]
                progress = True

    if pending:
        raise ctx.err(
            "let: manopole con dipendenze cicliche o irrisolvibili: "
            f"{sorted(pending)}.",
            key=key_prefix,
            hint="una manopola derivata puo' referenziare solo altre manopole.",
        )
    return resolved


def _knob_names(block: Any) -> set:
    return set(block) if isinstance(block, dict) else set()


def _check_shadowing(data: Dict[str, Any], ctx: ErrCtx) -> None:
    """Ombreggiare un nome fra livelli e' errore (documento > gruppo > voce).

    Documento e' antenato di ogni gruppo e di ogni ``spread.let``; il gruppo
    e' antenato del proprio ``spread.let``. Due gruppi diversi sono fratelli:
    lo stesso nome non collide. Gira al load, sul documento grezzo, prima che
    l'iniezione consumi i nomi.
    """
    doc = _knob_names(data.get("let"))
    for name, entry in (data.get("streams") or {}).items():
        if not isinstance(entry, dict):
            continue
        group = _knob_names(entry.get("let"))
        spread = entry.get("spread")
        voice = _knob_names(spread.get("let")) if isinstance(spread, dict) else set()
        for var in sorted(doc & group):
            raise ctx.err(
                f"let: il gruppo '{name}' ridichiara la manopola di documento "
                f"'{var}' — ombreggiare fra livelli e' errore.",
                key=("streams", name, "let", var),
                hint="dai un nome diverso alla manopola di gruppo (un valore "
                "diverso vuole un nome diverso, non una precedenza).",
            )
        for var in sorted(doc & voice):
            raise ctx.err(
                f"let: lo spread di '{name}' ridichiara la manopola di "
                f"documento '{var}' — ombreggiare fra livelli e' errore.",
                key=("streams", name, "spread", "let", var),
                hint="dai un nome diverso alla manopola di voce.",
            )
        for var in sorted(group & voice):
            raise ctx.err(
                f"let: lo spread di '{name}' ridichiara la manopola di gruppo "
                f"'{var}' — ombreggiare fra livelli e' errore.",
                key=("streams", name, "spread", "let", var),
                hint="dai un nome diverso alla manopola di voce.",
            )


def _guard_referenced(
    block: Dict[str, Any],
    resolved: Dict[str, Any],
    rest: Dict[str, Any],
    ctx: ErrCtx,
) -> None:
    """Ogni manopola dev'essere referenziata da un'espressione: dal resto del
    documento o da un'altra manopola derivata (specchio della guardia di
    versions)."""
    referenced = _referenced_names(rest)
    for val in block.values():
        if is_expr_node(val):
            referenced |= _expr_names(val["expr"])
    for name in block:
        if name not in referenced:
            raise ctx.err(
                f"let: la manopola '{name}' non e' referenziata da nessuna "
                "espressione del documento.",
                key=("let", name),
                hint=f"usala in un nodo-expr (es. \"expr: '{name} * 2'\") "
                "oppure toglila dal blocco.",
            )
