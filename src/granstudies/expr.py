"""Valutatore di espressioni aritmetiche su scalari ed Env (nodo-expr).

Il nodo-expr ``{expr: "...", let: {...}}`` e' una forma di ``Threshold``:
un'espressione aritmetica i cui nomi si risolvono in uno scope di scalari e
forme *statiche* di Env (``[a, b]``, ``[[t, v], ...]``, ``{type, points,
curve}``). Un'operazione tra un Env e uno scalare agisce elementwise sulle y
(i tempi restano intatti); tra due Env e' un errore esplicito — richiederebbe
unione dei breakpoint, si estende se servira' davvero.

Grammatica (whitelist AST, ``mode="eval"``): numeri, nomi, ``+ - * / **``,
unario ``-``, parentesi. Niente call, subscript, confronti: il parser rifiuta
ogni altro costrutto col frammento incriminato.

Modulo puro, solo stdlib: chi lo chiama decide lo scope (``expand_env`` passa
il solo ``let``; la strategy di spread aggiunge ``i`` e ``n``) e avvolge i
``ValueError`` col proprio contesto (path, stream, riga).
"""
from __future__ import annotations

import ast
import operator
from typing import Any, Dict, Mapping, Tuple

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

# Chiavi ammesse nel nodo-expr.
_NODE_KEYS = frozenset({"expr", "let"})


def is_expr_node(spec: Any) -> bool:
    """True se ``spec`` e' un nodo-expr (dict con chiave ``expr``)."""
    return isinstance(spec, dict) and "expr" in spec


def parse_expr_node(spec: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """``(testo, let)`` del nodo-expr, validati.

    ``let`` e' opzionale; i suoi valori devono essere scalari o forme statiche
    di Env — un nodo-generatore dentro ``let`` e' un incrocio di meccanismi
    non ammesso (la validazione lo rifiuta come forma non riconosciuta).
    """
    extra = set(spec) - _NODE_KEYS
    if extra:
        raise ValueError(
            f"nodo-expr: chiavi non ammesse {sorted(extra)} (solo expr/let)."
        )
    text = spec["expr"]
    if not isinstance(text, str):
        raise ValueError(
            f"nodo-expr: 'expr' deve essere una stringa (ricevuto {text!r})."
        )
    let = spec.get("let") or {}
    if not isinstance(let, dict):
        raise ValueError(f"nodo-expr: 'let' deve essere un dict (ricevuto {let!r}).")
    for name, value in let.items():
        _checked(name, value)
    return text, dict(let)


def eval_expr(text: str, scope: Mapping[str, Any]) -> Any:
    """Valuta ``text`` nello ``scope``: scalare o Env (elementwise sulle y).

    Il risultato e' sempre una struttura nuova (niente alias con lo scope),
    con i float arrotondati a 9 decimali come nel resto del modulo dei
    generatori.
    """
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"expr: sintassi non valida in {text!r}: {exc.msg}.") from exc
    try:
        out = _eval(tree.body, scope)
    except ZeroDivisionError:
        raise ValueError(f"expr: divisione per zero in {text!r}.") from None
    return _rebuild(out)


def _is_scalar(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_pairs(v: Any) -> bool:
    """True se ``v`` e' una lista di breakpoint ``[[t, y], ...]`` numerici."""
    return (
        isinstance(v, (list, tuple))
        and len(v) > 0
        and all(
            isinstance(p, (list, tuple)) and len(p) == 2
            and _is_scalar(p[0]) and _is_scalar(p[1])
            for p in v
        )
    )


def _checked(name: str, v: Any) -> Any:
    """Il valore di scope ``name``, se ha una forma ammessa."""
    if _is_scalar(v):
        return v
    if _is_pairs(v):
        return v
    if (
        isinstance(v, (list, tuple)) and len(v) == 2
        and _is_scalar(v[0]) and _is_scalar(v[1])
    ):
        return v
    if isinstance(v, dict) and _is_pairs(v.get("points")):
        return v
    raise ValueError(
        f"expr: '{name}' ha una forma non riconosciuta ({v!r}) — in scope "
        "solo scalari o forme statiche di Env (niente nodi-generatore)."
    )


def _map_y(env: Any, fn) -> Any:
    """L'Env con ``fn`` applicata a ogni y, tempi e forma intatti."""
    if isinstance(env, dict):
        return {**env, "points": [[t, fn(y)] for t, y in env["points"]]}
    if _is_pairs(env):
        return [[t, fn(y)] for t, y in env]
    a, b = env  # shorthand [a, b]
    return [fn(a), fn(b)]


def _eval(node: ast.AST, scope: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if not _is_scalar(node.value):
            raise ValueError(f"expr: costante non numerica {node.value!r}.")
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in scope:
            names = ", ".join(sorted(scope)) or "nessuno"
            raise ValueError(
                f"expr: nome ignoto '{node.id}' (disponibili: {names})."
            )
        return _checked(node.id, scope[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand, scope)
        if isinstance(node.op, ast.UAdd):
            return v
        return _map_y(v, operator.neg) if not _is_scalar(v) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        op = _BINOPS[type(node.op)]
        left = _eval(node.left, scope)
        right = _eval(node.right, scope)
        left_env, right_env = not _is_scalar(left), not _is_scalar(right)
        if left_env and right_env:
            raise ValueError(
                "expr: operazione tra due Env non supportata "
                "(solo Env con scalare)."
            )
        if left_env:
            return _map_y(left, lambda y: op(y, right))
        if right_env:
            return _map_y(right, lambda y: op(left, y))
        return op(left, right)
    raise ValueError(
        f"expr: costrutto non ammesso {ast.unparse(node)!r} "
        "(solo numeri, nomi, + - * / **, parentesi)."
    )


def _rebuild(v: Any) -> Any:
    """Copia del risultato con i float arrotondati a 9 decimali."""
    if isinstance(v, float):
        return round(v, 9)
    if isinstance(v, int):
        return v
    if isinstance(v, dict):
        return {**v, "points": [[_rebuild(t), _rebuild(y)] for t, y in v["points"]]}
    return [_rebuild(x) for x in v]
