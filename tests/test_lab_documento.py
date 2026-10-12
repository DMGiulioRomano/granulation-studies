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


# --- i tempi in secondi sopra lo stream conservato ------------------------------
# Senza `time_mode: normalized` l'engine legge i tempi in secondi (93f201c):
# il laboratorio li porta a frazioni per leggerli (`tempiFrazione`, su una
# copia: lo stream aperto resta com'e' scritto) e li riscrive in secondi
# (`scalaTempi`) solo dove ha toccato. Gli inviluppi `{type, points}` in secondi
# sono della #88.

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
