"""Processo ``versions``: repliche dello stack distribuite nel tempo.

Il quarto blocco accanto ad ``axes``/``stack``/``sweep``: dichiara variabili
(vocabolario dei generatori Y: ``values`` / ``ramp`` / banda con ``n``) i cui
valori vengono iniettati negli scope ``let`` dei nodi-expr del documento. Ogni
combinazione (prodotto cartesiano lessicografico nell'ordine di dichiarazione,
prima variabile esterna/lenta) genera una *versione*: la replica completa
degli stream dello stack — envelope, camminate e seed identici — con lo
``stream_id`` suffissato con i valori della combinazione. Le versioni si
ascoltano cosi' dentro un unico documento engine, senza rimappare nessun
envelope: ogni stream conserva il proprio ``time_mode: normalized`` sulla
propria durata, e l'engine dimensiona il buffer su ``max(onset + duration)``.

Sulla timeline le versioni si posizionano con le chiavi riservate ``onset``/
``duration`` del blocco (issue #26): sequenze lunghe N (numero di combo),
fuori dal prodotto cartesiano, mappate 1:1 sulle versioni — ``onset[k]``
assoluto, ``duration[k]`` default di versione (una duration per-stream vince).
Chiavi assenti -> le versioni si concatenano sulle durate di versione (col
solo ``duration:`` top-level e' il classico ``onset = k * duration``).
Sovrapposizioni e buchi sono legittimi: il merge degli stem fa overlay-add.

Il blocco richiede ``stack:`` (le versioni sono repliche dello stack), ma e'
un processo indipendente con output proprio (``yaml/versions/versions.yml``:
``yaml/stack/stack.yml`` resta il materiale com'e' scritto, senza repliche —
e' l'istanza di partenza del percorso); ``duration:`` top-level e' un
default, serve solo quando nessun'altra fonte risolve durate e posizioni.
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
from . import gainmap
from .stack import build_stack_stream
from .study_spec import resolve_streams
from .sweep import _fmt
from .value_generators import expand_params, band, ramp, stable_seed, y_generator
from .yaml_builder import build_multi_document
from .yaml_loc import Locations

# Nomi che il sistema fornisce gia' agli scope expr (``i``/``n`` dello spread,
# le costanti): una variabile di versions con questi nomi sarebbe ambigua.
_RESERVED_NAMES = frozenset({"i", "n", "pi", "e"})

# Chiavi riservate del blocco ``versions:`` (issue #26): non sono variabili di
# scope — non entrano nel prodotto cartesiano ne' nella guardia "referenziata"
# — ma generatori della timeline: sequenze lunghe N (numero di combinazioni)
# mappate 1:1 sull'ordine lessicografico delle versioni.
_TIMELINE_KEYS = ("onset", "duration")

# ``chunk`` (opzionale): un intero, non un generatore. Se presente, il
# raggruppamento in documenti di ``generate_versions_documents`` non segue
# piu' la prima variabile dichiarata ma taglia il prodotto cartesiano piatto
# (nell'ordine lessicografico di ``version_combos``) in blocchi da ``chunk``
# combinazioni: cosi' ogni documento attraversa entrambe le variabili invece
# di fissarne una.
_CHUNK_KEY = "chunk"
_RESERVED_KEYS = _TIMELINE_KEYS + (_CHUNK_KEY,)


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
    variabili diverse decorrelate da sole. Le chiavi riservate ``onset``/
    ``duration`` non sono variabili: le legge ``parse_version_timeline``.
    """
    ctx = ErrCtx(locs=locs)
    raw = data.get("versions")
    if not isinstance(raw, dict) or not raw:
        raise ctx.err(
            "versions: serve un dict non vuoto {variabile: generatore}.",
            key=("versions",),
            hint="es. 'versions: {d: {values: [1, 2, 3]}}'.",
        )
    raw = {k: v for k, v in raw.items() if k not in _RESERVED_KEYS}
    if not raw:
        raise ctx.err(
            "versions: servono variabili oltre alle chiavi riservate "
            "'onset'/'duration'/'chunk' (sono loro a decidere quante "
            "versioni esistono).",
            key=("versions",),
            hint="dichiara almeno una variabile, es. 'd: {values: [1, 2, 3]}'.",
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


def _timeline_sequence(
    name: str, cfg: Any, n: int, sid: str, ctx: ErrCtx
) -> List[float]:
    """Risolve una chiave riservata (``onset``/``duration``) in N valori.

    Stesso vocabolario delle variabili (``values``/``ramp``/banda), ma il
    conteggio lo possiede il prodotto cartesiano: ``values`` deve avere
    esattamente N elementi; la banda deduce ``n = N`` (unico punto del
    progetto dove n e' deducibile) e un ``n`` esplicito diverso e' errore;
    ``ramp`` senza ``step`` distribuisce N valori equispaziati start -> stop,
    con ``step`` la griglia generata deve contare esattamente N. Una banda
    senza ``seed`` deriva ``stable_seed("<study>:versions:<nome>")``.
    """
    key = ("versions", name)
    if not isinstance(cfg, dict):
        raise ctx.err(
            f"versions: '{name}' deve avere un generatore (dict), "
            f"trovato {cfg!r}.",
            key=key,
            hint="dichiara 'values', 'ramp' o una banda ('base'/'range').",
        )
    with ctx.wrapping(key=key):
        gen_key, params = y_generator(cfg)
    seed = stable_seed(f"{sid}:versions:{name}")
    with ctx.wrapping(key=key):
        if gen_key == "values":
            values: List[Any] = list(params)
        elif gen_key == "ramp":
            if "step" in params:
                values = ramp(**expand_params(params, seed=seed))
            else:
                if "start" not in params or "stop" not in params:
                    raise ctx.err(
                        f"versions: '{name}', la rampa richiede 'start' e "
                        "'stop'.",
                        key=key,
                    )
                start, stop = params["start"], params["stop"]
                values = [
                    start + (stop - start) * k / (n - 1) for k in range(n)
                ] if n > 1 else [start]
        else:  # band
            band_params = dict(params)
            if band_params.setdefault("n", n) != n:
                raise ctx.err(
                    f"versions: '{name}', 'n' e' {band_params['n']} ma le "
                    f"versioni sono {n} — il conteggio lo possiede il "
                    "prodotto cartesiano delle variabili.",
                    key=key,
                    hint="ometti 'n': per le chiavi riservate e' dedotto.",
                )
            band_params.setdefault("seed", seed)
            values = band(
                **expand_params(band_params, seed=band_params["seed"])
            )
    if len(values) != n:
        raise ctx.err(
            f"versions: '{name}' genera {len(values)} valori ma le versioni "
            f"sono {n} (la sequenza si mappa 1:1 sulle combinazioni).",
            key=key,
        )
    for v in values:
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise ctx.err(
                f"versions: '{name}', valore non numerico {v!r}.", key=key
            )
        if name == "onset" and v < 0:
            raise ctx.err(
                f"versions: onset deve essere >= 0 (generato {v}).", key=key
            )
        if name == "duration" and v <= 0:
            raise ctx.err(
                f"versions: duration deve essere > 0 (generato {v}).", key=key
            )
    return [float(v) for v in values]


def parse_version_timeline(
    data: Dict[str, Any], n: int, locs: Locations | None = None
) -> tuple[List[float] | None, List[float] | None]:
    """Risolve le chiavi riservate ``onset``/``duration`` di ``versions:``.

    Ritorna ``(onsets, durations)``, ognuno una lista lunga ``n`` o ``None``
    se la chiave e' assente. ``onset[k]`` e' la posizione **assoluta** della
    versione k sulla timeline (non monotono legittimo: sovrapposizioni e
    buchi emergono dai valori); ``duration[k]`` fa da default di ``duration:``
    per gli stream della versione k.
    """
    ctx = ErrCtx(locs=locs)
    raw = data.get("versions") or {}
    sid = data.get("study_id") or "study"
    out = {}
    for name in _TIMELINE_KEYS:
        cfg = raw.get(name)
        out[name] = (
            None if cfg is None else _timeline_sequence(name, cfg, n, sid, ctx)
        )
    return out["onset"], out["duration"]


def version_combos(
    vars: Dict[str, List[Any]], *, interleaved: bool = False
) -> List[Dict[str, Any]]:
    """Prodotto cartesiano delle variabili.

    Di default lessicografico: l'ordine di dichiarazione conta, la prima
    variabile e' esterna (lenta), l'ultima interna (veloce) — come gli
    ``orderings`` dello sweep. Con ``interleaved=True`` (attivato da
    ``versions.chunk``, v. ``_build_versions``) nessuna variabile resta
    ferma per un intero giro delle altre: le combinazioni sono ordinate per
    somma degli indici crescente (traversata diagonale della griglia), cosi'
    un ``chunk`` attraversa sempre entrambi gli assi invece di scorrere solo
    quella interna a variabile esterna fissa.
    """
    names = list(vars)
    if not interleaved:
        return [
            dict(zip(names, picked))
            for picked in itertools.product(*(vars[n] for n in names))
        ]
    ranges = [range(len(vars[n])) for n in names]
    idx_combos = sorted(itertools.product(*ranges), key=lambda idxs: (sum(idxs), idxs))
    return [
        dict(zip(names, (vars[n][i] for n, i in zip(names, idxs))))
        for idxs in idx_combos
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


def _build_versions(
    data: Dict[str, Any],
    study_id: str | None = None,
    locs: Locations | None = None,
    *,
    output_sr: Optional[int] = 48000,
    samples_dir: Optional[str] = None,
) -> tuple[str, List[tuple[str, Dict[str, Any]]]]:
    """Gli stream di tutte le versioni, ognuno con l'etichetta del suo gruppo.

    Cuore condiviso da ``generate_versions_document`` (un documento solo) e
    ``generate_versions_documents`` (uno per gruppo).

    Per ogni combinazione: iniezione nello scope, risoluzione degli stream
    (``resolve_streams``, il parse di sempre), costruzione via
    ``build_stack_stream`` — identica allo stack — poi ``stream_id``
    suffissato con l'etichetta della combinazione (``fermo__d=1``) e onset
    spostato sulla posizione della versione.

    Le chiavi riservate ``onset``/``duration`` del blocco (issue #26)
    posizionano le versioni: ``onset[k]`` e' assoluto (l'onset per-stream
    resta relativo alla propria versione: ``onset_finale = onset_versione +
    onset_stream``); ``duration[k]`` viene iniettata come ``duration:`` del
    documento della combo k *prima* di ``resolve_streams``, quindi fa da
    default e una duration per-stream vince comunque. Chiavi assenti ->
    concatenazione: ``onset_versione[k]`` e' la somma delle durate delle
    versioni precedenti (col solo ``duration:`` top-level, il classico
    ``k * duration``). La durata documento e' ``max(onset + duration)`` sugli
    stream costruiti: versioni sovrapposte o bucate sono legittime.
    """
    sid = study_id or data.get("study_id") or "study"
    ctx = ErrCtx(locs=locs)
    if "stack" not in data:
        raise ctx.err(
            "versions: richiede il blocco 'stack:' (le versioni sono "
            "repliche dello stack).",
            key=("versions",),
            hint="aggiungi 'stack: {}' (anche vuoto) al documento.",
        )
    raw_versions = data.get("versions") or {}
    chunk = raw_versions.get(_CHUNK_KEY)
    if chunk is not None and (
        not isinstance(chunk, int) or isinstance(chunk, bool) or chunk < 1
    ):
        raise ctx.err(
            f"versions: 'chunk' deve essere un intero >= 1, trovato {chunk!r}.",
            key=("versions", "chunk"),
        )
    vars = parse_versions(data, locs=locs)
    combos = version_combos(vars, interleaved=chunk is not None)
    onsets, durations = parse_version_timeline(data, len(combos), locs=locs)
    if onsets is None:
        # Concatenazione: servono le durate di versione per posizionare.
        top = data.get("duration")
        per_version = durations if durations is not None else (
            [float(top)] * len(combos) if top is not None else None
        )
        if per_version is None:
            raise ctx.err(
                "versions: senza 'versions.onset' serve una durata di "
                "versione per concatenare — 'versions.duration' oppure "
                "'duration:' top-level.",
                key=("versions",),
                hint="aggiungi 'duration: <secondi>' al top del documento, "
                "o le chiavi riservate 'duration'/'onset' nel blocco.",
            )
        onsets = []
        acc = 0.0
        for d in per_version:
            onsets.append(acc)
            acc += d
    base_data = {k: v for k, v in data.items() if k != "versions"}

    if chunk is not None:
        n_groups = -(-len(combos) // chunk)  # ceil
        pad = len(str(n_groups - 1))
    outer = next(iter(vars))  # prima variabile = esterna/lenta: il gruppo di default
    built: List[tuple[str, Dict[str, Any]]] = []
    for k, combo in enumerate(combos):
        label = "__".join(f"{name}={_fmt(v)}" for name, v in combo.items())
        group = f"chunk={k // chunk:0{pad}d}" if chunk is not None else f"{outer}={_fmt(combo[outer])}"
        data_k = inject_combo(base_data, combo)
        if durations is not None:
            data_k["duration"] = durations[k]
        for spec in resolve_streams(data_k, sid, locs=locs):
            s = build_stack_stream(spec, output_sr=output_sr)
            s["stream_id"] = f"{s['stream_id']}__{label}"
            s["onset"] = (s.get("onset") or 0) + onsets[k]
            built.append((group, s))
    # La compensazione sta qui, *prima* del raggruppamento in documenti: il
    # riferimento e' comunque per-versione (le versioni concatenate non si
    # sovrappongono, quindi ognuna si normalizza da se'), ma la traslazione in
    # sottrazione e' unica per l'intero prodotto cartesiano. Compensando dopo
    # lo split, ogni file riceverebbe uno shift diverso e i gruppi non
    # sarebbero piu' confrontabili fra loro all'ascolto.
    gain = gainmap.parse_config(data)
    if gain and samples_dir:
        gainmap.compensate(
            [s for _, s in built],
            samples_dir=samples_dir,
            output_sr=output_sr or 48000,
            **gain,
        )
    return sid, built


def _versions_document(
    data: Dict[str, Any], sid: str, streams: List[Dict[str, Any]], title: str
) -> Dict[str, Any]:
    return build_multi_document(
        streams,
        title=title,
        seed=data.get("seed"),
        duration=max(s["onset"] + s["duration"] for s in streams),
    )


def generate_versions_document(
    data: Dict[str, Any],
    study_id: str | None = None,
    locs: Locations | None = None,
    *,
    output_sr: Optional[int] = 48000,
    samples_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Tutte le versioni in un solo documento (timeline completa).

    E' la vista non spezzata: la produzione passa da
    ``generate_versions_documents``.
    """
    sid, built = _build_versions(
        data, study_id, locs, output_sr=output_sr, samples_dir=samples_dir
    )
    return _versions_document(
        data, sid, [s for _, s in built], f"{sid} :: stack :: versions"
    )


def generate_versions_documents(
    data: Dict[str, Any],
    study_id: str | None = None,
    locs: Locations | None = None,
    *,
    output_sr: Optional[int] = 48000,
    samples_dir: Optional[str] = None,
) -> List[tuple[str, Dict[str, Any]]]:
    """Un documento per gruppo (default: per valore della **variabile esterna**).

    Il prodotto cartesiano di ``versions:`` cresce in fretta e un documento
    unico diventa un audio da decine di minuti, ingestibile da aprire e da
    ascoltare. Senza ``versions.chunk`` il raggruppamento usa la prima
    variabile dichiarata (esterna/lenta, v. ``version_combos``) come confine
    naturale di file: con ``d`` x ``g`` escono N_d documenti, ciascuno con
    le sole combo di quel ``d`` — utile ma fissa una variabile per documento.

    Con ``versions.chunk: N`` il raggruppamento ignora le variabili e taglia
    il prodotto cartesiano piatto (ordine lessicografico di ``version_combos``)
    in blocchi da N combinazioni consecutive: ogni documento attraversa cosi'
    entrambe le variabili, invece di sentirne muovere una sola per file.

    Ogni documento e' **ribasato a zero** (si sottrae l'onset minimo del
    gruppo), cosi' apre da solo senza silenzio iniziale; le posizioni
    relative dentro il gruppo — comprese quelle dettate da ``versions.onset``
    esplicito, sovrapposizioni e buchi inclusi — restano intatte.

    Ritorna coppie ``(etichetta, documento)`` con etichetta ``"d=3"``,
    nell'ordine delle versioni.
    """
    sid, built = _build_versions(
        data, study_id, locs, output_sr=output_sr, samples_dir=samples_dir
    )
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for group, s in built:
        groups.setdefault(group, []).append(s)
    out = []
    for group, streams in groups.items():
        off = min(s["onset"] for s in streams)
        for s in streams:
            s["onset"] -= off
        out.append(
            (group, _versions_document(
                data, sid, streams, f"{sid} :: stack :: versions :: {group}"
            ))
        )
    return out
