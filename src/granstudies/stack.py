"""Processo ``stack``: N stream con lievi variazioni, sommati in un documento.

Il gemello verticale dello sweep. Dove sweep *esplode* gli stream in N file
(varianti enumerate, prodotto cartesiano), stack li *collassa* in un solo YAML
multi-stream. L'invariante: ``axes`` conosce solo Y (valori + interpolation);
il processo possiede X — sweep via plateau/transition (durata derivata), stack
via le strategy-X (``x_strategies``) normalizzate sulla durata condivisa letta
da ``duration:``.

In stack gli assi NON si combinano: niente prodotto cartesiano, niente zip.
Ogni asse di uno stream diventa un envelope indipendente sulla stessa durata,
coi suoi valori (Y), i suoi tempi (X) e la sua curva (interpolation).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .value_generators import GENERATORS, rand_at
from .x_strategies import rand as x_rand
from .x_strategies import resolve_x, x_owns_n

# Le chiavi-generatore di Y ammesse in un asse (vocabolario condiviso con sweep).
_Y_KEYS = frozenset({"values", *GENERATORS})


def _y_generator(y_cfg: Dict[str, Any]) -> tuple[str, Any]:
    """Estrae (nome, params) dell'unica chiave-generatore Y di un asse."""
    keys = [k for k in y_cfg if k in _Y_KEYS]
    if len(keys) != 1:
        opts = ", ".join(sorted(_Y_KEYS))
        raise ValueError(
            f"stack: serve esattamente una chiave-generatore Y tra {{{opts}}}, "
            f"trovate {sorted(keys) or 'nessuna'}."
        )
    return keys[0], y_cfg[keys[0]]


def axis_envelope(
    y_cfg: Dict[str, Any],
    x_cfg: Dict[str, Any] | None,
    duration: float,
    *,
    y_seed: int = 0,
    x_seed: int = 0,
) -> List[List[float]]:
    """Assembla l'envelope ``[[t, v], ...]`` di un asse: coupling X per Y.

    Due versi, decisi dalla n-ownership (validata in entrambi):

    - **X possiede n** (strategy ``rand``): i tempi emergono dalla frequenza
      (``x_strategies.rand``); la Y deve essere ``rand`` *senza* ``n`` e viene
      campionata ai tempi reali dei punti (``rand_at``). E' rspline.
    - **Y possiede n** (``values``/``ramp``/``rand`` con ``n``): i valori si
      risolvono per primi e la X distribuisce ``len(values)`` tempi
      (``resolve_x``, default ``linear``).

    ``y_seed``/``x_seed`` sono i default globali gia' risolti a monte (catena di
    precedenza in ``study_spec``): il ``seed`` dichiarato dentro la config
    dell'asse vince sempre (default, non override brutale).
    """
    y_key, y_params = _y_generator(y_cfg)

    if x_owns_n(x_cfg):
        if y_key != "rand" or "n" in y_params:
            raise ValueError(
                "stack: la strategy-X 'rand' possiede n — la Y deve essere "
                f"'rand' senza 'n' (trovata '{y_key}'"
                + (" con 'n'" if y_key == "rand" and "n" in y_params else "")
                + ")."
            )
        x_params = dict(x_cfg["rand"])
        x_params.setdefault("seed", x_seed)
        times = x_rand(duration=duration, **x_params)
        y_kwargs = dict(y_params)
        y_kwargs.setdefault("seed", y_seed)
        values = rand_at(times, **y_kwargs)
        return [[t, v] for t, v in zip(times, values)]

    if y_key == "rand" and "n" not in y_params:
        raise ValueError(
            "stack: Y 'rand' senza 'n' richiede la strategy-X 'rand' "
            "(e' la X a possedere n); con X lineare dichiara 'n' nella Y."
        )
    if y_key == "values":
        values = list(y_params)
    else:
        y_kwargs = dict(y_params)
        if y_key == "rand":
            y_kwargs.setdefault("seed", y_seed)
        values = GENERATORS[y_key](**y_kwargs)
    times = resolve_x(x_cfg, n=len(values))
    return [[t, v] for t, v in zip(times, values)]
