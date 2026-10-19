"""Il laboratorio apre un documento e lo riscrive: cosa resta e cosa cambia.

Qui la pagina gira intera (``tests/lab_dom.js``), non a frammenti: il giro
che conta passa per ``carica`` (il documento aperto), i select, le voci, il
loop, la storia, la bozza, e torna fuori da ``labDoc``. Il documento arriva
come lo manda il server (``yaml.safe_load`` -> JSON).

La regola (#87, da DMGiulioRomano/mare-nostrum#3): si parte dallo stream del
documento aperto e si sovrascrive solo cio' che il laboratorio conosce **e che
e' stato toccato**. Il ``base:`` dello studio e la tabella ``DEFAULTS`` valgono
solo per il foglio bianco.

I test sono quelli di mare-nostrum, sulle sue fixture
(``tests/fixtures/mare-nostrum/``: il brano, e lo studio 001-41 da cui fa la
pagina), perche' la regola e' stata scritta li' e i suoi stream sono documenti
veri di PGE-ui. In fondo gli stessi giri sulla pagina di uno studio di questo
repo (``1-10ms``), dove il ``base:`` e le manopole sono altri.
"""
import json
import os
import shutil
import subprocess

import pytest
import yaml

from granstudies.graph import build_html, lab_completo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HARNESS = os.path.join(ROOT, "tests", "lab_dom.js")
ENGINE_SRC = os.path.join(ROOT, "engine", "src")
# Le fixture di mare-nostrum hanno la forma del suo repo: il brano in radice e
# gli studi sotto `studies/`. `ROOT` e' la radice di questo, coi suoi studi.
MARE_NOSTRUM = os.path.join(ROOT, "tests", "fixtures", "mare-nostrum")

node = pytest.mark.skipif(shutil.which("node") is None, reason="serve node")
engine = pytest.mark.skipif(not os.path.isdir(os.path.join(ENGINE_SRC, "pge")),
                            reason="serve il submodule engine")

# Due dei sample del brano, non tutti: uno stream che usa un sample fuori
# dalla cartella dello studio vede il suo select vuoto, come nel browser.
CAMPIONI = ["001-41_5-5_5.wav", "001-3_0-5_5.wav"]


def _predefiniti():
    """I default dell'engine per path, come li passa `cmd_graph`. Senza il
    submodule non ce ne sono, e la pagina ricade sul foglio bianco."""
    if not os.path.isdir(os.path.join(ENGINE_SRC, "pge")):
        return {}
    from granstudies.engine_bridge import parameter_path_defaults
    return parameter_path_defaults()


def _pagina(tmp_path, study="001-41", radice=MARE_NOSTRUM, campioni=CAMPIONI):
    with open(os.path.join(radice, "studies", study, "study.yml")) as fh:
        raw = yaml.safe_load(fh)
    p = tmp_path / "graph.html"
    p.write_text(build_html(study, lab_completo(raw, campioni, {}, lambda _p: None,
                                                _predefiniti(), study)))
    return p


def _lab(tmp_path, scenario, prima=None, study="001-41", radice=MARE_NOSTRUM,
         campioni=CAMPIONI):
    """Fa girare lo scenario sulla pagina; l'ultima riga stampata e' JSON."""
    args = ["node", HARNESS, str(_pagina(tmp_path, study, radice, campioni))]
    sc = tmp_path / "scenario.js"
    sc.write_text(scenario)
    args.append(str(sc))
    if prima:
        pr = tmp_path / "prima.js"
        pr.write_text(prima)
        args.append(str(pr))
    out = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _brano():
    with open(os.path.join(MARE_NOSTRUM, "mare-nostrum.yml")) as fh:
        return yaml.safe_load(fh)


def _stream(sid):
    return next(s for s in _brano()["streams"] if s["stream_id"] == sid)


def _documento(st):
    """Uno stream del brano in un file suo, come lo apre il laboratorio."""
    return {"duration": st.get("duration"), "bpm": 120, "streams": [st]}


def _apri(st, path=None):
    return "carica(%s, %s);\n" % (json.dumps(_documento(st)),
                                  json.dumps(path or "/brano/%s.yml" % st["stream_id"]))


STAMPA = "console.log(JSON.stringify(labDoc()));\n"

# Il valore che si scrive nel campo di un parametro e si salva sul
# breakpoint selezionato: e' il gesto di `salva modifica`.
def _tocca(i, path, valore, tipo=None):
    js = "bpLoad(%d); document.getElementById(%s).value = %s;\n" % (
        i, json.dumps("P:" + path), json.dumps(str(valore)))
    if tipo:
        js += "document.getElementById(%s).value = %s;\n" % (
            json.dumps("I:" + path), json.dumps(tipo))
    return js + "bpSave();\n"


# --- #3: lo stream aperto si conserva -----------------------------------------

@node
def test_read_direction_a_inviluppo_sopravvive_al_giro(tmp_path):
    """Il caso che ha aperto la #3: 8 stream del brano su 10 la perdevano."""
    st = _stream("stream2")
    doc = _lab(tmp_path, _apri(st) + STAMPA)
    assert doc["streams"][0]["grain"]["read_direction"] == st["grain"]["read_direction"]


@node
@pytest.mark.parametrize("sid", ["stream2", "stream4", "stream9"])
def test_aperto_e_risalvato_senza_toccare_e_lo_stesso_stream(tmp_path, sid):
    """Niente chiavi del `base:` dello studio, niente default del laboratorio.

    stream4 non dichiara `pointer.offset_range` ne' `pitch.range`, e il
    laboratorio di 001-41 ha un campo per tutti e due: restano assenti. Lo
    `stream_id` e l'`onset` sono quelli del documento, non `lab` e 0.
    """
    st = _stream(sid)
    doc = _lab(tmp_path, _apri(st) + STAMPA)
    assert doc["streams"][0] == st


def _con_testa(st):
    """Il documento con in testa chiavi che il laboratorio non conosce: il
    `seed` (#89 conta che resti), una chiave di PGE-ui, un bpm che non e' 120
    e la durata del brano intero, diversa da quella dello stream."""
    return {"duration": 322.074, "bpm": 90, "seed": 1441,
            "ui_tracks": [{"id": "t1", "streams": [st["stream_id"]]}], "streams": [st]}


@node
def test_le_chiavi_in_testa_al_documento_restano(tmp_path):
    """Aperto e risalvato senza toccare niente, torna identico anche fuori
    dallo stream: prima `labDoc` riscriveva la testa come `{duration, bpm:
    120}` e il `seed` spariva."""
    doc = _con_testa(_stream("stream2"))
    got = _lab(tmp_path, "carica(%s, '/brano/stream2.yml');\n" % json.dumps(doc) + STAMPA)
    assert got == doc


@node
def test_la_durata_toccata_si_scrive_in_testa_e_nello_stream(tmp_path):
    """La durata in testa segue la regola delle altre chiavi: resta quella
    del documento finche' nessuno tocca `durata (s)`; toccata, si scrive li'
    e nello stream. Il resto della testa resta."""
    doc = _con_testa(_stream("stream2"))
    got = _lab(tmp_path, "carica(%s, '/brano/stream2.yml');\n" % json.dumps(doc) + """
const d = document.getElementById('labDur');
d.value = '120';
d.onchange();
console.log(JSON.stringify(labDoc()));
""")
    assert got["duration"] == 120 and got["streams"][0]["duration"] == 120
    assert {k: got[k] for k in ("bpm", "seed", "ui_tracks")} == \
        {k: doc[k] for k in ("bpm", "seed", "ui_tracks")}


@node
def test_un_parametro_assente_non_eredita_lo_schermo_del_documento_di_prima(tmp_path):
    """Aperto dopo un altro documento, un parametro che il nuovo non dichiara
    mostra il valore da cui parte il foglio bianco, non quello rimasto a
    schermo — ne' sui breakpoint (`pan_range`) ne' nei fissi
    (`voices.pitch.unit`). Nel file non entra comunque, finche' non lo si tocca.
    """
    a = dict(_stream("stream3"), pan_range=360)
    st = _stream("stream2")          # niente voci, pan_range 360
    del st["pan_range"]
    got = _lab(tmp_path, _apri(a) + _apri(st) + """
console.log(JSON.stringify({
  schermo: document.getElementById('P:pan_range').value,
  punti: bps.map(b => b.vals['pan_range']),
  unit: document.getElementById('P:voices.pitch.unit').value,
  doc: labDoc()}));
""")
    assert float(got["schermo"]) == 0 and set(got["punti"]) == {0}
    assert got["unit"] == "semitones"
    assert got["doc"]["streams"][0] == st


@node
@engine
def test_un_parametro_assente_si_mostra_al_valore_che_l_engine_suona(tmp_path):
    """Lo stream non dichiara `grain.duration` ne' `grain.envelope`: l'engine
    rende col suo default, e lo schermo deve dire quello, non il punto di
    partenza del foglio bianco (`DEFAULTS`).

    Altrimenti lo schermo mente in silenzio: mostra un valore che l'ascolto
    non ha, e sceglierlo a mano non scrive niente — per `labDoc` e' "non
    toccato" — mentre l'engine continua a rendere il suo. Il documento resta
    senza le due chiavi finche' non le si tocca davvero.
    """
    from granstudies.engine_bridge import parameter_path_defaults
    motore = parameter_path_defaults()
    st = _stream("stream2")
    del st["grain"]["duration"], st["grain"]["envelope"]
    got = _lab(tmp_path, _apri(st) + """
const vista = {
  durate: bps.map(b => b.vals['grain.duration']),
  finestre: bps.map(b => b.vals['grain.envelope']),
  foglio: [DEFAULTS['grain.duration'], DEFAULTS['grain.envelope']]};
// Lo stesso valore, scelto a mano su ogni breakpoint: non e' una modifica.
for (let i = 0; i < bps.length; i++) {
  bpLoad(i);
  document.getElementById('P:grain.duration').value = String(vista.durate[0]);
  bpSave();
}
vista.doc = labDoc();
console.log(JSON.stringify(vista));
""")
    attesi = [motore["grain.duration"], motore["grain.envelope"]]
    # Il caso discrimina solo finche' il foglio bianco parte da altro.
    assert got["foglio"] != attesi
    assert set(got["durate"]) == {attesi[0]}
    assert set(got["finestre"]) == {attesi[1]}
    assert got["doc"]["streams"][0] == st


@node
def test_un_parametro_toccato_si_scrive_come_prima(tmp_path):
    """Breakpoint e interpolazione, come oggi; il resto resta com'era."""
    st = _stream("stream2")
    doc = _lab(tmp_path, _apri(st) + _tocca(0, "pitch.ratio", 0.75, "cubic") + STAMPA)
    out = doc["streams"][0]
    assert out["pitch"]["ratio"][0] == [0, 0.75, "cubic"]
    assert out["pitch"]["ratio"][-1][1] == 0.2
    out["pitch"]["ratio"] = st["pitch"]["ratio"]
    assert out == st


@node
def test_le_voci_toccate_si_scrivono_le_altre_restano(tmp_path):
    st = _stream("stream3")
    doc = _lab(tmp_path, _apri(st) + "setSel('voices.pan.strategy', 'off');\n" + STAMPA)
    out = doc["streams"][0]
    assert out["voices"] == {"num_voices": 4, "pitch": st["voices"]["pitch"]}
    out["voices"] = st["voices"]
    assert out == st


@node
def test_il_loop_acceso_si_scrive_col_suo_gruppo(tmp_path):
    """Il loop e' un gruppo di chiavi: acceso, `start: 0` se ne va con lui
    (col loop il pointer parte da loop_start), il resto del pointer resta."""
    st = _stream("stream2")
    doc = _lab(tmp_path, _apri(st) + "loopDisegna(0.1, 0.4);\n" + STAMPA)
    assert doc["streams"][0]["pointer"] == {
        "speed_ratio": 0.1, "loop_unit": "normalized", "offset_range": 0.01,
        "loop_start": 0.1, "loop_end": 0.4}


@node
def test_la_finestra_che_cambia_diventa_a_stati(tmp_path):
    st = _stream("stream2")
    doc = _lab(tmp_path, _apri(st)
               + "bps[bps.length - 1].vals['grain.envelope'] = 'bartlett'; drawTl();\n"
               + STAMPA)
    env = doc["streams"][0]["grain"]["envelope"]
    assert env["states"] == [[0, "hanning"], [1, "bartlett"]]
    assert doc["streams"][0]["grain"]["read_direction"] == st["grain"]["read_direction"]


@node
def test_il_foglio_bianco_nasce_da_defaults_e_base(tmp_path):
    doc = _lab(tmp_path, "bpAdd();\n" + STAMPA)
    out = doc["streams"][0]
    assert (out["stream_id"], out["onset"], out["time_mode"]) == ("lab", 0, "normalized")
    assert out["grain"]["duration"] == 0.064             # DEFAULTS
    assert out["distribution_mode"] == "uniform"         # base:


@node
def test_nuovo_dopo_un_documento_aperto_non_se_lo_porta_dietro(tmp_path):
    """`nuovo` torna al foglio bianco: lo stream di prima non e' piu' la base."""
    doc = _lab(tmp_path, _apri(_stream("stream2")) + "fNew(); bpAdd();\n" + STAMPA)
    out = doc["streams"][0]
    assert (out["stream_id"], out["onset"]) == ("lab", 0)
    assert "read_direction" not in out["grain"]


@node
def test_l_undo_torna_allo_stream_aperto(tmp_path):
    """Lo stream e la testa del documento: tutti e due stanno nella storia."""
    st = _stream("stream2")
    doc = _con_testa(st)
    got = _lab(tmp_path, "carica(%s, '/brano/stream2.yml');\n" % json.dumps(doc)
               + _tocca(0, "pitch.ratio", 0.75) + """
const toccato = labDoc();
vaiStoria(-1);
const annullato = labDoc();
vaiStoria(1);
console.log(JSON.stringify([toccato, annullato, labDoc()]));
""")
    toccato, annullato, rifatto = got
    assert annullato == doc
    assert toccato == rifatto and toccato["streams"][0]["pitch"]["ratio"][0] == [0, 0.75]
    assert toccato["seed"] == 1441


@node
def test_la_bozza_riporta_lo_stream_conservato(tmp_path):
    """Un refresh a meta' lavoro: torna anche quello che il laboratorio non
    conosce, non solo i breakpoint."""
    st = _stream("stream2")
    bozza = _lab(tmp_path, "carica(%s, '/brano/stream2.yml');\n" % json.dumps(_con_testa(st))
                 + _tocca(0, "pitch.ratio", 0.75)
                 + "console.log(localStorage.getItem('lab:001-41'));\n")
    bozza["sess"] = "S"
    prima = """
localStorage.setItem('lab:001-41', %s);
fetch = async () => ({ok: true, json: async () => ({ok: true, sessione: 'S', recenti: []})});
""" % json.dumps(json.dumps(bozza))
    doc = _lab(tmp_path, STAMPA, prima=prima)
    assert (doc["seed"], doc["bpm"], doc["duration"]) == (1441, 90, 322.074)
    out = doc["streams"][0]
    assert out["pitch"]["ratio"][0] == [0, 0.75]
    out["pitch"]["ratio"] = st["pitch"]["ratio"]
    assert out == st


@node
def test_apri_recente_conserva_lo_stream(tmp_path):
    """`apri recente` e' `/open` piu' `carica`, come `apri…`: il file passa per
    la stessa porta, e ne esce lo stesso stream, testa compresa."""
    doc = _con_testa(_stream("stream2"))
    got = _lab(tmp_path, """
const DOC = %s;
fetch = async (rotta, opt) => ({ok: true, json: async () =>
  rotta === '/stato' ? {ok: true, sessione: 'S', recenti: ['/brano/stream2.yml']}
  : rotta === 'open' && JSON.parse(opt.body).path === '/brano/stream2.yml'
    ? {ok: true, doc: DOC} : {ok: false, error: 'non qui: ' + rotta}});
(async () => {
  await recenti();
  const menu = document.getElementById('fRecent');
  menu.value = '/brano/stream2.yml';
  menu.onchange();
  for (let i = 0; i < 5; i++) await new Promise(r => setTimeout(r, 0));
  console.log(JSON.stringify({file: FILE, doc: labDoc()}));
})();
""" % json.dumps(doc))
    assert got["file"] == "/brano/stream2.yml"
    assert got["doc"] == doc


@node
def test_l_anteprima_e_quella_del_documento(tmp_path):
    """L'anteprima dice cosa finisce nello YAML: un inviluppo non toccato
    esce come era scritto, non coi punti in piu' della griglia dei
    breakpoint (qui quelli di `fill_factor`)."""
    righe = _lab(tmp_path, _apri(_stream("stream4"))
                 + "console.log(JSON.stringify(preview().split('\\n')));\n")
    assert "grain.duration: [[0.000, 0.02, step], [0.343, 0.0032], [1.000, 0.02]]" in righe
    assert ("fill_factor: {type: cubic} [[0.000, 2], [0.093, 2.01], [0.163, 0.46], "
            "[0.259, 0.4], [0.313, 2.75], [1.000, 1]]") in righe


@node
@pytest.mark.parametrize("sid", ["stream5", "stream10"])
def test_si_ascolta_senza_piazzamento_ma_si_salva_con(tmp_path, sid):
    """`onset`, `mute` e `solo` sono del brano, non del suono dello stream.

    Nel file restano (lo stream e' quello). Ma ascoltato nel laboratorio uno
    stream con onset 43 s partirebbe dopo 43 s di silenzio, e uno con `mute`
    non suonerebbe affatto: il render d'ascolto li toglie.
    """
    st = _stream(sid)
    got = _lab(tmp_path, _apri(st) + """
const POST = [];
fetch = async (rotta, opt) => { POST.push(JSON.parse(opt.body));
  return {ok: true, json: async () => ({ok: false, error: 'fermo qui'})}; };
labRender().then(() => console.log(JSON.stringify(POST[0])));
""")
    assert got["doc"]["streams"][0] == st
    ascolto = got["ascolto"]["streams"][0]
    assert ascolto["onset"] == 0
    assert "mute" not in ascolto and "solo" not in ascolto
    piazzati = {"onset", "mute", "solo"}
    assert ({k: v for k, v in ascolto.items() if k not in piazzati}
            == {k: v for k, v in st.items() if k not in piazzati})


# --- un documento che non e' uno stream solo ---------------------------------
# Il laboratorio e' il banco di UNO stream, e scrive un documento con uno
# stream solo. Aperto un documento che ne ha di piu', o un master che li
# importa con `file:` (PythonGranularEngine#290), la scrittura sul file aperto
# ne butterebbe via tutti gli altri, al primo `rendi e ascolta` e senza una
# domanda. E con la testa conservata (#87) il documento che ne usciva teneva
# anche quella del documento intero: le corsie di PGE-ui di tutti gli stream,
# la durata di tutto.
#
# Portati da DMGiulioRomano/mare-nostrum@c971ef9 e @49a9b2f, senza le parti
# che vengono dalle issue dopo nello stack (l'id dal nome del file e il seed
# dello studio, #89; la firma, #90), e con un master scritto qui: quello vero
# del brano di mare-nostrum non e' fra le fixture.
#
# Il "disco" e' fatto di piu' file: `/open` legge quello chiesto, `/render`
# scrive dove la pagina dice (in `live/`, se non dice niente).

def _dischi(dischi):
    return """
const POST = [];
const DISCHI = %s;
fetch = async (rotta, opt) => {
  if (rotta === '/stato')
    return {ok: true, json: async () => ({ok: true, sessione: 'S', recenti: []})};
  const body = JSON.parse(opt.body);
  POST.push(Object.assign({rotta}, body));
  if (rotta === 'open')
    return {ok: true, json: async () => ({ok: true, path: body.path,
      doc: JSON.parse(JSON.stringify(DISCHI[body.path]))})};
  if (body.path) DISCHI[body.path] = body.doc;
  return {ok: true, json: async () => ({ok: true, src: 'x.aif', yaml: 'r.yml',
    path: body.path || 'live/x.yml'})};
};
""" % json.dumps(dischi)


DOVE = """
const SCRITTURE = () => POST.filter(p => p.rotta === 'render').map(p => p.path || '');
"""

# Un master come lo scrive PGE-ui (DMGiulioRomano/PGE-ui#184): ogni voce
# importa uno stream da un file suo, e nel master resta il piazzamento.
MASTER = {"duration": 322.074, "bpm": 120, "seed": 1441,
          "streams": [{"file": "streams/stream2.yml"},
                      {"file": "streams/stream5.yml", "onset": 43.761}]}


@node
def test_un_master_non_si_apre_come_uno_stream(tmp_path):
    """La prima voce del master e' un rimando (`file: streams/stream2.yml`),
    non uno stream. Aperto come uno stream, il master diventava il file del
    laboratorio, e il primo render lo riscriveva con quella voce sola. Non si
    apre, e resta aperto il documento di prima: la scrittura dopo va li', non
    sul master."""
    st = _stream("stream2")
    got = _lab(tmp_path, _dischi({"/brano/streams/stream2.yml": _documento(st),
                                  "/brano/master.yml": MASTER}) + DOVE + """
(async () => {
  await apriPath('/brano/streams/stream2.yml');
  await apriPath('/brano/master.yml');
  const dopo = {file: FILE, info: document.getElementById('labInfo').textContent,
                id: labDoc().streams[0].stream_id};
  await labRender();
  console.log(JSON.stringify({dopo, scritture: SCRITTURE(),
                              master: DISCHI['/brano/master.yml']}));
})();
""")
    assert got["dopo"]["file"] == "/brano/streams/stream2.yml"
    assert got["dopo"]["id"] == "stream2"
    # La riga di stato dice cos'e' e cosa aprire al suo posto.
    assert "master" in got["dopo"]["info"] and "streams/stream2.yml" in got["dopo"]["info"]
    assert got["scritture"] == ["/brano/streams/stream2.yml"]
    assert got["master"] == MASTER


@node
def test_un_master_non_si_apre_neanche_sul_foglio_bianco(tmp_path):
    """Senza un documento di prima resta il foglio bianco: niente breakpoint,
    quindi niente da rendere, e il master resta com'e'."""
    got = _lab(tmp_path, _dischi({"/brano/master.yml": MASTER}) + DOVE + """
(async () => {
  await apriPath('/brano/master.yml');
  const dopo = {file: FILE, bps: bps.length};
  await labRender();
  console.log(JSON.stringify({dopo, scritture: SCRITTURE(),
                              master: DISCHI['/brano/master.yml']}));
})();
""")
    assert got["dopo"] == {"file": "", "bps": 0}
    assert got["scritture"] == []
    assert got["master"] == MASTER


@node
def test_un_documento_con_piu_stream_si_apre_sul_primo_e_non_ci_si_riscrive(tmp_path):
    """Un brano scritto per intero, o il documento di uno studio con piu'
    stream (`stack`, `versions`), si apre sul primo stream, come sempre. Ma
    quel file non e' piu' quello su cui il laboratorio scrive: e' un foglio da
    salvare con un nome suo, e il nome proposto e' lo `stream_id` del primo
    stream. La testa e' quella di un documento di uno stream: la sua durata,
    non quella del brano intero."""
    a, b = _stream("stream2"), _stream("stream5")
    doc = {"duration": 322.074, "bpm": 120, "seed": 1441, "streams": [a, b]}
    got = _lab(tmp_path, _dischi({"/brano/vecchio.yml": doc}) + DOVE + """
(async () => {
  await apriPath('/brano/vecchio.yml');
  const dopo = {file: FILE, nome: document.getElementById('labName').value,
                sporco: sporco(), bps: bps.length,
                info: document.getElementById('labInfo').textContent, doc: labDoc()};
  await labRender();
  console.log(JSON.stringify({dopo, scritture: SCRITTURE(),
                              disco: DISCHI['/brano/vecchio.yml']}));
})();
""")
    dopo = got["dopo"]
    assert (dopo["file"], dopo["nome"], dopo["sporco"]) == ("", "stream2", True)
    assert dopo["bps"] > 0
    assert "2 stream" in dopo["info"]
    scritto = dopo["doc"]
    assert scritto["streams"] == [a]
    assert scritto["duration"] == a["duration"]
    assert scritto["seed"] == 1441
    # Il render va in `live/` (path vuoto), e il documento sul disco resta.
    assert got["scritture"] == [""]
    assert got["disco"] == doc


@pytest.mark.parametrize("testa, durata, attese", [
    # La testa di un brano scritto da PGE-ui: il titolo e le sue corsie, che
    # nominano tutti gli stream del brano.
    ({"title": "brano", "duration": 322.074, "bpm": 120, "seed": 1441,
      "ui_tracks": [{"id": "t1", "name": "bassi", "streams": ["stream2", "stream5"]}]},
     True, ["seed", "duration", "bpm", "streams"]),
    # Senza seed nel documento non se ne inventa uno; senza durata nello
    # stream (lunga quanto il sample, PGE #205) non se ne scrive una: quella
    # del documento e' del brano intero.
    ({"duration": 322.074, "bpm": 120}, False, ["bpm", "streams"]),
])
@node
def test_lo_stream_preso_da_un_documento_con_piu_stream_ha_la_testa_di_uno_stream(
        tmp_path, testa, durata, attese):
    """Il documento che nasce dal primo stream e' un documento del laboratorio
    come gli altri: in testa il `seed`, la durata dello stream e il `bpm`,
    nell'ordine in cui li scrive il foglio bianco. Il resto della testa e' del
    documento da cui viene — la sua durata, il titolo, le corsie di PGE-ui
    (`ui_tracks`) — e accanto a uno stream solo direbbe il falso: aperto in
    PGE-ui, le corsie degli altri stream diventerebbero corsie vuote."""
    a, b = _stream("stream2"), _stream("stream5")
    if not durata:
        a = {k: v for k, v in a.items() if k != "duration"}
    doc = dict(testa, streams=[a, b])
    got = _lab(tmp_path, _dischi({"/brano/brano.yml": doc}) + """
(async () => {
  await apriPath('/brano/brano.yml');
  const d = labDoc();
  console.log(JSON.stringify({chiavi: Object.keys(d), doc: d}));
})();
""")
    assert got["chiavi"] == attese
    scritto = got["doc"]
    assert scritto.get("seed") == testa.get("seed")
    assert scritto["bpm"] == 120
    assert scritto.get("duration") == a.get("duration")
    assert scritto["streams"] == [a]


# --- le forme che il laboratorio non legge ---------------------------------------
# L'engine legge piu' forme di inviluppo di quelle che la pagina scrive: il
# blocco compatto `[pattern, end_time, n_reps]` (l'"add loop" di PGE-ui), anche
# dentro una lista, e il gruppo di breakpoint `[punti, interp]`. La pagina
# legge la lista di punti `[t, v]` / `[t, v, tipo]` — anche coi punti
# `{t, v, type}` — e il `{type, points}` (`curva`, #88, sotto): le altre non
# portano tempi fra i breakpoint, e nel file restano com'erano.
#
# Prima `carica` ci moriva a meta' (`for (const [t] of v)` su un numero o su un
# `{t, v}`), e moriva dopo aver gia' preso lo stream nuovo (`APERTO`) col file
# di prima ancora aperto: il `salva` dopo scriveva lo stream nuovo dentro il
# file di prima. Su `main`, senza `APERTO`, lo stesso `apri` falliva senza
# toccare niente. I punti `{t, v}` stavano qui fino alla #88, che li legge.

FORME = {
    "compatto": [[[0, -6], [50, 0], [100, -6]], 1.0, 4],
    "compatto_in_lista": [[0, -6], [[[0, -6], [100, 0]], 0.5, 2], [1, 0]],
    "gruppo": [[[0, -6], [0.5, 0], [1, -6]], "cubic"],
}


@node
@pytest.mark.parametrize("forma", sorted(FORME))
def test_un_inviluppo_che_il_laboratorio_non_legge_si_apre_e_resta_com_era(tmp_path, forma):
    """Si apre, i suoi punti non diventano breakpoint e non danno un tipo, e
    lo stream risalvato resta com'era — anche toccando un altro parametro."""
    st = dict(_stream("stream2"), volume=FORME[forma])
    got = _lab(tmp_path, _apri(_stream("stream2")) + "const ts0 = bps.map(b => b.t);\n"
               + _apri(st) + """
const vista = {ts0, ts: bps.map(b => b.t), tipi: bps.map(b => tipoDi(b, 'volume')),
               intatto: labDoc()};
""" + _tocca(0, "pitch.ratio", 0.75) + """
vista.toccato = labDoc();
console.log(JSON.stringify(vista));
""")
    assert got["ts"] == got["ts0"]
    assert set(got["tipi"]) == {"linear"}
    assert got["intatto"]["streams"][0] == st
    out = got["toccato"]["streams"][0]
    assert out["volume"] == FORME[forma]
    assert out["pitch"]["ratio"][0] == [0, 0.75]


@node
def test_aperto_dopo_un_altro_non_finisce_nel_file_di_prima(tmp_path):
    """Il caso vero: aperto un file, poi uno stream di PGE-ui con un blocco
    compatto, il `salva` scriveva il secondo stream dentro il primo file."""
    a = _stream("stream2")
    b = dict(_stream("stream5"), volume=FORME["compatto"])
    got = _lab(tmp_path, _dischi({"/brano/a.yml": _documento(a),
                                  "/brano/b.yml": _documento(b)}) + """
(async () => {
  await apriPath('/brano/a.yml');
  await apriPath('/brano/b.yml');
  const file = FILE;
  await fSave(false);
  console.log(JSON.stringify({file, a: DISCHI['/brano/a.yml'], b: DISCHI['/brano/b.yml']}));
})();
""")
    assert got["file"] == "/brano/b.yml"
    assert got["a"] == _documento(a)
    assert got["b"] == _documento(b)


# --- #88: gli inviluppi {type, points} ------------------------------------------
# `{type: cubic, points: [...]}` e' l'interpolazione globale di un inviluppo:
# la scrive PGE-ui appena quella di una curva di soli breakpoint non e'
# lineare, e nel brano di mare-nostrum la portano grain.duration (stream6,
# stream8), fill_factor (stream4) e voices.pitch.pitch_range (stream10, step).
# Portati da DMGiulioRomano/mare-nostrum#4 (071683c), sulle stesse fixture.

STREAMS = [s["stream_id"] for s in _brano()["streams"]]


def _motore(tmp_path):
    from granstudies import engine_bridge
    engine_bridge._ensure_engine_on_path()
    engine_bridge._silence_loggers(str(tmp_path / "logs"))
    from pge.envelopes.envelope import Envelope
    return Envelope


_TIPI = {"LinearInterpolation": "linear", "CubicInterpolation": "cubic",
         "StepInterpolation": "step"}


def _tipo_motore(env, t):
    """Il tipo del segmento che parte da t, per l'engine; None fuori dai punti."""
    segs = env.segments
    if not segs[0].start_time <= t < segs[-1].end_time:
        return None
    for s in segs:
        if s.start_time <= t < s.end_time:
            return _TIPI[type(s.strategy).__name__]
    return None


def _inviluppo(v):
    return isinstance(v, list) or (isinstance(v, dict) and "points" in v)


def _leggi(st, path):
    for k in path.split("."):
        if not isinstance(st, dict):
            return None
        st = st.get(k)
    return st


def _vicini(a, b):
    return abs(a - b) <= 1e-12 * max(1.0, abs(a), abs(b))


@node
@engine
@pytest.mark.parametrize("sid", STREAMS)
def test_ogni_breakpoint_si_apre_col_valore_e_il_tipo_del_motore(tmp_path, sid):
    """Niente NaN, e non un'approssimazione: su ogni breakpoint ogni inviluppo
    vale quanto lo valuta l'engine, anche dove il breakpoint e' di un altro
    parametro e il segmento e' `cubic` (PCHIP di Fritsch-Carlson, con le
    tangenti calcolate su tutti i punti) o `step`. E il menu di
    interpolazione di quel breakpoint mostra il tipo del segmento che ne parte.
    """
    Envelope = _motore(tmp_path)
    st = _stream(sid)
    got = _lab(tmp_path, _apri(st)
               + "console.log(JSON.stringify({bps, num: NUM.map(p => p.path)}));\n")
    visti = 0
    for path in got["num"]:
        raw = _leggi(st, path)
        if not _inviluppo(raw):
            continue
        env = Envelope(raw)
        for b in got["bps"]:
            v = b["vals"][path]
            assert isinstance(v, (int, float)), (path, b["t"], v)
            assert _vicini(v, env.evaluate(b["t"])), (path, b["t"], v, env.evaluate(b["t"]))
            tipo = _tipo_motore(env, b["t"])
            if tipo:
                assert b["ints"][path] == tipo, (path, b["t"])
            visti += 1
    assert visti


def _impronte(tmp_path, path):
    """Il fingerprint di ogni stream di un documento, per l'engine
    (`StreamCacheManager.compute_fingerprint`, quello che decide se uno stem
    va rifatto)."""
    _motore(tmp_path)
    from pge.engine.generator import Generator
    from pge.rendering.stream_cache_manager import StreamCacheManager

    g = Generator(str(path))
    g.load_yaml()
    m = StreamCacheManager(str(tmp_path / "manifest.json"), renderer_type="numpy")
    return {s["stream_id"]: m.compute_fingerprint(s) for s in g.data["streams"]}


@node
@engine
@pytest.mark.parametrize("study, radice", [("001-41", MARE_NOSTRUM), ("1-10ms", ROOT)],
                         ids=["001-41", "1-10ms"])
@pytest.mark.parametrize("sid", STREAMS)
def test_criterio_del_piano_ogni_stream_del_brano_risalvato_e_lo_stesso(
        tmp_path, sid, study, radice):
    """Passo 1 di `docs/plans/stream-come-file.md` di mare-nostrum.

    Ogni stream del brano, aperto nel laboratorio e risalvato senza toccare
    niente, da' all'engine lo stesso stream: stesso fingerprint. Il giro e'
    quello vero: YAML -> JSON del server -> pagina -> JSON -> YAML scritto
    come lo scrive `render_doc`. Sulla pagina di 001-41, dove nasce il
    criterio, e su quella di `1-10ms`, dove le manopole sono altre: li'
    `fill_factor` non e' una manopola e resta come scritto, `grain.duration`
    si'.
    """
    from granstudies import serve as S
    doc = _lab(tmp_path, _apri(_stream(sid)) + STAMPA, study=study, radice=radice,
               campioni=["silenzi.wav"] + CAMPIONI)
    salvato = tmp_path / (sid + ".yml")
    with open(salvato, "w") as fh:
        yaml.dump(doc, fh, Dumper=S._Dumper, sort_keys=False, allow_unicode=True)
    brano = os.path.join(MARE_NOSTRUM, "mare-nostrum.yml")
    assert _impronte(tmp_path, salvato)[sid] == _impronte(tmp_path, brano)[sid]


@node
@pytest.mark.parametrize("sid,path", [("stream4", "fill_factor"),
                                      ("stream6", "grain.duration"),
                                      ("stream8", "grain.duration"),
                                      ("stream10", "voices.pitch.pitch_range")])
def test_un_type_points_non_toccato_si_riscrive_nella_sua_forma(tmp_path, sid, path):
    st = _stream(sid)
    doc = _lab(tmp_path, _apri(st) + STAMPA)
    assert _leggi(doc["streams"][0], path) == _leggi(st, path)


@engine
def test_type_points_e_tipo_su_ogni_punto_sono_lo_stesso_inviluppo(tmp_path):
    """La prova che decide la forma di riscrittura, fatta sull'engine.

    `{type: T, points}` (un segmento solo, strategia T su tutti i punti) e la
    lista con T scritto su ogni punto (un segmento per coppia) potrebbero non
    coincidere: le tangenti della cubica si calcolano sui punti del segmento.
    Non e' cosi': l'engine le calcola sempre su TUTTI i punti, e i due
    inviluppi valgono uguale ovunque, integrale compreso (il pointer integra
    speed_ratio), sui quattro `{type, points}` del brano. Per questo un
    `{type, points}` toccato puo' restare tale (tutti i segmenti T) o
    diventare la lista del laboratorio (tipi mescolati) senza che il suono
    cambi. Vale anche col tipo globale e le eccezioni per punto insieme, la
    forma scritta a mano che il laboratorio legge (`curva`) come una lista.
    """
    Envelope = _motore(tmp_path)
    casi = []
    for st in _brano()["streams"]:
        for path in ("grain.duration", "fill_factor", "voices.pitch.pitch_range"):
            d = _leggi(st, path)
            if isinstance(d, dict) and "points" in d:
                casi.append(d)
    assert len(casi) == 4
    # Un toccato: tipo globale cubic, un segmento `linear` e uno `step`.
    casi.append({"type": "cubic", "points": [[0, 2], [0.2, 0.5, "linear"], [0.4, 3],
                                             [0.6, 1, "step"], [0.8, 2.5], [1, 1]]})
    for d in casi:
        P = d["points"]
        lista = [[p[0], p[1], p[2] if len(p) > 2 else d["type"]] for p in P[:-1]] + [P[-1][:2]]
        a, b = Envelope(d), Envelope(lista)
        for i in range(2401):
            t = -0.1 + 1.2 * i / 2400
            assert a.evaluate(t) == b.evaluate(t), (d, t)
        for k in range(1, 41):
            assert _vicini(a.integrate(0, k / 40), b.integrate(0, k / 40)), (d, k)


def _toccato(tmp_path, js):
    """stream4 aperto, `fill_factor` toccato; il documento e i breakpoint."""
    return _lab(tmp_path, _apri(_stream("stream4")) + """
const at = t => bps.findIndex(b => Math.abs(b.t - t) < 1e-9);
""" + js + "console.log(JSON.stringify({doc: labDoc(), bps}));\n")


def _riceve_cio_che_si_vede(Envelope, inv, bps):
    """L'engine, letto il documento, vale su ogni breakpoint quanto il
    laboratorio mostra li', col tipo di segmento che il menu mostra."""
    env = Envelope(inv)
    for b in bps:
        assert _vicini(env.evaluate(b["t"]), b["vals"]["fill_factor"]), b["t"]
        tipo = _tipo_motore(env, b["t"])
        if tipo:
            assert tipo == b["ints"]["fill_factor"], b["t"]


@node
@engine
def test_un_type_points_toccato_resta_type_points(tmp_path):
    """Toccato un valore, i segmenti restano tutti `cubic`: si riscrive
    `{type: cubic, points}`, la forma in cui era arrivato. Il resto dello
    stream non e' stato toccato."""
    Envelope = _motore(tmp_path)
    got = _toccato(tmp_path, "bpLoad(at(0.1631)); "
                             "document.getElementById('P:fill_factor').value = '0.9'; bpSave();\n")
    out = got["doc"]["streams"][0]
    ff = out["fill_factor"]
    assert isinstance(ff, dict) and ff["type"] == "cubic"
    assert all(len(p) == 2 for p in ff["points"])
    assert [0.1631, 0.9] in ff["points"]
    _riceve_cio_che_si_vede(Envelope, ff, got["bps"])
    st = _stream("stream4")
    out["fill_factor"] = st["fill_factor"]
    assert out == st


@node
@engine
def test_un_type_points_coi_tipi_mescolati_si_riscrive_lista(tmp_path):
    """Un segmento passato a `linear` in un `{type: cubic}`: si riscrive la
    lista del laboratorio, col tipo su ogni punto da cui parte una cubica.

    Il dict col tipo globale e le eccezioni sul punto sarebbe per l'engine lo
    stesso inviluppo, ma il laboratorio non lo scrive: PGE-ui non lo
    rileggeva intatto (`wrapEnv`, appena un punto aveva un tipo suo, riscriveva
    la lista piatta e il `type` globale si perdeva). Da DMGiulioRomano/PGE-ui#189
    lo riscrive com'e', ma scriverlo e' una scelta che mare-nostrum, da cui la
    pagina viene, non ha ancora fatto. La lista coi tipi sul punto PGE-ui la
    tiene.
    """
    Envelope = _motore(tmp_path)
    got = _toccato(tmp_path, "bpLoad(at(0.1631)); "
                             "document.getElementById('P:fill_factor').value = '0.9'; bpSave();\n"
                             "bpLoad(at(0.2586)); "
                             "document.getElementById('I:fill_factor').value = 'linear'; bpSave();\n")
    ff = got["doc"]["streams"][0]["fill_factor"]
    assert isinstance(ff, list)
    assert [0.1631, 0.9, "cubic"] in ff and [0.2586, 0.4] in ff
    assert len(ff[-1]) == 2
    _riceve_cio_che_si_vede(Envelope, ff, got["bps"])


@node
def test_un_type_points_che_non_usa_piu_il_suo_tipo_torna_lista(tmp_path):
    """Se nessun segmento e' piu' del tipo globale, `{type: step}` non dice
    piu' niente: torna la lista, che e' la forma di sempre del laboratorio."""
    got = _lab(tmp_path, _apri(_stream("stream10")) + """
for (const b of bps) b.ints['voices.pitch.pitch_range'] = 'linear';
drawTl();
console.log(JSON.stringify(labDoc()));
""")
    pr = got["streams"][0]["voices"]["pitch"]["pitch_range"]
    assert isinstance(pr, list) and all(len(p) == 2 for p in pr)


@node
@engine
def test_segui_il_render_legge_gli_inviluppi_come_il_motore(tmp_path):
    """Fra due breakpoint `segui` mostra il valore della curva dei breakpoint
    come la valuterebbe l'engine: il gradino tiene, la cubica e' una cubica."""
    Envelope = _motore(tmp_path)
    xs = [0.05, 0.12, 0.2, 0.3, 0.33, 0.5, 0.9]
    got = _lab(tmp_path, _apri(_stream("stream4")) + """
const xs = %s;
console.log(JSON.stringify({bps, a: xs.map(x => bpA(x).vals)}));
""" % json.dumps(xs))
    curva = [[b["t"], b["vals"]["fill_factor"], b["ints"]["fill_factor"]] for b in got["bps"]]
    env = Envelope(curva)
    for x, vals in zip(xs, got["a"]):
        assert _vicini(vals["fill_factor"], env.evaluate(x)), x
    step = _lab(tmp_path, _apri(_stream("stream10")) + """
console.log(JSON.stringify([0.2, 0.5].map(x => bpA(x).vals['voices.pitch.pitch_range'])));
""")
    assert step == [0.5, 0]


@node
@engine
def test_il_lucchetto_taglia_un_type_points_dove_la_curva_passa(tmp_path):
    """Lucchetto chiuso, durata dimezzata: i punti tengono il loro tempo in
    secondi, quelli oltre la nuova fine escono, e il punto di chiusura sta
    dove la curva (cubica) passava a meta' della durata vecchia."""
    Envelope = _motore(tmp_path)
    st = _stream("stream4")
    got = _lab(tmp_path, _apri(st) + """
const prima = bps.map(b => [b.t, b.vals['fill_factor'], b.ints['fill_factor']]);
LUCCHETTO = true;
const d = document.getElementById('labDur');
d.value = String(%s / 2);
d.onchange();
console.log(JSON.stringify({prima, doc: labDoc()}));
""" % st["duration"])
    ff = got["doc"]["streams"][0]["fill_factor"]
    assert isinstance(ff, dict) and ff["type"] == "cubic"
    assert ff["points"][-1][0] == 1
    attesa = Envelope(got["prima"]).evaluate(0.5)
    assert _vicini(ff["points"][-1][1], attesa)
    assert got["doc"]["streams"][0]["duration"] == st["duration"] / 2


@node
def test_genera_breakpoint_su_un_type_points(tmp_path):
    """I punti generati prendono i valori a schermo e i tipi dei menu: niente
    NaN, e l'inviluppo resta `{type: cubic}` con i tempi nuovi dentro."""
    got = _lab(tmp_path, _apri(_stream("stream4")) + """
document.getElementById('gN').value = '3';
document.getElementById('gDa').value = '0.4';
document.getElementById('gA').value = '0.6';
genBps();
console.log(JSON.stringify(labDoc()));
""")
    ff = got["streams"][0]["fill_factor"]
    assert isinstance(ff, dict) and ff["type"] == "cubic"
    assert all(isinstance(p[1], (int, float)) for p in ff["points"])
    # Tutti e tre col valore a schermo (quello del primo breakpoint, 2): il
    # punto di mezzo, uguale ai due vicini e dello stesso tipo, non dice
    # niente e `serie` lo lascia fuori, come per ogni inviluppo.
    punti = {p[0]: p[1] for p in ff["points"]}
    assert punti[0.4] == punti[0.6] == 2 and 0.5 not in punti


# I punti `{t, v}` (con `type` facoltativo) sono un'altra scrittura della lista:
# l'`EnvelopeBuilder` dell'engine li normalizza in `[t, v, type]`. Fino alla
# #88 la pagina non li leggeva (stavano fra le forme qui sopra); `curva` li
# legge come la lista, e il gesto e' lo stesso: non toccati restano come sono
# scritti, toccati si riscrivono nella lista del laboratorio — per l'engine lo
# stesso inviluppo.
PUNTI_DICT = [{"t": 0, "v": -6, "type": "step"}, {"t": 0.5, "v": 3}, {"t": 1, "v": 0}]


@node
@engine
def test_i_punti_t_v_si_leggono_come_li_legge_il_motore(tmp_path):
    Envelope = _motore(tmp_path)
    st = dict(_stream("stream2"), volume=PUNTI_DICT)
    got = _lab(tmp_path, _apri(st) + """
const vista = {bps: bps.map(b => [b.t, b.vals['volume'], tipoDi(b, 'volume')]),
               intatto: labDoc()};
""" + _tocca(0, "pitch.ratio", 0.75) + """
vista.altro = labDoc();
""" + _tocca(0, "volume", -9) + """
vista.toccato = labDoc();
console.log(JSON.stringify(vista));
""")
    env = Envelope(PUNTI_DICT)
    ts = [t for t, _v, _tipo in got["bps"]]
    assert 0.5 in ts and 1 in ts                  # i suoi tempi sono breakpoint
    for t, v, tipo in got["bps"]:
        assert _vicini(v, env.evaluate(t)), t
        atteso = _tipo_motore(env, t)
        if atteso:
            assert tipo == atteso, t
    assert got["intatto"]["streams"][0] == st
    # Un altro parametro toccato: i punti `{t, v}` restano come sono scritti.
    assert got["altro"]["streams"][0]["volume"] == PUNTI_DICT
    # Toccati, la lista del laboratorio: per l'engine lo stesso inviluppo, a
    # meno del primo punto, che e' quello toccato.
    vol = got["toccato"]["streams"][0]["volume"]
    assert isinstance(vol, list) and vol[0] == [0, -9, "step"]
    nuovo = Envelope(vol)
    for i in range(1, 101):
        t = 0.5 + 0.5 * i / 100
        assert _vicini(nuovo.evaluate(t), env.evaluate(t)), t


# --- i tempi in secondi sopra lo stream conservato ------------------------------
# Senza `time_mode: normalized` l'engine legge i tempi in secondi (93f201c):
# il laboratorio li porta a frazioni per leggerli (`tempiFrazione`, su una
# copia: lo stream aperto resta com'e' scritto) e li riscrive in secondi
# (`scalaTempi`) solo dove ha toccato — anche dentro un `{type, points}`, che
# la #88 legge e scala nei suoi punti (sotto).

DUR_S = 100.0


def _in_secondi(st):
    """stream2 com'e' scritto senza `time_mode`: gli inviluppi in secondi.

    Anche `grain.read_direction`, che il laboratorio non conosce: l'engine
    legge i suoi tempi con lo stesso `time_mode`.
    """
    st = json.loads(json.dumps(st))
    st.pop("time_mode", None)
    st["duration"] = DUR_S
    for k in ("duration", "read_direction"):
        st["grain"][k] = [[round(p[0] * DUR_S, 6)] + p[1:] for p in st["grain"][k]]
    return st


@node
def test_in_secondi_aperto_e_risalvato_e_lo_stesso_stream(tmp_path):
    st = _in_secondi(_stream("stream2"))
    got = _lab(tmp_path, _apri(st) + "console.log(JSON.stringify({ts: bps.map(b => b.t), "
                                     "doc: labDoc()}));\n")
    assert got["doc"]["streams"][0] == st
    # Sullo schermo i tempi sono frazioni, quelli di `grain.duration`.
    assert got["ts"] == [0, 0.17038, 0.37228, 0.9834]


@node
def test_in_secondi_un_parametro_toccato_si_scrive_in_secondi(tmp_path):
    """Toccato su un breakpoint, `pitch.ratio` diventa un inviluppo coi tempi
    in secondi, e lo stream resta senza `time_mode`; gli inviluppi non toccati
    restano com'erano, nei loro secondi."""
    st = _in_secondi(_stream("stream2"))
    got = _lab(tmp_path, _apri(st) + _tocca(1, "pitch.ratio", 0.5) + STAMPA)
    out = got["streams"][0]
    assert out["pitch"]["ratio"] == [[0, 0.2], [17.038, 0.5], [37.228, 0.2], [98.34, 0.2]]
    assert "time_mode" not in out
    out["pitch"]["ratio"] = st["pitch"]["ratio"]
    assert out == st


def _in_secondi_tp(st):
    """stream4 com'e' scritto senza `time_mode`: gli inviluppi in secondi,
    `fill_factor` che e' un `{type: cubic}` compreso. Prima della #88 la sola
    conversione dei tempi lasciava il dict com'era, cioe' in secondi letti come
    frazioni."""
    st = json.loads(json.dumps(st))
    st.pop("time_mode", None)
    st["duration"] = DUR_S

    def sec(v):
        if isinstance(v, dict):
            return dict(v, points=sec(v["points"]))
        return [[round(p[0] * DUR_S, 6)] + p[1:] for p in v]

    st["fill_factor"] = sec(st["fill_factor"])
    st["grain"]["duration"] = sec(st["grain"]["duration"])
    return st


@node
def test_in_secondi_un_type_points_aperto_e_risalvato_e_lo_stesso_stream(tmp_path):
    st = _in_secondi_tp(_stream("stream4"))
    got = _lab(tmp_path, _apri(st) + "console.log(JSON.stringify({ts: bps.map(b => b.t), "
                                     "doc: labDoc()}));\n")
    assert got["doc"]["streams"][0] == st
    assert all(0 <= t <= 1 for t in got["ts"]) and 0.0926 in got["ts"]


@node
@engine
def test_in_secondi_ogni_breakpoint_vale_quanto_per_il_motore(tmp_path):
    Envelope = _motore(tmp_path)
    st = _in_secondi_tp(_stream("stream4"))
    got = _lab(tmp_path, _apri(st) + "console.log(JSON.stringify(bps));\n")
    for path in ("fill_factor", "grain.duration"):
        env = Envelope(_leggi(st, path))
        for b in got:
            assert _vicini(b["vals"][path], env.evaluate(b["t"] * DUR_S)), (path, b["t"])


@node
@engine
def test_in_secondi_un_type_points_toccato_si_scrive_in_secondi(tmp_path):
    """Toccato resta `{type: cubic}`, coi tempi in secondi, e l'engine vale su
    ogni breakpoint quanto il laboratorio mostra. `grain.duration`, non
    toccato, resta com'era."""
    Envelope = _motore(tmp_path)
    st = _in_secondi_tp(_stream("stream4"))
    got = _lab(tmp_path, _apri(st) + """
const i = bps.findIndex(b => Math.abs(b.t - 0.1631) < 1e-9);
bpLoad(i); document.getElementById('P:fill_factor').value = '0.9'; bpSave();
console.log(JSON.stringify({doc: labDoc(), bps}));
""")
    out = got["doc"]["streams"][0]
    ff = out["fill_factor"]
    assert isinstance(ff, dict) and ff["type"] == "cubic"
    assert [16.31, 0.9] in ff["points"] and ff["points"][-1][0] == DUR_S
    env = Envelope(ff)
    for b in got["bps"]:
        assert _vicini(env.evaluate(b["t"] * DUR_S), b["vals"]["fill_factor"]), b["t"]
    assert out["grain"]["duration"] == st["grain"]["duration"]
    assert "time_mode" not in out


# --- su una pagina di questo repo -----------------------------------------------
# Le manopole di `1-10ms` sono altre (density e grain.duration, piu' quelle che
# ogni pagina ha), e il suo `base:` e' quello di uno sweep: `pointer.speed_ratio:
# 0`, `pointer.loop_unit: absolute`, `sample: silenzi.wav`. Prima della #87 uno
# stream aperto li' ne usciva ricostruito su quel `base:`: stream2 perdeva
# `fill_factor` e `read_direction`, prendeva una `density` dallo schermo, e il
# suo pointer si fermava (speed_ratio 0).

def _qui(tmp_path, scenario):
    return _lab(tmp_path, scenario, study="1-10ms", radice=ROOT,
                campioni=["silenzi.wav"] + CAMPIONI)


@node
def test_su_1_10ms_lo_stream_aperto_resta_lo_stesso(tmp_path):
    st = _stream("stream2")
    assert _qui(tmp_path, _apri(st) + STAMPA)["streams"][0] == st


@node
def test_su_1_10ms_la_manopola_dello_studio_toccata_si_scrive(tmp_path):
    """`grain.duration` e' un asse di 1-10ms: toccato, si scrive come oggi, e il
    resto dello stream — `fill_factor`, il pointer — resta com'era."""
    st = _stream("stream2")
    out = _qui(tmp_path, _apri(st) + _tocca(0, "grain.duration", 0.004) + STAMPA)["streams"][0]
    assert out["grain"]["duration"][0] == [0, 0.004]
    assert "density" not in out
    out["grain"]["duration"] = st["grain"]["duration"]
    assert out == st


@node
def test_su_1_10ms_il_foglio_bianco_nasce_dal_suo_base(tmp_path):
    """Il foglio bianco resta quello di prima: `DEFAULTS` e il `base:` dello
    studio sotto, scritto per intero."""
    out = _qui(tmp_path, "bpAdd();\n" + STAMPA)["streams"][0]
    assert (out["stream_id"], out["onset"], out["time_mode"]) == ("lab", 0, "normalized")
    assert out["grain"] == {"envelope": "hanning", "duration": 0.064}   # base:, DEFAULTS
    assert out["pointer"] == {"speed_ratio": 0}                         # base:
    assert out["sample"] == "silenzi.wav"
    assert out["density"] == 1                     # la prima tacca dello studio
