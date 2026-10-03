"""Le tacche del laboratorio: da dove vengono i valori fra cui si sceglie.

``lab_data`` legge lo ``study.yml`` **cosi' com'e' scritto** e per ogni
parametro ne ricava la lista di valori che vale la pena sentire. I generatori
li risolve con ``value_generators.resolve`` — lo stesso di ``for_each:`` —
quindi ``ramp:`` e le bande danno tacche come ``values:``, e gli assi scritti
dentro ``streams:`` entrano come il documento (issue #77).

Qui si verifica il *contratto*, non il contenuto degli studi reali: quelli
sono dell'utente e cambiano a ogni sessione d'ascolto. L'invariante sul corpus
vero (il laboratorio si apre sempre, e ogni asse dichiarato diventa una
manopola) sta in ``test_studies_corpus.py``.
"""
import copy

import pytest

from granstudies.graph import lab_data


def _params(doc, study_id=None):
    return {p["path"]: p for p in lab_data(doc, study_id)["params"]}


# --- i generatori: ramp e bande, non solo `values:` ------------------------

def test_una_ramp_diventa_tacche():
    """Il caso della gran parte degli studi di questo repo: l'asse e' una
    rampa, e prima non dava nessuna manopola."""
    p = _params({"axes": {"density": {"ramp": {"start": 1, "stop": 10, "step": 3},
                                      "baseline": 20}}})["density"]
    assert p["values"] == [1, 4, 7, 10]
    assert p["kind"] == "num"
    # Con le tacche non e' una manopola libera: il menu `▾` ce l'ha.
    assert "free" not in p


def test_una_banda_con_n_diventa_tacche():
    """La banda e' deterministica sul suo seed: le tacche sono quelle che il
    render sentirebbe, non altri pescaggi."""
    doc = {"axes": {"density": {"base": 10, "range": 5, "n": 4, "seed": 7}}}
    p = _params(doc)["density"]
    assert len(p["values"]) == 4
    assert all(10 <= v <= 15 for v in p["values"])
    assert _params(copy.deepcopy(doc))["density"]["values"] == p["values"]


def test_una_banda_collassata_segue_base_e_i_duplicati_cadono():
    """``range`` omesso = banda collassata: n volte lo stesso valore. Come
    tacca e' una sola — un menu con quattro righe identiche non e' un menu."""
    p = _params({"axes": {"density": {"base": 10, "n": 4}}})["density"]
    assert p["values"] == [10]


def test_una_banda_senza_n_non_da_tacche_ma_la_manopola_resta():
    """Senza ``n`` i valori emergono dalla camminata-X dello stack, non si
    enumerano: niente tacche. La manopola resta, scrivibile a mano."""
    p = _params({"axes": {"grain.duration": {"base": 0.05, "baseline": 0.05}}})["grain.duration"]
    assert p["values"] == [] and p["kind"] == "num" and p["free"] is True


def test_un_asse_senza_generatore_resta_una_manopola_a_mano():
    """La forma degli stack: solo ``baseline`` e ``drift``, nessun marcatore.
    Prima l'asse non compariva affatto e il parametro sotto osservazione non
    era nemmeno scrivibile."""
    p = _params({"axes": {"density": {"baseline": 10, "drift": {"step": 0.12}}}})["density"]
    assert p["values"] == [] and p["kind"] == "num" and p["free"] is True


# --- le tacche sono i valori che il render sente ---------------------------
#
# Il confronto e' col parse (``resolve_streams``), non con numeri trascritti:
# la regola del seed e la compilazione dei nodi annidati sono del parse, e un
# test che le riscrivesse si confronterebbe con la propria copia.

_RIPOSO = {"base": {"sample": "a.wav", "duration": 6, "time_mode": "normalized"},
           "sweep": {"mode": "discrete"}}


def _resi(doc, study_id="s"):
    """I valori che il parse da' a ogni asse, per path: cio' che il render sente."""
    from granstudies.study_spec import resolve_streams

    out = {}
    for spec in resolve_streams(copy.deepcopy(doc), study_id):
        for ax in spec.axes:
            out.setdefault(ax.path, set()).update(ax.values)
    return out


def _tacche_di(doc, path, study_id="s"):
    return set(_params(doc, study_id)[path]["values"])


def test_una_banda_senza_seed_da_le_tacche_del_render():
    """Senza ``seed`` la banda non pesca col seed 0 del generatore: il parse
    deriva il seed dallo studio (``stable_seed("<id>:y")``), e le tacche
    devono essere quelle, non un pescaggio che nessun render fa."""
    doc = dict(copy.deepcopy(_RIPOSO),
               axes={"density": {"baseline": 20, "base": 10, "range": 5, "n": 3}})
    assert _tacche_di(doc, "density") == _resi(doc)["density"]


def test_axes_seed_e_il_seed_delle_bande_che_non_ne_hanno_uno():
    doc = dict(copy.deepcopy(_RIPOSO),
               axes={"seed": 42, "density": {"baseline": 20, "base": 10, "range": 5, "n": 3}})
    assert _tacche_di(doc, "density") == _resi(doc)["density"]


def test_la_banda_di_uno_stream_pesca_col_seed_dello_stream():
    """Due stream che ereditano la stessa banda senza seed pescano valori
    diversi (il seed viene dal loro id): le tacche sono l'unione di quelli."""
    doc = dict(copy.deepcopy(_RIPOSO),
               axes={"density": {"baseline": 20, "base": 10, "range": 5, "n": 3}},
               streams={"a": {}, "b": {"base": {"volume": -3}}})
    assert _resi(doc)["density"] <= _tacche_di(doc, "density")


@pytest.mark.parametrize("cfg", [
    {"ramp": {"start": 1, "stop": 20, "step": {"linear_env": [1, 5]}}},
    {"n": 3, "seed": 1, "base": {"linear_env": {"values": [10, 20]}}, "range": 2},
    {"n": 3, "seed": 1, "base": {"expr": "2*5"}, "range": 2},
])
def test_i_generatori_annidati_si_compilano_come_nel_parse(cfg):
    """Un ``linear_env:`` (o un ``expr`` senza ``let``) dentro lo ``step`` di
    una rampa o il ``base`` di una banda il parse lo compila in breakpoint
    (``expand_params``): sono valori enumerati come gli altri, non un asse
    illeggibile."""
    doc = dict(copy.deepcopy(_RIPOSO), axes={"density": dict(cfg, baseline=20)})
    assert _tacche_di(doc, "density") == _resi(doc)["density"]
    assert "free" not in _params(doc)["density"]


def test_graph_passa_l_id_dello_studio_come_il_parse():
    """Senza ``study_id`` nel documento il seed lo da' il nome dello studio,
    come in ``_load_specs``; con ``study_id`` vince quello."""
    doc = dict(copy.deepcopy(_RIPOSO),
               axes={"density": {"baseline": 20, "base": 10, "range": 5, "n": 3}})
    assert _tacche_di(doc, "density", "lab01") == _resi(doc, "lab01")["density"]
    doc["study_id"] = "altro"
    assert _tacche_di(doc, "density", "lab01") == _resi(doc, "altro")["density"]


@pytest.mark.parametrize("cfg", [
    {"ramp": {"step": 1}},                      # TypeError: manca start/stop
    {"ramp": "x"},                              # TypeError: ramp non e' un dict
    {"values": 5},                              # TypeError: values non e' una lista
    {"base": {"expr": "g0"}, "n": 3},           # ValueError: expr non espansa
    {"base": [[0]], "n": 2},                    # LookupError: Env senza il valore
    {"values": [1], "ramp": {"start": 0, "stop": 1, "step": 1}},   # due marcatori
    {"linear_env": {"values": [1, 2]}},         # wrapper di ruolo, non un asse piatto
    {"base": 1, "n": 2, "distribution": "boh"},  # distribuzione sconosciuta
    {"base": {"expr": "10**400"}, "n": 2},      # OverflowError: l'expr si valuta
    {"values": "hanning"},                      # una stringa, non una lista
])
def test_un_generatore_illeggibile_non_fa_esplodere_il_laboratorio(cfg):
    """La pagina si apre sempre: un generatore che non si risolve costa le sue
    tacche, non il laboratorio. Chi sbaglia lo dicono `sweep` e `render`."""
    p = _params({"axes": {"density": dict(cfg, baseline=1)}})["density"]
    assert p["values"] == [] and p["free"] is True


def test_interpolation_e_seed_non_sono_assi():
    """Sotto ``axes:`` sono vocabolario condiviso, non parametri: la regola e'
    quella del parse (``study_spec.axis_names``), non una lista riscritta qui."""
    doc = {"axes": {"interpolation": "step", "seed": 1988,
                    "density": {"values": [1, 2]}}}
    assert set(_params(doc)) == {"density"}


def test_la_manopola_sta_sul_path_dell_asse_non_sul_suo_nome():
    """``path`` e' l'alias del parse (``axes: {densita: {path: density}}``):
    la pagina scrive la manopola nel documento engine col suo path, e un
    ``densita:`` li' l'engine non lo conosce."""
    doc = {"axes": {"densita": {"path": "density", "baseline": 10, "values": [5, 10]}}}
    p = _params(doc)
    assert set(p) == {"density"}
    assert p["density"]["values"] == [5, 10]


def test_l_alias_vale_anche_dentro_gli_stream():
    doc = {"axes": {"densita": {"path": "density", "baseline": 10, "values": [5]}},
           "streams": {"a": {"axes": {"densita": {"values": [7]}}}}}
    assert _params(doc)["density"]["values"] == [5, 7]


# --- l'ordine delle tacche -------------------------------------------------

def test_le_tacche_numeriche_sono_ordinate_e_senza_doppioni():
    """Nello ``study.yml`` ``values:`` e' una *sequenza* da percorrere, e puo'
    tornare sui suoi passi; qui e' un menu, dove un valore sta una volta sola.
    Senza un ordine canonico l'unione fra documento e stream non ne avrebbe."""
    p = _params({"axes": {"distribution": {"values": [0, .25, 0, 1, 0, .75]}}})["distribution"]
    assert p["values"] == [0, .25, .75, 1]


def test_le_tacche_categoriali_tengono_l_ordine_dichiarato():
    """Un nome non si ordina: l'ordine utile e' quello in cui l'autore le ha
    scritte."""
    p = _params({"axes": {"grain.envelope": {"values": ["hanning", "expodec", "hanning"]}}})
    assert p["grain.envelope"]["values"] == ["hanning", "expodec"]
    assert p["grain.envelope"]["kind"] == "cat"


# --- gli assi dentro `streams:` --------------------------------------------

def test_gli_assi_degli_stream_si_uniscono_a_quelli_del_documento():
    """La forma delle zone d'ombra: lo stream ritocca la rampa del documento
    con una chiave puntata. Le tacche sono l'unione — il laboratorio compone
    UNO stream, e quale zona si stia ascoltando lo decide chi compone."""
    doc = {
        "axes": {"density": {"ramp": {"start": 1, "stop": 10, "step": 5}, "baseline": 20}},
        "streams": {"zona": {"axes.density.ramp.step": 3}},
    }
    assert _params(doc)["density"]["values"] == [1, 4, 6, 7, 10]


def test_uno_stream_che_cambia_generatore_rimpiazza_quello_ereditato():
    """Il deep-merge da solo lascerebbe ``values`` e ``ramp`` sullo stesso
    asse, cioe' due marcatori e nessuna tacca: vale la regola del parse
    (``_replace_generators``), non una seconda copia scritta qui."""
    doc = {
        "axes": {"density": {"values": [100]}},
        "streams": {"a": {"axes": {"density": {"ramp": {"start": 1, "stop": 3, "step": 1}}}}},
    }
    assert _params(doc)["density"]["values"] == [1, 2, 3, 100]


def test_un_asse_dichiarato_solo_da_uno_stream_c_e_lo_stesso():
    doc = {"streams": {"a": {"axes": {"distribution": {"values": [0, 1]}}}}}
    assert _params(doc)["distribution"]["values"] == [0, 1]


def test_le_tacche_di_uno_stream_bastano_a_togliere_la_manopola_dal_libero():
    """Senza tacche al documento ma con tacche in uno stream, il menu c'e'."""
    doc = {
        "axes": {"density": {"baseline": 1}},
        "streams": {"a": {"axes": {"density": {"values": [2, 3]}}}},
    }
    p = _params(doc)["density"]
    assert p["values"] == [2, 3] and "free" not in p


def test_uno_stream_illeggibile_non_porta_via_le_tacche_del_documento():
    """Un override che non si espande (chiave puntata ambigua, generatore
    rotto) costa il suo contributo, non la pagina."""
    doc = {
        "axes": {"density": {"values": [1, 2]}},
        "streams": {"a": {"axes": {"density": {"ramp": {"step": 1}}}},
                    "b": "non un dict"},
    }
    assert _params(doc)["density"]["values"] == [1, 2]


# --- `for_each: base.*` ----------------------------------------------------

def test_for_each_base_risolve_i_generatori_come_gli_assi():
    doc = {"for_each": {"base.distribution": {"ramp": {"start": 0, "stop": 1, "step": .5}}}}
    assert _params(doc)["distribution"]["values"] == [0, .5, 1]


def test_for_each_accetta_la_lista_nuda_come_for_each_stesso():
    """``base.distribution: [0, 1]`` e' la forma breve che ``for_each`` gia'
    accetta (``{"values": cfg}``): il laboratorio legge la stessa grammatica."""
    assert _params({"for_each": {"base.distribution": [0, 1]}})["distribution"]["values"] == [0, 1]


def test_for_each_fuori_da_base_non_entra():
    """``stack.seed`` o ``percorso.arco`` non sono parametri di uno stream."""
    doc = {"for_each": {"stack.seed": {"values": [1, 2]},
                        "percorso.arco": {"values": [1]}}}
    assert lab_data(doc)["params"] == []


def test_un_for_each_illeggibile_non_diventa_una_manopola():
    """A differenza di un asse, una chiave di ``for_each`` senza generatore
    leggibile non dichiara niente: ``for_each`` stesso la rifiuta."""
    assert lab_data({"for_each": {"base.distribution": {"ramp": {"step": 1}}}})["params"] == []


# --- lo stream a riposo ----------------------------------------------------

def test_il_base_e_quello_del_documento_non_quello_degli_stream():
    """Con piu' stream i fissi partono dal ``base:`` del documento: e' l'unico
    che tutti condividono. Il ``base:`` di una entry differenzia quella voce
    dalle sorelle, e fonderli darebbe uno stream che non ha scritto nessuno."""
    doc = {"base": {"sample": "a.wav", "pointer": {"start": 0.1}},
           "streams": {"a": {"base": {"pointer": {"start": 0.9}}}}}
    assert lab_data(doc)["base"] == {"sample": "a.wav", "pointer": {"start": 0.1}}


def test_lab_data_non_tocca_il_documento_che_legge():
    """``_replace_generators`` pota le chiavi della banda sul dict che trova:
    senza una copia poterebbe l'override dentro ``streams:``, e lo stream
    dopo (o un alias YAML) leggerebbe un documento gia' mangiato."""
    doc = {"streams": {"a": {"axes": {"density": {"values": [1, 2], "n": 3, "range": 5}}}}}
    prima = copy.deepcopy(doc)
    lab_data(doc)
    assert doc == prima


def test_senza_niente_da_leggere_resta_il_guscio():
    assert lab_data(None) == {"base": {}, "params": []}
    assert lab_data({})["params"] == []
