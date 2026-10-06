"""Bounds dei parametri per clamping e normalizzazione delle distanze.

Tutti i bounds vengono dall'engine — single source of truth, niente tabelle
copiate: il registry ``parameter_definitions.GRANULAR_PARAMETERS`` per i
parametri registrati (mappa path->chiave derivata da ``ALL_SCHEMAS``),
``PitchUnit.value_bounds`` per i path ``pitch.<unita'>``, che unit-driven non
sono nel registry.

Le chiavi sono i path YAML *dotted* (es. ``grain.duration``), come usati nello
``study.yml`` e nelle definizioni di stato.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional, Tuple

# Path noti al registry dell'engine ma assenti da ``ALL_SCHEMAS`` (non hanno
# una voce di schema YAML): unica tabella rimasta a mano. Tutto il resto viene
# da ``engine_bridge.parameter_schema_paths``.
#
# La chiave e' il path dove l'engine *legge* il valore, non il nome del
# registry: ``num_voices``/``scatter`` stanno nel blocco ``voices:``
# (``Stream._init_voice_manager``). ``pointer_deviation`` resta fuori: il suo
# valore non ha una chiave YAML (``_dummy_fixed_zero_``) e la sola manopola,
# la banda ``pointer.offset_range``, ha i bounds ``min_range``/``max_range``,
# non quelli del valore che ``bounds_for`` legge.
_EXTRA_PATHS: Dict[str, str] = {
    "voices.num_voices": "num_voices",
    "voices.scatter": "scatter",
}

_PITCH_PREFIX = "pitch."


@lru_cache(maxsize=1)
def _path_map() -> Dict[str, str]:
    """path YAML dotted -> chiave nel registry, derivata dagli schema engine."""
    from .engine_bridge import parameter_bounds, parameter_schema_paths

    registry = parameter_bounds()
    # ``pointer.start`` sta negli schema ma non nel registry: nessun bound da
    # confrontare, quindi resta fuori dai path noti.
    return {
        **{p: k for p, k in parameter_schema_paths().items() if k in registry},
        **_EXTRA_PATHS,
    }


# Unita' ammesse per ``grain.duration``/``grain.duration_range``, come
# l'engine (``pge.core.stream.GRAIN_DURATION_UNITS``). I bounds del registry
# sono in secondi: qui vive la conversione verso quel dominio.
GRAIN_DURATION_UNITS = ("seconds", "samples", "milliseconds")

# Unita' ammesse per ``pointer.loop_unit``, come l'engine
# (``pge.parameters.loop_unit.LOOP_UNITS`` da PGE #246; prima in
# ``pge.controllers.pointer_controller``). ``seconds`` e'
# la grafia canonica, ``absolute`` l'alias storico — stessa lettura, valori
# gia' in secondi assoluti. Fuori di qui l'engine alza
# ``InvalidFieldValueError``: la chiave e' scritta, quindi il refuso va
# nominato invece di ricadere in silenzio su "assoluto".
LOOP_UNITS = ("seconds", "absolute", "normalized")

# L'unita' che vale quando ``loop_unit`` e' assente. Da PGE v9 (engine #222)
# NON eredita piu' da ``time_mode``: le due chiavi governano assi diversi con
# riferimenti diversi — ``time_mode`` scala l'asse X (tempo) degli envelope
# sulla duration dello stream, ``loop_unit`` l'asse Y (valore) sulla durata
# del file audio.
LOOP_UNIT_DEFAULT = "seconds"

# Le chiavi del blocco pointer che ``loop_unit`` interpreta: lo stesso
# ``LOOP_UNIT_SCOPE`` dell'engine (``pge.parameters.loop_unit`` da PGE #246;
# prima ``_LOOP_UNIT_SCOPE`` del PointerController). ``start`` e' fra
# queste benche' loop non sia — e' una posizione nel sample come loop_start,
# stesso dominio e stessa unita'.
LOOP_UNIT_SCOPE = ("start", "loop_start", "loop_end", "loop_dur")

_LOOP_SCALED_PATHS = frozenset(f"pointer.{k}" for k in LOOP_UNIT_SCOPE)

# Le letture di ``loop_unit`` in cui il valore e' gia' in secondi, cioe'
# confrontabile coi bounds del registry cosi' com'e'.
_LOOP_UNITS_IN_SECONDS = tuple(u for u in LOOP_UNITS if u != "normalized")

_MS_PER_SECOND = 1000.0


def grain_duration_factor(
    unit: Optional[str],
    output_sr: Optional[int] = None,
) -> float:
    """Fattore che porta un valore di ``grain.duration`` in secondi.

    ``seconds`` (o unita' assente) -> 1.0; ``milliseconds`` -> 1e-3;
    ``samples`` -> ``1/output_sr``, l'unica unita' che dipende dal sample rate
    e quindi l'unica che pretende ``output_sr``.
    """
    if unit is None or unit == "seconds":
        return 1.0
    if unit == "milliseconds":
        return 1.0 / _MS_PER_SECOND
    if unit == "samples":
        if output_sr is None:
            raise ValueError("l'unita' 'samples' richiede output_sr")
        return 1.0 / output_sr
    raise ValueError(
        f"unita' di grain.duration sconosciuta: {unit!r} "
        f"(ammesse: {list(GRAIN_DURATION_UNITS)})"
    )


def known_paths() -> frozenset:
    """Tutti i path dotted noti: registry engine + le unita' di ``pitch.*``."""
    from .engine_bridge import pitch_units

    return frozenset(_path_map()) | frozenset(
        _PITCH_PREFIX + u for u in pitch_units()
    )


# Path il cui dominio non e' un intervallo ma un elenco di nomi: i bounds non
# li descrivono (il registry da' a ``grain.envelope`` un (0, 0) che non dice
# niente di una finestra), il catalogo dell'engine si'. Stessa regola dei
# bounds: nessuna tabella copiata qui, solo il ponte verso
# ``engine_bridge``.
_CATEGORICAL: Dict[str, str] = {
    "grain.envelope": "window_names",
}


def categorical_domain(path: str) -> Optional[frozenset]:
    """I nomi ammessi per un path categoriale, o ``None`` se il path non lo e'.

    Un asse su un path categoriale enumera stringhe (``[hanning, expodec, ...]``)
    invece di numeri: e' il dominio che lo dice, non il tipo dei valori scritti.
    Su un path categoriale ``violation``/``clamp`` non confrontano nulla.
    """
    fn = _CATEGORICAL.get(path)
    if fn is None:
        return None
    from . import engine_bridge

    return getattr(engine_bridge, fn)()


# Path il cui dominio e' un insieme finito di *numeri*: i bounds del registry
# ne sono l'inviluppo, non il dominio. ``grain.read_direction`` (engine #207)
# ha bounds (-1, 1) ma ammette solo -1 e +1: ``0.3`` non e' un verso e ``0``
# non ha segno, e l'engine li rifiuta al parse invece di arrotondarli
# (``pge.parameters.read_direction``). Stessa regola dei categoriali: nessuna
# tabella copiata qui, l'insieme lo dice l'engine.
_DISCRETE: Dict[str, str] = {
    "grain.read_direction": "read_direction_values",
}


def discrete_domain(path: str) -> Optional[frozenset]:
    """I numeri ammessi per un path a dominio discreto, o ``None`` se il path
    non lo e'.

    Un asse su un path discreto enumera i suoi valori (``values: [-1, 1]``):
    ``ramp`` e la banda possono produrre valori fra un elemento e l'altro,
    dove l'engine non ha niente da renderizzare. ``violation``/``clamp``
    applicano i bounds come su ogni path, ma sono solo l'inviluppo: un valore
    dentro i bounds e fuori dall'insieme lo ferma ``study_spec``, contro questo
    insieme.
    """
    fn = _DISCRETE.get(path)
    if fn is None:
        return None
    from . import engine_bridge

    return getattr(engine_bridge, fn)()


def bounds_for(
    path: str,
    output_sr: Optional[int] = None,
) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """(min, max) per un path, o ``None`` se sconosciuto.

    I bounds vengono dall'engine: il registry dei parametri per i path di
    ``ALL_SCHEMAS``, ``PitchUnit.value_bounds`` per i path ``pitch.<unita'>``
    (l'ultimo segmento e' il nome dell'unita', come nel blocco ``pitch:`` dello
    YAML).

    ``max`` puo' essere ``None`` (bound dinamico nell'engine): il tetto dei
    ``loop_*`` e' la durata del sample, che qui non si conosce, quindi in
    secondi di quelli si valida solo il minimo. Sotto ``normalized`` il tetto
    torna noto (1, la fine del file) e il minimo diventa un pavimento a 0
    (vedi ``_bounds_in_unit``).

    ``output_sr`` di default e' quello di render dell'engine, cosi' il minimo di
    ``grain.duration`` e' sempre il pavimento dinamico (1 campione) e mai il
    fallback statico di 1 ms: ometterlo non deve cambiare il verdetto (issue #17).
    """
    if path.startswith(_PITCH_PREFIX):
        from .engine_bridge import pitch_bounds, pitch_units

        unit = path[len(_PITCH_PREFIX):]
        if unit not in pitch_units():
            return None
        pb = pitch_bounds(unit)
        return (pb.min_val, pb.max_val)
    key = _path_map().get(path)
    if key is None:
        return None
    from .engine_bridge import parameter_bounds

    sr = output_sr or default_output_sr()
    pb = parameter_bounds(output_sr=sr)[key]
    return (pb.min_val, pb.max_val)


def default_output_sr() -> int:
    """Sample rate di render di default dell'engine (single source)."""
    from .engine_bridge import default_output_sr as _sr

    return _sr()


def declared_unit(path: str, doc: Dict) -> Optional[str]:
    """L'unita' in cui ``doc`` esprime il valore di ``path``, se la dichiara.

    ``grain.duration`` la legge da ``grain.duration_unit`` (``stream.py:415``),
    le posizioni di ``LOOP_UNIT_SCOPE`` da ``pointer.loop_unit``; sugli altri
    path nessuna chiave dichiara un'unita' e il ritorno e' ``None``. E'
    l'argomento ``unit`` di ``violation``/``clamp``: chi chiama non deve
    sapere quale chiave governa quale path.
    """
    if path == "grain.duration":
        block, key = "grain", "duration_unit"
    elif path in _LOOP_SCALED_PATHS:
        block, key = "pointer", "loop_unit"
    else:
        return None
    sub = doc.get(block)
    return sub.get(key) if isinstance(sub, dict) else None


def is_sample_fraction(path: str, unit: Optional[str]) -> bool:
    """True se il valore di ``path`` e' una frazione della durata del sample.

    Vale per le posizioni di ``LOOP_UNIT_SCOPE`` sotto ``loop_unit:
    normalized`` (``unit`` e' quella di ``declared_unit``): li' ``violation``
    ritorna i bounds in frazioni, non in secondi.
    """
    return path in _LOOP_SCALED_PATHS and unit == "normalized"


def _sample_fraction_bounds(
    path: str, lo: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    """Bounds di una posizione nel sample in frazioni della sua durata.

    L'engine riscala la frazione per ``sample_dur_sec`` e poi applica i bounds
    in secondi ``[min_val, sample_dur_sec]``: in frazioni sono
    ``[min_val / sample_dur_sec, 1]``. La durata qui non si conosce, ma:

    - il tetto e' proporzionale alla durata, quindi in frazioni non ne dipende:
      e' il max dell'engine a ``sample_dur_sec=1``, la fine del file. Oltre,
      l'engine clamperebbe in silenzio;
    - la scala e' positiva e non cambia il segno: un minimo >= 0 in secondi
      rifiuta ogni frazione negativa, che l'engine altrimenti porterebbe al
      minimo in silenzio. Il pavimento e' 0 — esatto per ``loop_start``/
      ``loop_end`` (minimo 0), largo per ``loop_dur``, il cui minimo (0.005 s)
      in frazioni dipende dal file e non si confronta (rifiuterebbe una
      frazione che l'engine accetta). Resta fuori proprio ``loop_dur: 0``:
      sotto il minimo su qualunque file, ma senza un valore ammesso noto a cui
      ``clamp`` possa portarlo.
    """
    from .engine_bridge import parameter_bounds

    ceiling = parameter_bounds(sample_dur_sec=1.0)[_path_map()[path]].max_val
    floor = 0 if lo is not None and lo >= 0 else None
    return floor, ceiling


def _bounds_in_unit(
    path: str,
    *,
    unit: Optional[str] = None,
    output_sr: Optional[int] = None,
) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """Bounds del path riportati nell'unita' del valore da confrontare.

    ``unit`` e' quella che ``declared_unit`` legge per il path: la
    ``grain.duration_unit`` per ``grain.duration``, la ``loop_unit`` per le
    posizioni nel sample; sugli altri path viene ignorato.

    Le posizioni nel sample hanno bounds in secondi che l'engine applica dopo
    aver riscalato il valore secondo ``loop_unit``. Sotto ``normalized`` il
    valore e' una frazione della durata del sample e i bounds si riportano in
    frazioni (vedi ``_sample_fraction_bounds``). Un'unita' fuori vocabolario:
    ``None``, nessun confronto — l'engine la rifiuta per conto suo (come
    ``gainmap``, che non la stima).

    Un path categoriale (``categorical_domain``) non ha un intervallo: ``None``,
    il valore e' un nome e la sua ammissione la decide il catalogo, al parse.
    """
    if path in _CATEGORICAL:
        return None
    sr = output_sr or default_output_sr()
    if path in _LOOP_SCALED_PATHS:
        b = bounds_for(path, output_sr=sr)
        if b is None:
            return None
        if unit is None or unit in _LOOP_UNITS_IN_SECONDS:
            return b
        if unit != "normalized":
            return None
        return _sample_fraction_bounds(path, b[0])
    b = bounds_for(path, output_sr=sr)
    if b is None:
        return None
    lo, hi = b
    factor = grain_duration_factor(
        unit if path == "grain.duration" else None, sr
    )
    if factor != 1.0:
        lo = None if lo is None else lo / factor
        hi = None if hi is None else hi / factor
    return lo, hi


def violation(
    path: str,
    value: float,
    *,
    unit: Optional[str] = None,
    output_sr: Optional[int] = None,
) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """I bounds del path se ``value`` li sfora, altrimenti ``None``.

    Unico punto in cui un valore si confronta coi bounds (su un path a dominio
    discreto sono l'inviluppo dell'insieme: l'ammissione la decide
    ``discrete_domain``, piu' stretto). Il confronto avviene
    nell'unita' di ``value`` (vedi ``_bounds_in_unit``), il ritorno e' nel
    dominio in cui i bounds sono dichiarati — secondi per ``grain.duration`` —
    perche' e' quello in cui ha senso mostrarli in un errore. Le frazioni del
    sample fanno eccezione (``is_sample_fraction``): in secondi i loro bounds
    non si scrivono senza la durata del file, e tornano in frazioni.
    """
    b = _bounds_in_unit(path, unit=unit, output_sr=output_sr)
    if b is None:
        return None
    lo, hi = b
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        if is_sample_fraction(path, unit):
            return b
        return bounds_for(path, output_sr=output_sr)
    return None


def clamp(
    path: str,
    value: float,
    *,
    output_sr: Optional[int] = None,
    unit: Optional[str] = None,
) -> float:
    """Riporta ``value`` entro i bounds del path (no-op se path sconosciuto).

    ``unit``: unita' in cui e' espresso ``value`` (vedi ``declared_unit``);
    il ritorno resta nell'unita' di partenza. Stesso confronto di
    ``violation``: ``clamp`` sposta un valore se e solo se quella lo rifiuta.
    """
    b = _bounds_in_unit(path, unit=unit, output_sr=output_sr)
    if b is None:
        return value
    lo, hi = b
    if lo is not None and value < lo:
        return lo
    if hi is not None and value > hi:
        return hi
    return value


def span(path: str) -> Optional[float]:
    """Ampiezza (max-min) di un path, per normalizzare le distanze.

    Ritorna ``None`` se i bounds non sono entrambi finiti.
    """
    b = bounds_for(path)
    if b is None:
        return None
    lo, hi = b
    if lo is None or hi is None:
        return None
    width = float(hi) - float(lo)
    return width if width > 0 else None
