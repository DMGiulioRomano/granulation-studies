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
from .versions import _expr_names, _inject, _referenced_names
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
    block = data.get("let")
    if block is None:
        return data
    ctx = ErrCtx(locs=locs)
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

    resolved = _resolve_knobs(block, ctx)
    _guard_referenced(block, resolved, out, ctx)
    _inject(out, resolved)
    return out


def _resolve_knobs(block: Dict[str, Any], ctx: ErrCtx) -> Dict[str, Any]:
    """Risolve i valori delle manopole. Scalari ed envelope (liste) sono gia'
    valori di scope; i nodi-expr derivati si valutano contro le manopole gia'
    risolte, a fixpoint (l'ordine di dichiarazione non conta)."""
    resolved: Dict[str, Any] = {}
    pending: Dict[str, Any] = {}
    for name, val in block.items():
        if is_expr_node(val):
            pending[name] = val
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
                with ctx.wrapping(key=("let", name)):
                    resolved[name] = eval_expr(node["expr"], scope)
                del pending[name]
                progress = True

    if pending:
        raise ctx.err(
            "let: manopole con dipendenze cicliche o irrisolvibili: "
            f"{sorted(pending)}.",
            key=("let",),
            hint="una manopola derivata puo' referenziare solo altre manopole.",
        )
    return resolved


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
