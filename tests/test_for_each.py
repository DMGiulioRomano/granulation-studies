"""``for_each:`` — l'asse esterno: una combinazione, un render intero.

Il blocco moltiplica i file invece dei gradini: ogni combinazione e' una patch
sullo ``study.yml`` e ha la sua cartella sotto ``generated/<study>/``. Qui
stanno il parse (prodotto cartesiano, etichette, guardie) e il giro completo
della CLI, che e' il punto in cui si vede se le combinazioni restano davvero
separate — cartelle, snapshot e nomi dei ``.sv``.

Portato da mare-nostrum (``tests/test_for_each.py``), piu' i casi che qui
contano e la' no: i nomi d'asse dotted (``grain.duration``, l'asse di quasi
ogni scala di questo studio), ``where`` su uno studio piatto, e l'avviso sulle
combinazioni orfane che il piano promette.
"""
import glob
import os
import shutil
import subprocess

import pytest
import yaml

from granstudies import __main__ as cli
from granstudies import for_each
from granstudies.errors import SpecError


def _combos(block):
    return for_each.parse({"base": {"volume": 0}, "for_each": block})


# --- parse: forme e prodotto cartesiano ------------------------------------

def test_senza_blocco_una_sola_combinazione_vuota():
    # Il caso degenere non e' un ramo speciale: chi itera trova sempre almeno
    # una combinazione, e uno studio senza assi esterni resta com'era.
    assert for_each.parse({"base": {}}) == [for_each.EMPTY]
    assert for_each.parse(None) == [for_each.EMPTY]


def test_manopola_singola_la_chiave_e_il_path():
    combos = _combos({"base.distribution": {"values": [0, 0.5, 1]}})
    assert [c.label for c in combos] == ["distribution=0", "distribution=0.5", "distribution=1"]
    assert combos[1].overrides == {"base.distribution": 0.5}


def test_lista_nuda_e_generatore_sono_la_stessa_cosa():
    assert [c.label for c in _combos({"base.volume": [6, 12]})] == \
           [c.label for c in _combos({"base.volume": {"values": [6, 12]}})]
    # e il vocabolario dei generatori vale tutto: ramp compreso
    assert [c.label for c in _combos({"base.volume": {"ramp": {"start": 0, "stop": 12, "step": 6}}})] == \
           ["volume=0", "volume=6", "volume=12"]


def test_etichetta_toglie_sezione_e_generatore():
    # `base.` e `axes.`, e il nome del generatore in coda, nel nome di una
    # cartella sono rumore: la chiave e' cio' che si muove.
    assert _combos({"base.grain.duration": [0.01]})[0].label == "grain.duration=0.01"
    assert _combos({"axes.fill_factor.values": [1]})[0].label == "fill_factor=1"
    assert _combos({"axes.grain.duration.values": [1]})[0].label == "grain.duration=1"
    assert _combos({"stack.seed": [7]})[0].label == "stack.seed=7"


def test_stati_nominati_per_gli_override_non_scalari():
    combos = _combos({"griglia": {
        "fitta": {"axes.fill_factor.values": [0.5, 1, 2, 4]},
        "rada": {"axes.fill_factor.values": [0.5, 4]},
    }})
    assert [c.label for c in combos] == ["griglia=fitta", "griglia=rada"]
    assert combos[1].overrides == {"axes.fill_factor.values": [0.5, 4]}


def test_bundle_vuoto_e_lo_stato_che_non_tocca_niente():
    combos = _combos({"v": {"originale": {}, "mossa": {"base.volume": 3}}})
    assert [c.label for c in combos] == ["v=originale", "v=mossa"]
    assert combos[0].overrides == {}


def test_prodotto_cartesiano_lessicografico():
    # Primo asse dichiarato = piu' esterno (varia piu' lentamente), come negli
    # orderings dello sweep e negli assi di versions.
    combos = _combos({
        "base.distribution": [0, 1],
        "griglia": {"fitta": {"base.volume": 1}, "rada": {"base.volume": 2}},
    })
    assert [c.label for c in combos] == [
        "distribution=0__griglia=fitta", "distribution=0__griglia=rada",
        "distribution=1__griglia=fitta", "distribution=1__griglia=rada",
    ]
    assert combos[2].overrides == {"base.distribution": 1, "base.volume": 1}


# --- parse: le guardie -----------------------------------------------------

def test_valore_non_scalare_manda_agli_stati_nominati():
    # Una lista non puo' diventare un nome di cartella, e un indice anonimo
    # (d0/ d1/) non dice cosa contiene: il nome lo da' l'utente.
    with pytest.raises(SpecError) as e:
        _combos({"axes.fill_factor.values": {"values": [[1, 2], [3, 4]]}})
    assert "stati nominati" in str(e.value)


def test_stato_non_dict_e_errore():
    with pytest.raises(SpecError) as e:
        _combos({"griglia": {"rada": 0.5}})
    assert "bundle di override" in str(e.value)


def test_stato_che_si_chiama_come_un_generatore_e_errore():
    # `base`/`values`/`ramp` come nome di stato farebbero leggere l'asse come
    # manopola singola: l'errore vero sarebbe arrivato molto piu' in la'.
    with pytest.raises(SpecError) as e:
        _combos({"griglia": {"base": {"base.volume": 1}, "rada": {"base.volume": 2}}})
    assert "nessuno stato puo' chiamarsi" in str(e.value)


def test_uno_stato_solo_che_si_chiama_come_un_generatore_e_errore():
    # Senza uno stato accanto dal nome qualunque, nessuna chiave estranea
    # tradisce l'asse. `values` diventava la lista delle chiavi del bundle:
    # una combinazione sola, `griglia=axes.density.values`, che scriveva quella
    # stringa in una chiave `griglia` alla radice e usciva 0 con la griglia
    # intatta. `ramp` era un TypeError nudo, `base` la banda a cui manca `n`.
    # Il segnale e' il valore: uno stato e' un dict di override, e il
    # parametro di `values` non lo e' mai (quelli di `ramp` e `base` si', ma
    # con le loro chiavi).
    for stato in ("values", "base", "ramp"):
        with pytest.raises(SpecError) as e:
            _combos({"griglia": {stato: {"axes.density.values": [5, 10]}}})
        assert "nessuno stato puo' chiamarsi" in str(e.value), stato
    # la rampa vera resta una rampa
    assert len(_combos({"base.volume": {"ramp": {"start": 0, "stop": 12, "step": 6}}})) == 3


def test_una_banda_con_base_a_envelope_resta_una_banda():
    # Il `base` di una banda puo' essere un Env, `{points, type?, curve?}`:
    # un dict che non e' uno stato. La guardia qui sopra lo prendeva per un
    # bundle e rifiutava un generatore che `resolve` risolve.
    for env in ({"points": [[0, 0], [1, 6]]},
                {"type": "linear", "points": [[0, 0], [1, 6]]}):
        combos = _combos({"base.volume": {"base": env, "n": 3}})
        assert [c.label for c in combos] == ["volume=0", "volume=3", "volume=6"], env


def test_un_envelope_senza_punti_e_un_errore_con_la_posizione():
    # Un Env di banda senza `points` (o con `points` vuoto) usciva da
    # `resolve()` come KeyError/IndexError: fuori da `ctx.wrapping`, cioe'
    # traceback, come il TypeError dei generatori malformati.
    for cfg in (
        {"base": 0, "range": {"type": "step"}, "n": 3},
        {"base": {"type": "step"}, "n": 3},
        {"base": {"points": []}, "n": 3},
    ):
        with pytest.raises(SpecError) as e:
            _combos({"base.volume": cfg})
        assert "base.volume" in str(e.value), cfg


def test_values_senza_lista_e_errore():
    # `values: voce.wav` e' lo sbaglio naturale per un valore solo: list() di
    # una stringa la spezzava in lettere (una cartella per lettera, o un
    # doppione di etichetta che accusava la 'v'), di un numero alzava un
    # TypeError senza posizione ne' rimedio.
    for raw in ("abc", 0.5):
        with pytest.raises(SpecError) as e:
            _combos({"base.sample": {"values": raw}})
        assert "vuole una lista" in str(e.value), raw
        assert f"values: [{raw}]" in str(e.value.hint), raw


def test_un_generatore_malformato_e_un_errore_con_la_posizione():
    # `ctx.wrapping` riavvolge solo i ValueError: un ramp senza `step` (lo
    # sbaglio naturale), un ramp scalare o una banda con un range testuale
    # uscivano come TypeError nudo, cioe' traceback invece del blocco d'errore.
    for cfg in (
        {"ramp": {"start": 0, "stop": 12}},
        {"ramp": 5},
        {"base": 0, "range": "sei", "n": 3},
    ):
        with pytest.raises(SpecError) as e:
            _combos({"base.volume": cfg})
        assert "base.volume" in str(e.value), cfg
    # un numero non finito non ha un nome di cartella: `_fmt` alzava
    # OverflowError (inf) o ValueError fuori da ogni contesto (nan)
    for v in (float("inf"), float("nan")):
        with pytest.raises(SpecError) as e:
            _combos({"base.volume": [0, v]})
        assert "finito" in str(e.value), v


def test_un_nome_d_asse_o_un_path_che_non_e_una_stringa_e_un_errore():
    # YAML fa numeri e booleani anche delle chiavi (`2024:`, `on:`): un nome
    # d'asse o un path di bundle cosi' arrivava a `_slug`/`_short`/`_set_path`
    # e usciva come TypeError/AttributeError, cioe' traceback. Il rimedio e'
    # scriverlo fra virgolette.
    for block in (
        {1: [0, 6]},                                  # Forma 1: il path e' la chiave
        {2024: {"a": {}}},                            # Forma 2: il nome dell'asse
        {True: {"a": {}}},                            # `on:` in YAML 1.1
        {"griglia": {"a": {1: 2}}},                   # un path dentro un bundle
    ):
        with pytest.raises(SpecError) as e:
            _combos(block)
        assert "stringa" in str(e.value), block
        assert "virgolette" in str(e.value.hint), block
    # Uno stato resta libero: e' un nome, non un path, e finisce nella label
    # com'e' scritto (`griglia=1`).
    assert [c.label for c in _combos({"griglia": {1: {}, 2: {}}})] == [
        "griglia=1", "griglia=2"]


def test_un_path_con_un_segmento_vuoto_e_un_errore():
    # `base.` (il punto in piu' in coda) creava in silenzio una chiave '' dentro
    # `base:`, che nessuno legge: la guardia sulle sezioni inesistenti non la
    # vedeva, perche' `base` esiste. Un segmento vuoto e' sempre un refuso.
    for block in (
        {"base.": [0, 6]},
        {".base.volume": [0, 6]},
        {"griglia": {"a": {"base..volume": 6}}},
    ):
        with pytest.raises(SpecError) as e:
            _combos(block)
        assert "segmento vuoto" in str(e.value), block


def test_etichette_gemelle_sono_errore():
    with pytest.raises(SpecError) as e:
        _combos({"base.distribution": [0], "axes.distribution.values": [1]})
    assert "stessa etichetta" in str(e.value)


def test_due_valori_con_la_stessa_etichetta_sono_errore():
    # Dentro un asse, due valori (o due stati) che si scrivono uguali nel nome
    # della cartella darebbero due combinazioni in una cartella sola: la
    # seconda riscriverebbe la prima in silenzio, e `where` la stamperebbe due
    # volte. Il doppione vero, `1` e `1.0`, e lo slug che fonde due nomi
    # diversi sono lo stesso difetto.
    for block in ({"base.volume": [0, 0]},
                  {"base.volume": [1, 1.0]},
                  {"base.sample": ["voce 1.wav", "voce_1.wav"]},
                  {"g": {"a b": {"base.volume": 1}, "a_b": {"base.volume": 2}}}):
        with pytest.raises(SpecError) as e:
            _combos(block)
        assert "stessa cartella" in str(e.value), block


def test_etichette_che_differiscono_solo_per_maiuscole_sono_errore():
    # Sul filesystem di default di macOS `griglia=Rada` e `griglia=rada` sono
    # la stessa cartella: la seconda combinazione riscriverebbe la prima in
    # silenzio, come per il doppione vero.
    for block in ({"g": {"Rada": {"base.volume": 1}, "rada": {"base.volume": 2}}},
                  {"base.sample": ["Voce.wav", "voce.wav"]}):
        with pytest.raises(SpecError) as e:
            _combos(block)
        assert "stessa cartella" in str(e.value), block


def test_due_assi_sullo_stesso_path_sono_errore():
    # Il valore finale dipenderebbe dall'ordine di dichiarazione, che qui non
    # e' una precedenza dichiarata.
    with pytest.raises(SpecError) as e:
        _combos({"a": {"x": {"base.volume": 1}}, "b": {"y": {"base.volume": 2}}})
    assert "toccano" in str(e.value)


def test_due_assi_su_path_annidati_sono_errore():
    # Stesso difetto di due assi sullo stesso path, un livello sotto: il
    # valore viene *assegnato*, quindi `base.grain` di un asse cancella o
    # viene cancellato dal `base.grain.duration` dell'altro, secondo l'ordine.
    with pytest.raises(SpecError) as e:
        _combos({"a": {"x": {"base.grain": {"duration": 0.01}}},
                 "base.grain.duration": [0.02]})
    assert "toccano" in str(e.value)


def test_blocco_vuoto_o_malformato_e_errore():
    for block in ({}, [], "distribution"):
        with pytest.raises(SpecError):
            for_each.parse({"for_each": block})


# --- apply: la patch -------------------------------------------------------

def test_apply_assegna_il_path_e_toglie_il_blocco():
    doc = {"base": {"volume": 0, "grain": {"envelope": "hanning"}},
           "for_each": {"base.volume": [6]}}
    out = for_each.apply(doc, _combos({"base.volume": [6]})[0])
    assert out == {"base": {"volume": 6, "grain": {"envelope": "hanning"}}}
    assert doc["base"]["volume"] == 0          # l'originale non si tocca
    assert "for_each" in doc


def test_apply_crea_una_chiave_nuova_ma_non_una_sezione():
    doc = {"base": {"volume": 0}}
    out = for_each.apply(doc, for_each.Combo("x", (("base.pan_range", 360),)))
    assert out["base"]["pan_range"] == 360
    # `bse.pan_range` sarebbe un refuso che passa in silenzio senza muovere nulla
    with pytest.raises(SpecError) as e:
        for_each.apply(doc, for_each.Combo("x", (("bse.pan_range", 360),)))
    assert "non esiste nel documento" in str(e.value)


def test_apply_di_combinazione_vuota_toglie_comunque_il_blocco():
    # Da qui in giu' il documento e' uno studio normale: nessun parser deve
    # conoscere l'esistenza degli assi esterni.
    assert for_each.apply({"base": {}, "for_each": {"base.volume": [6]}},
                          for_each.EMPTY) == {"base": {}}


def test_apply_raggiunge_un_asse_dal_nome_dotted():
    # `grain.duration` e' una chiave sola di `axes:`, non `grain` -> `duration`:
    # spezzare il path su ogni punto non lo troverebbe mai, e su questo studio
    # e' l'asse di quasi ogni scala.
    doc = {"axes": {"density": {"values": [5, 50]},
                    "grain.duration": {"values": [0.001, 0.01]}}}
    out = for_each.apply(
        doc, for_each.Combo("g", (("axes.grain.duration.values", [0.001, 0.005]),)))
    assert out["axes"]["grain.duration"] == {"values": [0.001, 0.005]}
    assert "grain" not in out["axes"]
    # e la chiave nuova sotto l'asse dotted si crea come le altre
    out = for_each.apply(
        doc, for_each.Combo("g", (("axes.grain.duration.baseline", 0.004),)))
    assert out["axes"]["grain.duration"]["baseline"] == 0.004


def test_apply_su_un_nome_dotted_ambiguo_e_errore():
    # Assi `grain` e `grain.duration` entrambi dichiarati: `axes.grain.duration.x`
    # puo' voler dire l'uno o l'altro. Come per le chiavi puntate di `streams:`,
    # e' un errore esplicito, mai una scelta silenziosa.
    doc = {"axes": {"grain": {"duration": {"values": [1]}},
                    "grain.duration": {"values": [2]}}}
    with pytest.raises(SpecError) as e:
        for_each.apply(doc, for_each.Combo("g", (("axes.grain.duration.values", [3]),)))
    assert "ambiguo" in str(e.value)


# --- CLI: dove si scrive ---------------------------------------------------

_DOC = {
    "study_id": "s_fe",
    "seed": 7,
    "samples_dir": "samples",
    "base": {"onset": 0, "sample": "corpus.wav", "duration": 10, "volume": 0,
             "time_mode": "normalized", "grain": {"envelope": "hanning"}},
    "axes": {"density": {"path": "density", "baseline": 20, "values": [5, 50]}},
    "sweep": {"mode": "envelope", "orders": [1], "plateau": 5, "transition": 5},
    "for_each": {"base.volume": {"values": [0, 6]}},
}


def _studio(tmp_path, monkeypatch, doc=None):
    monkeypatch.setattr(cli, "REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("COMBO", raising=False)
    sdir = tmp_path / "studies" / "s_fe"
    sdir.mkdir(parents=True)
    (sdir / "study.yml").write_text(yaml.safe_dump(doc or _DOC, sort_keys=False))
    return sdir


def test_gen_dir_scende_di_un_livello_solo_con_la_combinazione(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "REPO_ROOT", str(tmp_path))
    assert cli.gen_dir("s1") == os.path.join(str(tmp_path), "generated", "s1")
    monkeypatch.setattr(cli, "_COMBO", for_each.Combo("volume=6", (("base.volume", 6),)))
    assert cli.gen_dir("s1") == os.path.join(str(tmp_path), "generated", "s1", "volume=6")


def test_combo_filtra_e_una_label_sbagliata_e_errore(tmp_path, monkeypatch):
    _studio(tmp_path, monkeypatch)
    assert [c.label for c in cli._combos("s_fe")] == ["volume=0", "volume=6"]
    monkeypatch.setenv("COMBO", "volume=6")
    assert [c.label for c in cli._combos("s_fe")] == ["volume=6"]
    monkeypatch.setenv("COMBO", "volume=99")
    with pytest.raises(SpecError) as e:
        cli._combos("s_fe")
    # L'elenco sta nel rimedio, che il blocco d'errore rimpagina con
    # textwrap: gli a-capo si perderebbero e le label si incollerebbero fra
    # loro, quindi il separatore e' una virgola, che sopravvive.
    assert "volume=0, volume=6." in str(e.value)
    assert "volume=0, volume=6." in e.value.format_block().replace("\n" + " " * 14, " ")


def _fake_engine(monkeypatch):
    import granstudies.render as render_mod

    def fake(yaml_path, output_path, samples_dir, output_sr=48000,
             per_stream=False, use_cache=False, cache_dir=None, jobs=1):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as fh:
            fh.write(open(yaml_path).read())
        return [output_path]

    monkeypatch.setattr(render_mod.engine_bridge, "render", fake)


def test_il_giro_completo_produce_una_cartella_per_combinazione(tmp_path, monkeypatch):
    _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0

    g = tmp_path / "generated" / "s_fe"
    assert sorted(p.name for p in g.iterdir()) == ["volume=0", "volume=6"]
    for label, atteso in (("volume=0", 0), ("volume=6", 6)):
        # lo snapshot e' il documento PATCHATO: dice da se' i valori della
        # combinazione, senza rimandare al blocco for_each:
        snap = yaml.safe_load((g / label / "study.yml").read_text())
        assert snap["base"]["volume"] == atteso
        assert "for_each" not in snap
        variante = next((g / label / "yaml").rglob("*.yml"))
        assert yaml.safe_load(variante.read_text())["streams"][0]["volume"] == atteso
    # e l'audio delle due combinazioni e' diverso davvero
    a0 = next((g / "volume=0" / "audio").rglob("*.aif")).read_text()
    a6 = next((g / "volume=6" / "audio").rglob("*.aif")).read_text()
    assert a0 != a6


def test_lo_snapshot_e_il_documento_letto_all_inizio_del_render(tmp_path, monkeypatch):
    # Un render dura minuti, e nel frattempo lo study.yml si tocca (e' il ciclo
    # di lavoro: ascolto, modifica, rigenera). Lo snapshot deve dire il
    # documento che ha prodotto l'audio, non quello trovato alla fine.
    import granstudies.render as render_mod

    sdir = _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    motore = render_mod.engine_bridge.render

    def modifica_durante_il_render(*a, **kw):
        doc = dict(_DOC, base=dict(_DOC["base"], duration=99))
        (sdir / "study.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
        return motore(*a, **kw)

    monkeypatch.setattr(render_mod.engine_bridge, "render", modifica_durante_il_render)
    monkeypatch.setenv("COMBO", "volume=0")
    assert cli.main(["render", "s_fe", "--no-score", "--jobs", "1"]) == 0
    snap = yaml.safe_load(
        (tmp_path / "generated" / "s_fe" / "volume=0" / "study.yml").read_text())
    assert snap["base"]["duration"] == 10


def test_una_patch_su_axes_cambia_le_varianti_generate(tmp_path, monkeypatch):
    doc = dict(_DOC, for_each={"griglia": {
        "corta": {"axes.density.values": [5, 50]},
        "lunga": {"axes.density.values": [5, 20, 50]},
    }})
    _studio(tmp_path, monkeypatch, doc)
    assert cli.main(["sweep", "s_fe"]) == 0
    g = tmp_path / "generated" / "s_fe"
    corta = next((g / "griglia=corta" / "yaml").rglob("*.yml"))
    lunga = next((g / "griglia=lunga" / "yaml").rglob("*.yml"))
    punti = lambda p: len(yaml.safe_load(p.read_text())["streams"][0]["density"]["points"])
    assert punti(lunga) > punti(corta)


def test_una_patch_su_un_asse_dotted_arriva_allo_sweep(tmp_path, monkeypatch):
    # Il caso tipico di questo studio: due griglie di grain.duration, un file
    # per griglia. Il path attraversa il nome d'asse dotted.
    doc = dict(_DOC,
               axes={"grain.duration": {"baseline": 0.005, "values": [0.001, 0.01]}},
               for_each={"griglia": {
                   "corta": {"axes.grain.duration.values": [0.001, 0.01]},
                   "lunga": {"axes.grain.duration.values": [0.001, 0.004, 0.01]},
               }})
    _studio(tmp_path, monkeypatch, doc)
    assert cli.main(["sweep", "s_fe"]) == 0
    g = tmp_path / "generated" / "s_fe"

    def punti(label):
        variante = next((g / label / "yaml").rglob("*.yml"))
        return len(yaml.safe_load(variante.read_text())["streams"][0]["grain"]["duration"]["points"])

    assert punti("griglia=lunga") > punti("griglia=corta")


def test_combo_restringe_il_giro(tmp_path, monkeypatch):
    _studio(tmp_path, monkeypatch)
    monkeypatch.setenv("COMBO", "volume=6")
    assert cli.main(["sweep", "s_fe"]) == 0
    g = tmp_path / "generated" / "s_fe"
    assert [p.name for p in g.iterdir()] == ["volume=6"]


def test_where_stampa_una_root_per_combinazione(tmp_path, monkeypatch, capsys):
    _studio(tmp_path, monkeypatch)
    assert cli.main(["where", "s_fe"]) == 0
    out = capsys.readouterr().out.split()
    assert out == [str(tmp_path / "generated" / "s_fe" / "volume=0"),
                   str(tmp_path / "generated" / "s_fe" / "volume=6")]


def test_where_rispetta_combo(tmp_path, monkeypatch, capsys):
    # E' la riga che la funzione zsh `study` legge per sapere cosa aprire:
    # `COMBO=volume=6 study s_fe` deve aprire la sola combinazione scelta.
    _studio(tmp_path, monkeypatch)
    monkeypatch.setenv("COMBO", "volume=6")
    assert cli.main(["where", "s_fe"]) == 0
    assert capsys.readouterr().out.split() == [
        str(tmp_path / "generated" / "s_fe" / "volume=6")]


def test_where_senza_for_each_stampa_la_cartella_piatta(tmp_path, monkeypatch, capsys):
    doc = {k: v for k, v in _DOC.items() if k != "for_each"}
    _studio(tmp_path, monkeypatch, doc)
    assert cli.main(["where", "s_fe"]) == 0
    captured = capsys.readouterr()
    assert captured.out.split() == [str(tmp_path / "generated" / "s_fe")]
    # niente intestazione `[for_each]`: l'uscita di where si legge riga per riga
    assert "[for_each]" not in captured.out


def test_sv_di_combinazioni_diverse_hanno_nomi_diversi(tmp_path, monkeypatch):
    """Sonic Visualiser identifica la sessione dal nome file: due combinazioni
    dello stesso studio devono produrre .sv distinguibili, altrimenti la
    seconda non si apre mentre la prima e' aperta — e il confronto fra
    combinazioni e' il motivo per cui gli assi esterni esistono."""
    import granstudies.sv_export as sv_export

    _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    esportati = []
    monkeypatch.setattr(
        sv_export, "variant_to_sv",
        lambda variant, audio, out, layout, markers, markers_scope: esportati.append(out),
    )
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    assert cli.main(["sv", "s_fe"]) == 0

    nomi = [os.path.basename(p) for p in esportati]
    assert len(nomi) == 2, nomi          # una variante per combinazione
    assert len(nomi) == len(set(nomi)), nomi
    assert all("volume=0" in n or "volume=6" in n for n in nomi)


_STUDY_FN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         ".zsh_completions", "_study")


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh non installato")
def test_study_zsh_non_apre_le_sessioni_degli_stem_di_una_combinazione(
        tmp_path, monkeypatch, capsys):
    """La funzione ``study`` apre il ``.sv`` di ogni documento contro il mix e
    lascia fuori quello contro gli stem. La label di combinazione va in coda al
    basename anche per gli stem, quindi il riconoscimento deve reggere anche
    ``..._stems__<label>.sv``, non solo ``..._stems.sv``. I nomi non sono
    scritti qui: li produce ``cmd_sv``, e il test chiede solo che quelli
    aperti siano i suoi ``.sv`` senza stem."""
    import granstudies.sv_export as sv_export

    doc = {k: v for k, v in _DOC.items() if k != "sweep"}
    doc["stack"] = {}
    _studio(tmp_path, monkeypatch, doc)

    def scrivi(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").close()
        return True

    monkeypatch.setattr(sv_export, "stack_to_sv",
                        lambda variant, audio, out, layout, axis_paths=None: scrivi(out))
    monkeypatch.setattr(sv_export, "stack_stems_to_sv",
                        lambda variant, audio_dir, out, process="stack",
                        axis_paths=None: scrivi(out))

    assert cli.main(["where", "s_fe"]) == 0
    roots = capsys.readouterr().out.split()
    assert len(roots) == 2
    for root in roots:          # il documento stack e il suo mix, per combinazione
        for sub, nome in (("yaml", "stack.yml"), ("audio", "stack.aif")):
            os.makedirs(os.path.join(root, sub, "stack"))
            open(os.path.join(root, sub, "stack", nome), "w").close()
    assert cli.main(["sv", "s_fe"]) == 0
    prodotti = sorted(p for r in roots for p in glob.glob(os.path.join(r, "sv", "**", "*.sv"),
                                                          recursive=True))
    mix = [p for p in prodotti if "_stems" not in os.path.basename(p)]
    assert len(prodotti) == 4 and len(mix) == 2, prodotti

    # `make` finto: `where` risponde con le root della CLI vera, il resto
    # (all-study, sv) e' gia' stato fatto qui sopra.
    script = (
        "compdef() { : }\n"
        "make() { [[ $1 == where ]] && print -rl -- ${(f)ROOTS}; return 0 }\n"
        "sonic() { print -r -- \"$1\" }\n"
        f"source '{_STUDY_FN}'\n"
        "study s_fe\n"
    )
    res = subprocess.run(["zsh", "-f", "-c", script], cwd=tmp_path, text=True,
                         capture_output=True, env=dict(os.environ, ROOTS="\n".join(roots)))
    assert res.returncode == 0, res.stderr
    assert sorted(res.stdout.split("\n")[:-1]) == mix


def test_senza_for_each_lo_stesso_albero_piatto(tmp_path, monkeypatch):
    # Il caso degenere non e' un ramo speciale: senza assi esterni l'albero e'
    # quello di sempre, generated/<study>/{yaml,audio,...}, niente
    # sotto-cartella di combinazione e niente suffisso nei .sv. In piu' c'e'
    # solo lo snapshot study.yml, che il render scrive per ogni combinazione.
    doc = {k: v for k, v in _DOC.items() if k != "for_each"}
    _studio(tmp_path, monkeypatch, doc)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    assert cli.sv_combo_suffix() == ""

    g = tmp_path / "generated" / "s_fe"
    assert not [p.name for p in g.iterdir() if "=" in p.name]
    assert (g / "yaml" / "sweep").is_dir()
    assert next((g / "audio" / "sweep").rglob("*.aif"))
    snap = yaml.safe_load((g / "study.yml").read_text())
    assert snap == doc


# --- COMBO come filtro per fette -------------------------------------------

_DOC_4 = dict(_DOC, for_each={
    "base.volume": {"values": [0, 6]},
    "base.pan": {"values": [0, 90]},
})


def test_combo_seleziona_una_fetta_non_solo_una_combinazione(tmp_path, monkeypatch):
    # Con piu' assi esterni la label intera e' lunga da scrivere e la domanda
    # e' quasi sempre parziale: "tutte le pan a volume 6".
    _studio(tmp_path, monkeypatch, _DOC_4)
    assert [c.label for c in cli._combos("s_fe")] == [
        "volume=0__pan=0", "volume=0__pan=90", "volume=6__pan=0", "volume=6__pan=90"]
    monkeypatch.setenv("COMBO", "volume=6")
    assert [c.label for c in cli._combos("s_fe")] == ["volume=6__pan=0", "volume=6__pan=90"]
    # i vincoli sono in and, in qualunque ordine
    monkeypatch.setenv("COMBO", "pan=90__volume=0")
    assert [c.label for c in cli._combos("s_fe")] == ["volume=0__pan=90"]


def test_il_match_e_per_segmento_intero(tmp_path, monkeypatch):
    # `distribution=0` non deve prendersi anche `distribution=0.3`.
    _studio(tmp_path, monkeypatch, dict(_DOC, for_each={"base.volume": {"values": [0, 0.3]}}))
    monkeypatch.setenv("COMBO", "volume=0")
    assert [c.label for c in cli._combos("s_fe")] == ["volume=0"]


def test_il_separatore_non_compare_dentro_un_segmento():
    # `__` separa gli assi nella label, e COMBO la spezza li'. Un valore o uno
    # stato che lo contiene da se' (`brano__s1.wav`, il nome di uno stem del
    # motore; lo stato `a__b`), o che finisce con `_` e lo forma col
    # separatore, spezzava un segmento in due: `COMBO=g=a` prendeva anche
    # `g=a__b`, e `COMBO=s1.wav` selezionava un valore che non esiste.
    combos = _combos({"base.sample": ["brano__s1.wav", "voce_"],
                      "g": {"a": {}, "a__b": {}}})
    assert [c.label for c in combos] == [
        "sample=brano_s1.wav__g=a", "sample=brano_s1.wav__g=a_b",
        "sample=voce__g=a", "sample=voce__g=a_b"]
    for c in combos:
        assert all(s.count("=") == 1 for s in c.label.split("__")), c.label


def test_combo_non_prende_uno_stato_che_ne_contiene_il_nome(tmp_path, monkeypatch):
    _studio(tmp_path, monkeypatch, dict(_DOC, for_each={
        "g": {"a": {"base.volume": 1}, "a__b": {"base.volume": 2}}}))
    monkeypatch.setenv("COMBO", "g=a")
    assert [c.label for c in cli._combos("s_fe")] == ["g=a"]
    # e il rimedio dice qual e' il separatore dei vincoli
    monkeypatch.setenv("COMBO", "g=c")
    with pytest.raises(SpecError) as e:
        cli._combos("s_fe")
    assert "'__'" in str(e.value.hint)


# --- combinazioni orfane ---------------------------------------------------

def test_una_combinazione_tolta_dal_blocco_e_segnalata_non_cancellata(
        tmp_path, monkeypatch, capsys):
    # Togliere un valore da for_each lascia la sua cartella con l'audio gia'
    # ascoltato: spesso e' proprio il «prima» da riascoltare. Come per le
    # varianti orfane dello sweep: avviso, nessuna cancellazione.
    sdir = _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    doc = dict(_DOC, for_each={"base.volume": {"values": [6, 12]}})
    (sdir / "study.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    capsys.readouterr()

    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    err = capsys.readouterr().err
    g = tmp_path / "generated" / "s_fe"
    assert str(g / "volume=0") in err
    assert str(g / "volume=6") not in err and str(g / "volume=12") not in err
    assert err.count("orfan") == 1         # una volta sola, non una per combinazione
    assert (g / "volume=0" / "study.yml").is_file()


def test_l_albero_piatto_di_prima_e_orfano_sotto_for_each(tmp_path, monkeypatch, capsys):
    # Aggiungere for_each a uno studio gia' generato lascia l'albero piatto
    # accanto alle combinazioni: `study` non lo apre piu', e va detto.
    doc = {k: v for k, v in _DOC.items() if k != "for_each"}
    sdir = _studio(tmp_path, monkeypatch, doc)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    (sdir / "study.yml").write_text(yaml.safe_dump(_DOC, sort_keys=False))
    capsys.readouterr()

    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    err = capsys.readouterr().err
    assert "albero piatto" in err
    assert (tmp_path / "generated" / "s_fe" / "yaml").is_dir()


def test_l_avviso_sull_albero_piatto_nomina_le_sue_cartelle_non_la_radice(
        tmp_path, monkeypatch, capsys):
    # La radice `generated/<study>/` e' l'albero piatto, ma da quando c'e'
    # for_each: tiene anche le combinazioni vive. Nominarla fra le orfane e
    # chiudere con «rimuovile a mano» era un consiglio che cancellava l'audio
    # appena renderizzato: l'avviso nomina le cartelle dell'albero piatto, che
    # si possono togliere davvero.
    doc = {k: v for k, v in _DOC.items() if k != "for_each"}
    sdir = _studio(tmp_path, monkeypatch, doc)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    (sdir / "study.yml").write_text(yaml.safe_dump(_DOC, sort_keys=False))
    capsys.readouterr()

    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    err = capsys.readouterr().err
    g = tmp_path / "generated" / "s_fe"
    # le righe indentate sono l'elenco: la prosa resta una frase, non un path
    indicati = {riga.strip() for riga in err.splitlines() if riga[:1].isspace()}
    assert str(g) not in indicati, err
    assert {str(g / "yaml"), str(g / "audio"), str(g / "study.yml")} <= indicati, err
    # e cio' che la radice tiene e' vivo: e' l'audio di questo render
    assert (g / "volume=0" / "audio").is_dir() and (g / "volume=6" / "audio").is_dir()


def test_una_cache_dir_esplicita_alla_radice_non_e_un_albero_piatto(
        tmp_path, monkeypatch, capsys):
    # L'elenco dell'albero piatto nomina anche `cache/`, ma il *segnale* che
    # l'albero c'e' restano `yaml/` e `audio/`: con `CACHE_DIR` puntata alla
    # radice, la cache divisa per combinazione crea `generated/<study>/cache`
    # senza che di albero piatto ce ne sia uno. Un avviso che grida dove non
    # c'e' niente e' il primo che si impara a saltare.
    _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    g = tmp_path / "generated" / "s_fe"
    cdir = g / "cache"
    # i manifest li scrive l'engine, che qui e' finto: la cartella per
    # combinazione e' quella che `cmd_render` gli passa (vedi il test sopra).
    (cdir / "volume=0").mkdir(parents=True)
    capsys.readouterr()

    assert cli.main(["render", "s_fe", "--no-score", "--cache-dir", str(cdir)]) == 0
    assert "orfan" not in capsys.readouterr().err


def test_la_cartella_di_una_combinazione_dichiarata_non_e_orfana_con_un_altro_nome(
        tmp_path, monkeypatch, capsys):
    # Sul filesystem di default di macOS `griglia=Rada` e `griglia=rada` sono
    # la stessa cartella: dopo aver rinominato lo stato solo nelle maiuscole il
    # render scrive nella cartella di prima, che listdir restituisce col nome
    # vecchio. Confrontata per nome, l'avviso la dava per orfana e consigliava
    # di cancellarla: era quella viva. Qui due nomi per una cartella li da' un
    # symlink, che e' la stessa situazione su un filesystem case-sensitive.
    doc = dict(_DOC, for_each={"griglia": {"rada": {"base.volume": 0}}})
    _studio(tmp_path, monkeypatch, doc)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    g = tmp_path / "generated" / "s_fe"
    (g / "griglia=Rada").symlink_to(g / "griglia=rada", target_is_directory=True)
    capsys.readouterr()

    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    assert "orfan" not in capsys.readouterr().err


def test_una_cache_dir_esplicita_si_separa_per_combinazione(tmp_path, monkeypatch):
    # Il manifest della cache stem si chiama come lo YAML (`stack.json`,
    # `<variante>.json`), e i basename sono gli stessi in ogni combinazione.
    # Con `--cache-dir` (`make render CACHE_DIR=...`) condivisa, una
    # combinazione trovava il fingerprint scritto da un'altra: dopo una
    # modifica renderizzata con COMBO su una fetta, l'altra fetta vedeva lo
    # stream "clean" e teneva lo stem vecchio che aveva su disco.
    import granstudies.render as render_mod

    _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    motore = render_mod.engine_bridge.render
    viste = {}

    def registra(yaml_path, output_path, samples_dir, output_sr=48000,
                 per_stream=False, use_cache=False, cache_dir=None, jobs=1):
        if per_stream:
            label = os.path.relpath(output_path, tmp_path / "generated" / "s_fe")
            viste[label.split(os.sep)[0]] = cache_dir
        return motore(yaml_path, output_path, samples_dir, output_sr=output_sr,
                      per_stream=per_stream, use_cache=use_cache, cache_dir=cache_dir)

    monkeypatch.setattr(render_mod.engine_bridge, "render", registra)
    assert cli.main(["sweep", "s_fe"]) == 0
    cdir = str(tmp_path / "cache_condivisa")
    assert cli.main(["render", "s_fe", "--no-score", "--jobs", "1",
                     "--cache-dir", cdir]) == 0
    assert viste == {"volume=0": os.path.join(cdir, "volume=0"),
                     "volume=6": os.path.join(cdir, "volume=6")}


def test_una_cache_dir_esplicita_resta_quella_senza_for_each(tmp_path, monkeypatch):
    import granstudies.render as render_mod

    _studio(tmp_path, monkeypatch, {k: v for k, v in _DOC.items() if k != "for_each"})
    _fake_engine(monkeypatch)
    motore = render_mod.engine_bridge.render
    viste = []

    def registra(*a, **kw):
        if kw.get("per_stream"):
            viste.append(kw.get("cache_dir"))
        return motore(*a, **kw)

    monkeypatch.setattr(render_mod.engine_bridge, "render", registra)
    assert cli.main(["sweep", "s_fe"]) == 0
    cdir = str(tmp_path / "cache_condivisa")
    assert cli.main(["render", "s_fe", "--no-score", "--jobs", "1",
                     "--cache-dir", cdir]) == 0
    assert viste == [cdir]


def test_senza_orfane_nessun_avviso(tmp_path, monkeypatch, capsys):
    _studio(tmp_path, monkeypatch)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", "s_fe"]) == 0
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    # e con COMBO le combinazioni non scelte non sono orfane: sono dichiarate
    monkeypatch.setenv("COMBO", "volume=6")
    assert cli.main(["render", "s_fe", "--no-score"]) == 0
    assert "orfan" not in capsys.readouterr().err
