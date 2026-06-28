"""Costruzione di YAML engine-compatibili da uno stream base + override.

Gli override sono espressi come path *dotted* (``grain.duration``) -> valore.
Il valore puo' essere uno scalare (variante statica) o una lista di breakpoint
``[[t, v], ...]`` (envelope, usato da ``compose``). In entrambi i casi viene
inserito nella posizione annidata corretta dello stream.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Mapping


def deep_set(d: Dict[str, Any], dotted_path: str, value: Any) -> None:
    """Imposta ``value`` in ``d`` seguendo un path dotted, creando i dict mancanti.

    Esempio: ``deep_set(s, "grain.duration", 0.2)`` -> ``s["grain"]["duration"] = 0.2``.
    """
    if not dotted_path:
        raise ValueError("dotted_path vuoto")
    keys = dotted_path.split(".")
    node = d
    for key in keys[:-1]:
        nxt = node.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            node[key] = nxt
        node = nxt
    node[keys[-1]] = value


def deep_get(d: Mapping[str, Any], dotted_path: str, default: Any = None) -> Any:
    """Legge un valore da un dict via path dotted (``default`` se assente)."""
    node: Any = d
    for key in dotted_path.split("."):
        if not isinstance(node, Mapping) or key not in node:
            return default
        node = node[key]
    return node


def build_stream(
    base_stream: Mapping[str, Any],
    overrides: Mapping[str, Any],
    *,
    envelope_time_mode: str | None = None,
) -> Dict[str, Any]:
    """Crea un nuovo dict stream = copia di ``base_stream`` con override applicati.

    Se ``envelope_time_mode`` e' valorizzato (es. ``"normalized"``), gli override
    *lista* (breakpoint ``[[t, v], ...]``) vengono wrappati nel dict envelope
    dell'engine ``{type: linear, points: ..., time_mode: <mode>}``. Lasciato a
    ``None`` (default) le liste passano grezze: cosi' la pipeline ``compose``
    (envelope assoluti) resta invariata.
    """
    stream = copy.deepcopy(dict(base_stream))
    for path, value in overrides.items():
        if envelope_time_mode is not None and isinstance(value, list):
            value = {
                "type": "linear",
                "points": value,
                "time_mode": envelope_time_mode,
            }
        deep_set(stream, path, value)
    return stream


def build_document(
    base_stream: Mapping[str, Any],
    overrides: Mapping[str, Any],
    *,
    title: str | None = None,
    seed: int | None = None,
    duration: float | None = None,
    envelope_time_mode: str | None = None,
) -> Dict[str, Any]:
    """Crea un documento YAML engine completo con un singolo stream.

    Le chiavi top-level (``title``, ``seed``, ``duration``) sono incluse solo se
    fornite, cosi' l'output resta minimale e diff-friendly. ``envelope_time_mode``
    e' inoltrato a ``build_stream`` per il wrapping degli envelope.
    """
    doc: Dict[str, Any] = {}
    if title is not None:
        doc["title"] = title
    if seed is not None:
        doc["seed"] = seed
    if duration is not None:
        doc["duration"] = duration
    doc["streams"] = [
        build_stream(base_stream, overrides, envelope_time_mode=envelope_time_mode)
    ]
    return doc
