"""La pagina del laboratorio: un solo stream, composto e sentito al volo.

La pagina e' una sola, in ``generated/<study>/graph.html``, e non guarda il
disco: e' il banco su cui si compone UN documento engine — i parametri sono le
tacche dichiarate nello ``study.yml``, l'audio nasce da ``POST /render`` (vedi
``serve.py``). Il nome ``graph`` viene dalla griglia delle varianti discrete
che la pagina era in mare-nostrum, tolta e mai portata qui.

Nessuna dipendenza: l'HTML sta alla radice dell'output e carica l'audio con
path relativi.
"""
from __future__ import annotations

import copy
import html
import json
import os
from typing import Any, Dict, Iterator, List, Tuple

from .errors import ErrCtx
from .study_spec import axis_names, merge_stream_override
from .value_generators import resolve


# Le eccezioni di un generatore che non si risolve. E' l'insieme che
# ``for_each._parse_axis`` gia' riconosce — ``ValueError`` (e con esso
# ``SpecError``) da ``y_generator``/``ramp``/``band``, ``TypeError`` da un
# generatore scritto male (``ramp`` senza ``start``, ``values`` che non e' una
# lista), ``LookupError`` da un Env di banda senza il suo valore — piu'
# ``RuntimeError``: espandere una chiave puntata che introduce un asse dotted
# nuovo chiede il registro dell'engine (``split_axis_key`` ->
# ``bounds.known_paths``), che senza il submodule non c'e'.
_ILLEGGIBILE = (ValueError, TypeError, LookupError, RuntimeError)

# Il prefisso che, in ``for_each:``, marca una patch sullo stream a riposo.
_BASE = "base."


def _tacche(cfg: Any) -> List[Any] | None:
    """I valori del generatore di un asse, o ``None`` se non e' leggibile.

    Un generatore solo lo risolve ``value_generators.resolve``, lo stesso che
    usa ``for_each:``: ``values`` (lista), ``ramp`` (griglia), banda
    (``base``/``range``/``n``). La lista nuda e' la forma breve che
    ``for_each`` accetta, e si legge come ``values``.

    Non si risolve = niente tacche, mai un'eccezione: il laboratorio e' un
    banco su cui si scrive a mano, e una pagina che non si apre e' peggio di
    una manopola senza menu. Chi sbaglia il generatore lo sentono dire
    ``sweep`` e ``render``, che su quei valori ci devono renderizzare.
    """
    if isinstance(cfg, list):
        cfg = {"values": cfg}
    if not isinstance(cfg, dict):
        return None
    try:
        return list(resolve(cfg))
    except _ILLEGGIBILE:
        return None


def _assi(doc: Dict[str, Any]) -> Iterator[Tuple[str, Any]]:
    """Gli assi di ``doc``, nell'ordine in cui sono scritti.

    Cosa sia un asse lo decide ``study_spec.axis_names`` — la stessa regola
    del parse, non una lista di chiavi riservate riscritta qui.
    """
    nomi = axis_names(doc)
    for nome, cfg in (doc.get("axes") or {}).items():
        if nome in nomi:
            yield nome, cfg


def _uniche(valori: List[Any]) -> List[Any]:
    """Senza doppioni, nell'ordine in cui sono comparsi."""
    visti: set = set()
    out: List[Any] = []
    for v in valori:
        try:
            if v in visti:
                continue
            visti.add(v)
        except TypeError:          # un valore non hashable: niente insieme
            if v in out:
                continue
        out.append(v)
    return out


def lab_data(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    """Il corredo del laboratorio: lo stream a riposo e le tacche di ogni parametro.

    Le liste sono quelle gia' scelte nello ``study.yml`` — assi interni, assi
    esterni ``base.*`` e assi scritti dentro ``streams:`` sono, dal punto di
    vista di uno stream solo, la stessa cosa: valori di quel parametro che
    vale la pena sentire. Il laboratorio non li moltiplica in una griglia, li
    usa come tacche fra cui scegliere il valore di un breakpoint.

    **Unione, non selettore** (issue #77). Le tacche di un parametro sono
    l'unione di tutte le sue fonti, documento e stream insieme. Il
    laboratorio compone UNO stream: una lista per stream vorrebbe un
    selettore in pagina, cioe' chiedere "quale zona stai ascoltando" a chi
    sta componendo un'altra cosa. Le quattro zone d'ombra di ``1-10ms``
    scrivono quattro rampe di ``density`` sullo stesso asse: insieme sono le
    density che quello studio ha trovato interessanti, che e' esattamente
    cio' che un menu di tacche deve offrire.

    **Lo stream a riposo e' il ``base:`` del documento**, non quello delle
    entry: con piu' stream e' l'unico che tutti condividono, mentre il
    ``base:`` di una entry differenzia quella voce dalle sorelle (il
    ``pointer.start`` di un cugino) e fonderli darebbe uno stream che non ha
    scritto nessuno.

    **Un asse senza generatore leggibile resta una manopola**, senza menu:
    ``grain.duration`` sotto osservazione in uno stack e' il parametro dello
    studio anche quando le sue tacche non si enumerano (una banda senza
    ``n``: i valori li fa emergere la camminata-X). Toglierlo lascerebbe fuori
    dal banco proprio il parametro che lo studio sta studiando. Una chiave di
    ``for_each:`` illeggibile invece non dichiara niente — li' il generatore
    *e'* la dichiarazione, e ``for_each`` stesso la rifiuta.
    """
    raw = raw or {}
    ordine: List[str] = []
    grezze: Dict[str, List[Any]] = {}

    def aggiungi(path: str, valori: List[Any]) -> None:
        if path not in grezze:
            ordine.append(path)
            grezze[path] = []
        grezze[path].extend(valori)

    for nome, cfg in _assi(raw):
        aggiungi(nome, _tacche(cfg) or [])
    for key, cfg in (raw.get("for_each") or {}).items():
        # Solo le patch su `base.`: `stack.seed` o `percorso.arco` non sono
        # parametri di uno stream e nel laboratorio non hanno posto.
        if not isinstance(key, str) or not key.startswith(_BASE):
            continue
        valori = _tacche(cfg)
        if valori:
            aggiungi(key[len(_BASE):], valori)
    nomi = axis_names(raw)
    for sid, entry in (raw.get("streams") or {}).items():
        if not isinstance(entry, dict):
            continue
        try:
            # La copia non e' prudenza: ``_replace_generators`` pota le chiavi
            # della banda sul dict che trova, e per un asse che solo questo
            # stream dichiara quel dict *e'* l'override dentro ``raw``. Senza,
            # lo stream dopo (o un alias YAML) leggerebbe un documento mangiato.
            merged = merge_stream_override(
                raw, copy.deepcopy(entry), nomi, ErrCtx(stream=str(sid))
            )
        except _ILLEGGIBILE:
            continue
        for nome, cfg in _assi(merged):
            aggiungi(nome, _tacche(cfg) or [])

    params: List[Dict[str, Any]] = []
    for path in ordine:
        valori = _uniche(grezze[path])
        if not valori:
            # Un asse e' numerico per costruzione (``Axis.baseline`` e
            # ``Axis.values`` sono float) e uno categoriale si scrive con
            # ``values:``, che si risolve sempre: senza tacche restano le
            # rampe e le bande, cioe' numeri. ``free`` e' lo stesso marcatore
            # di volume e pan — campo senza menu.
            params.append({"path": path, "values": [], "kind": "num", "free": True})
            continue
        # Categoriale = il valore e' un nome, non un numero. Restano manopole
        # fisse per lo stream, con un'eccezione: `grain.envelope`, che la
        # pagina automatizza scrivendo {states, curve} invece di una lista di
        # breakpoint — l'engine rifiuta la seconda ("Window non trovata") ma
        # conosce la prima (MultiStateWindowStrategy).
        if all(isinstance(v, (int, float)) for v in valori):
            # Nello ``study.yml`` ``values:`` e' una sequenza da percorrere e
            # puo' tornare sui suoi passi; qui e' un menu, dove un valore sta
            # una volta sola e in ordine. Senza un ordine canonico l'unione
            # fra documento e stream non ne avrebbe nessuno.
            params.append({"path": path, "values": sorted(valori), "kind": "num"})
        else:
            params.append({"path": path, "values": valori, "kind": "cat"})
    return {"base": raw.get("base") or {}, "params": params}


def build_html(study: str, lab: Dict[str, Any] | None = None) -> str:
    data = {"study": study, "lab": lab or {"base": {}, "params": []}}
    return _template().replace("__TITLE__", html.escape(f"{study} — laboratorio")) \
                    .replace("__DATA__", json.dumps(data))


def write_graph(study: str, out_path: str,
                lab: Dict[str, Any] | None = None) -> int:
    """Scrive ``out_path``. Ritorna il numero di parametri del laboratorio.

    La pagina si scrive sempre: il laboratorio compone da zero e non ha
    bisogno di niente su disco.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(build_html(study, lab))
    return len((lab or {}).get("params") or [])


_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "graph_page.html")


def _template() -> str:
    """Il guscio della pagina.

    Sta in un file suo e non in una stringa qui: e' HTML/CSS/JS vero, e dentro
    un .py perderebbe evidenziazione, indentazione e ``node --check``.
    """
    with open(_TEMPLATE_PATH) as fh:
        return fh.read()


_AUDIO = (".wav", ".flac", ".aif", ".aiff")


def campioni(samples_dir: str) -> List[str]:
    """I sample della cartella dello studio, come li scrive `sample:`.

    Nel laboratorio il sample e' una manopola fissa per lo stream come le
    altre categoriali: cambiarlo e' un ascolto diverso, non un asse. I nomi
    sono relativi a ``samples_dir`` — e' cosi' che l'engine li risolve.
    """
    out: List[str] = []
    for root, _dirs, files in os.walk(samples_dir):
        for f in files:
            if f.lower().endswith(_AUDIO):
                out.append(os.path.relpath(os.path.join(root, f), samples_dir))
    return sorted(out)
