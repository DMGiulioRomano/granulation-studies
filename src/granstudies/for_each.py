"""``for_each:`` — l'asse esterno: moltiplica i file, non i gradini.

Gli ``axes:`` di uno studio sono assi **interni**: scorrono nel tempo dentro
lo stesso file. ``for_each:`` e' l'asse **esterno**: ogni combinazione dei suoi
valori e' una **patch sullo ``study.yml``** e produce un render intero a se',
in ``generated/<study>/<label>/``.

    Interno se il confronto sta nella **giustapposizione** (lo senti cambiare
    mentre suona). Esterno se sta nel **riascolto** (devi risentire la stessa
    cosa da capo), o se la chiave definisce il file stesso — ``seed``,
    ``sample``, ``arco``, la durata.

La grammatica e' quella di ``versions:`` (assi ortogonali, prodotto cartesiano
lessicografico nell'ordine di dichiarazione), con due sole forme:

    for_each:
      base.distribution: {values: [0, 0.5, 1]}   # asse a manopola singola
      griglia:                                    # asse a stati nominati
        fitta: {axes.fill_factor.values: [0.5, 0.7, 0.85, 1, 2, 4, 8]}
        rada:  {axes.fill_factor.values: [0.5, 1, 4]}

Le chiavi delle patch sono **path puntati su tutto il documento**, non solo su
``base:``: e' cio' che rende esterno anche ``stack.seed`` o ``percorso.arco``,
che come assi interni non esisterebbero (la timeline *e'* il file). Il valore
viene **assegnato** al path, non fuso: ``base.grain: {...}`` sostituisce
l'intero sotto-albero. Il path si risolve sulle chiavi che il documento ha
davvero, quindi attraversa anche un nome d'asse dotted:
``axes.grain.duration.values`` raggiunge l'asse ``grain.duration``.

Il blocco assente e' la combinazione vuota — ``generated/<study>/`` piatto,
come uno studio senza ``for_each``: il caso degenere, non un ramo speciale.
"""
from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from .errors import ErrCtx
from .value_generators import _BAND_KEYS, Y_GENERATOR_KEYS, is_generator_node, resolve
from .yaml_loc import Locations

BLOCK = "for_each"

# Il vocabolario piatto di un generatore di sequenza: tutto il resto, accanto a
# un marcatore, e' una chiave che il generatore non conosce.
_GEN_VOCAB = _BAND_KEYS | Y_GENERATOR_KEYS | {"step", "curve"}


@dataclass(frozen=True)
class Combo:
    """Una combinazione: il nome della sua cartella e la patch che la produce."""

    label: str
    patch: tuple  # ((path, valore), ...) — hashable, ordine di dichiarazione

    @property
    def overrides(self) -> Dict[str, Any]:
        return dict(self.patch)


EMPTY = Combo(label="", patch=())


def parse(data: Dict[str, Any] | None, locs: Locations | None = None) -> List[Combo]:
    """Le combinazioni dichiarate dal documento, in ordine lessicografico.

    Senza blocco ``for_each:`` ritorna la sola combinazione vuota: chi itera
    non ha un ramo in meno da scrivere, e uno studio senza assi esterni resta
    esattamente com'era.
    """
    block = (data or {}).get(BLOCK)
    if block is None:
        return [EMPTY]
    ctx = ErrCtx(locs=locs)
    if not isinstance(block, dict) or not block:
        raise ctx.err(
            f"'{BLOCK}:' dev'essere un dict di assi non vuoto.",
            key=(BLOCK,),
            hint="un asse per riga: 'base.distribution: {values: [0, 0.5, 1]}', "
                 "oppure toglilo del tutto.",
        )
    axes = [_parse_axis(name, cfg, ctx) for name, cfg in block.items()]
    _reject_collisions(list(block), axes, ctx)
    combos: List[Combo] = []
    # Primo asse dichiarato = piu' esterno (varia piu' lentamente), come negli
    # `orderings` dello sweep e negli assi di `versions:`.
    for tup in itertools.product(*axes):
        patch: List[tuple] = []
        for part in tup:
            patch.extend(part.patch)
        combos.append(Combo(label="__".join(p.label for p in tup), patch=tuple(patch)))
    return combos


def apply(data: Dict[str, Any], combo: Combo, locs: Locations | None = None) -> Dict[str, Any]:
    """Il documento con la patch della combinazione applicata.

    Il blocco ``for_each:`` viene **rimosso**: da qui in giu' (stream, sweep,
    stack, versions, percorso) il documento e' uno studio normale, e nessun
    parser deve conoscere l'esistenza degli assi esterni.
    """
    out = copy.deepcopy(data) if data else {}
    out.pop(BLOCK, None)
    ctx = ErrCtx(locs=locs)
    for path, value in combo.patch:
        _set_path(out, path, value, ctx)
    return out


def labels(combos: List[Combo]) -> List[str]:
    return [c.label for c in combos]


# --- parse -----------------------------------------------------------------

def _parse_axis(axis: str, cfg: Any, ctx: ErrCtx) -> List[Combo]:
    # Import locale: ``sweep`` tira dentro l'intero parse dello studio (e con
    # esso soundfile), e questo modulo lo importa anche la CLI a freddo.
    from .sweep import _fmt

    key = (BLOCK, axis)
    _reject_stato_generatore(axis, cfg, ctx, key)
    # Forma 1 — manopola singola: la chiave dell'asse *e'* il path da patchare,
    # il valore un generatore di sequenza (o una lista nuda).
    if is_generator_node(cfg) or isinstance(cfg, list):
        with ctx.wrapping(key=key, axis=axis):
            values = resolve({"values": cfg} if isinstance(cfg, list) else cfg)
        if not values:
            raise ctx.err(f"{BLOCK}: l'asse '{axis}' non produce nessun valore.", key=key)
        out = []
        for v in values:
            if not _is_scalar(v):
                raise ctx.err(
                    f"{BLOCK}: l'asse '{axis}' ha un valore non scalare, che non "
                    "puo' diventare un nome di cartella.",
                    key=key,
                    hint="dagli un nome tu, con un asse a stati nominati: "
                         f"'{_short(axis)}: {{rada: {{{axis}: [...]}}}}'.",
                )
            out.append(Combo(label=f"{_short(axis)}={_slug(_fmt(v))}",
                             patch=((axis, v),)))
        return out
    # Forma 2 — stati nominati: ogni entry e' un bundle di override, e il nome
    # dello stato e' quello che finisce nella cartella. E' l'unica forma
    # ammessa per gli override non scalari: un nome di cartella che non dice
    # cosa contiene e' il difetto che le take avevano.
    if not isinstance(cfg, dict) or not cfg:
        raise ctx.err(
            f"{BLOCK}: l'asse '{axis}' dev'essere un generatore, una lista, o un "
            "dict di stati nominati.",
            key=key,
        )
    out = []
    for stato, bundle in cfg.items():
        skey = (BLOCK, axis, stato)
        if not isinstance(bundle, dict):
            raise ctx.err(
                f"{BLOCK}: l'asse '{axis}', stato '{stato}': uno stato e' un "
                "bundle di override '{path puntato: valore}'.",
                key=skey,
                hint=f"es. '{stato}: {{base.distribution: 0.5}}'. Un bundle vuoto "
                     "({}) e' lecito: e' lo stato che non tocca niente.",
            )
        out.append(Combo(label=f"{_slug(axis)}={_slug(str(stato))}",
                         patch=tuple(bundle.items())))
    return out


def _reject_stato_generatore(axis: str, cfg: Any, ctx: ErrCtx, key: tuple) -> None:
    """Uno stato chiamato ``base``/``values``/``ramp`` legge l'asse come Forma 1.

    Il discriminatore guarda la forma, non i nomi: un asse a stati nominati con
    uno stato di nome ``base`` diventa una banda, e l'errore vero salta fuori
    molto piu' in la', incomprensibile ("banda: 'n' obbligatorio"). Il segnale
    e' la chiave estranea al vocabolario piatto del generatore — che e' anche
    il refuso opposto (una chiave sbagliata dentro un generatore vero).
    """
    if not isinstance(cfg, dict) or not is_generator_node(cfg):
        return
    estranee = sorted(k for k in cfg if k not in _GEN_VOCAB)
    if not estranee:
        return
    raise ctx.err(
        f"{BLOCK}: l'asse '{axis}' e' letto come generatore (c'e' una chiave fra "
        f"{sorted(Y_GENERATOR_KEYS)}) ma ha anche {estranee}, che il generatore "
        "non conosce.",
        key=key,
        hint="se volevi un asse a stati nominati, nessuno stato puo' chiamarsi "
             f"{sorted(Y_GENERATOR_KEYS)}: rinominalo.",
    )


def _reject_collisions(names: List[str], axes: List[List[Combo]], ctx: ErrCtx) -> None:
    """Due assi non possono etichettare allo stesso modo ne' toccare lo stesso path.

    Etichette gemelle darebbero cartelle ambigue (``distribution=0__distribution=1``);
    due assi sullo stesso path renderebbero il valore finale dipendente
    dall'ordine di dichiarazione, che qui non e' una precedenza dichiarata.
    Vale anche per due path uno dentro l'altro (``base.grain`` e
    ``base.grain.duration``): il valore si assegna, non si fonde, quindi il
    sotto-albero dell'uno cancella la foglia dell'altro o ne e' cancellato,
    secondo l'ordine.

    Dentro un asse, lo stesso vale per i valori: due che si scrivono uguali
    nel nome della cartella (il doppione vero, ``1`` e ``1.0``, due nomi che lo
    slug fonde) darebbero due combinazioni in una cartella sola, e la seconda
    riscriverebbe la prima.
    """
    seen_label: Dict[str, str] = {}
    seen_path: Dict[str, str] = {}
    for name, parts in zip(names, axes):
        visti = set()
        for part in parts:
            if part.label in visti:
                raise ctx.err(
                    f"{BLOCK}: l'asse '{name}' da' due volte l'etichetta "
                    f"'{part.label}': due combinazioni finirebbero nella stessa "
                    "cartella.",
                    key=(BLOCK, name),
                    hint="togli il doppione o rinomina lo stato; se due valori "
                         "diversi nel nome di una cartella si scrivono uguali, "
                         "passa a un asse a stati nominati e dagli i nomi tu.",
                )
            visti.add(part.label)
        etichetta = parts[0].label.split("=", 1)[0]
        if etichetta in seen_label:
            raise ctx.err(
                f"{BLOCK}: gli assi '{seen_label[etichetta]}' e '{name}' danno la "
                f"stessa etichetta '{etichetta}' nel nome della cartella.",
                key=(BLOCK, name),
                hint="rinomina uno dei due (un asse a stati nominati porta il nome "
                     "che gli dai).",
            )
        seen_label[etichetta] = name
        for part in parts:
            for path, _v in part.patch:
                for altro, owner in seen_path.items():
                    if owner == name or not _overlap(altro, path):
                        continue
                    toccati = (f"entrambi '{path}'" if altro == path
                               else f"'{altro}' e '{path}', uno dentro l'altro")
                    raise ctx.err(
                        f"{BLOCK}: gli assi '{owner}' e '{name}' toccano {toccati}.",
                        key=(BLOCK, name),
                        hint="uniscili in un solo asse a stati nominati.",
                    )
                seen_path[path] = name


def _overlap(a: str, b: str) -> bool:
    """Lo stesso path, o uno dentro l'altro (confine su un segmento intero)."""
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


# --- patch -----------------------------------------------------------------

def _set_path(doc: Dict[str, Any], path: str, value: Any, ctx: ErrCtx) -> None:
    """Assegna ``value`` al path puntato. Il contenitore padre deve esistere.

    Creare una chiave nuova e' lecito (``base.pan_range`` su un ``base:`` che
    non ce l'ha), creare una **sezione** no: ``bse.pan_range`` sarebbe un refuso
    che passa in silenzio e non muove niente. Il resto della validazione arriva
    da sola dal parse dello studio, che le chiavi sconosciute le rifiuta gia'.

    Il path non si spezza su ogni punto: a ogni livello si cerca, fra i
    prefissi del resto del path, la chiave che il nodo ha davvero. E' cosi' che
    ``axes.grain.duration.values`` raggiunge l'asse ``grain.duration`` (una
    chiave sola, col punto dentro) invece di cercare un ``grain`` che non
    c'e'. Due prefissi presenti insieme (assi ``grain`` e ``grain.duration``)
    sono un'ambiguita': errore, come per le chiavi puntate di ``streams:``,
    mai una scelta silenziosa.
    """
    parts = path.split(".")
    node: Any = doc
    i = 0
    while True:
        if not isinstance(node, dict):
            raise ctx.err(
                f"{BLOCK}: il path '{path}' scende dentro un valore che non e' un "
                "dict.",
                key=(BLOCK,),
            )
        rest = parts[i:]
        spans = [j for j in range(1, len(rest) + 1) if ".".join(rest[:j]) in node]
        if len(spans) > 1:
            nomi = " o ".join(repr(".".join(rest[:j])) for j in spans)
            dove = f"sotto '{'.'.join(parts[:i])}'" if i else "alla radice"
            raise ctx.err(
                f"{BLOCK}: il path '{path}' e' ambiguo: {dove} la chiave puo' "
                f"essere {nomi}.",
                key=(BLOCK,),
                hint="rinomina una delle due chiavi, o assegna l'intero "
                     "sotto-albero dal livello sopra.",
            )
        if not spans:
            if len(rest) == 1:
                node[rest[0]] = value
                return
            raise ctx.err(
                f"{BLOCK}: il path '{path}' non esiste nel documento "
                f"('{'.'.join(parts[:i + 1])}' non c'e').",
                key=(BLOCK,),
                hint="il path e' quello dello study.yml: 'base.distribution', "
                     "'axes.grain.duration.values', 'stack.seed'.",
            )
        chiave = ".".join(rest[:spans[0]])
        if i + spans[0] == len(parts):
            node[chiave] = value
            return
        node = node[chiave]
        i += spans[0]


# --- nomi ------------------------------------------------------------------

def _is_scalar(v: Any) -> bool:
    return isinstance(v, (int, float, str, bool)) or v is None


def _short(path: str) -> str:
    """``base.grain.duration`` -> ``grain.duration``; ``axes.fill_factor.values``
    -> ``fill_factor``. Toglie il prefisso di sezione e il nome del generatore:
    nel nome della cartella sono rumore, la chiave e' cio' che si muove."""
    for pre in ("base.", "axes."):
        if path.startswith(pre):
            path = path[len(pre):]
            break
    for gen in (".values", ".ramp", ".band"):
        if path.endswith(gen):
            path = path[: -len(gen)]
            break
    return _slug(path)


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)
