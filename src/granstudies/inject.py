"""Iniezione per nome negli scope ``let`` dei nodi-expr, e analisi dei nomi.

Meccanica condivisa da tutti i livelli di manopola: ``document_let`` (riposo di
documento), ``versions``/``percorso`` (movimento), ``spread`` (manopole di
voce). Un valore si inietta in ogni nodo-expr la cui espressione *nomina* la
variabile: un ``let`` che non la referenzia resta intatto (nessun nome fantasma
negli scope altrui). Il valore iniettato ombreggia il default dichiarato nel
``let`` — e' il punto del meccanismo.

Modulo neutro (solo stdlib + ``expr.is_expr_node``) per non creare cicli:
``spread`` non puo' importare ``versions`` (``versions -> study_spec ->
spread``), quindi gli helper vivono qui.
"""
from __future__ import annotations

import ast
from typing import Any, Dict

from .expr import is_expr_node


def expr_names(text: Any) -> frozenset:
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


def referenced_names(node: Any) -> set:
    """Tutti i nomi referenziati dai nodi-expr di una struttura (ricorsivo)."""
    names: set = set()
    if is_expr_node(node):
        names |= expr_names(node.get("expr"))
    if isinstance(node, dict):
        for v in node.values():
            names |= referenced_names(v)
    elif isinstance(node, list):
        for v in node:
            names |= referenced_names(v)
    return names


def inject(node: Any, values: Dict[str, Any]) -> None:
    """Inietta ``values`` nei ``let`` dei nodi-expr che li nominano (in place)."""
    if is_expr_node(node):
        names = expr_names(node.get("expr"))
        relevant = {k: v for k, v in values.items() if k in names}
        if relevant:
            let = node.get("let")
            if not isinstance(let, dict):
                let = {}
                node["let"] = let
            let.update(relevant)
    if isinstance(node, dict):
        for v in node.values():
            inject(v, values)
    elif isinstance(node, list):
        for v in node:
            inject(v, values)
