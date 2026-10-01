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


def _params(doc):
    return {p["path"]: p for p in lab_data(doc)["params"]}


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


@pytest.mark.parametrize("cfg", [
    {"ramp": {"step": 1}},                      # TypeError: manca start/stop
    {"ramp": "x"},                              # TypeError: ramp non e' un dict
    {"values": 5},                              # TypeError: values non e' una lista
    {"base": {"expr": "g0"}, "n": 3},           # ValueError: expr non espansa
    {"base": [[0]], "n": 2},                    # LookupError: Env senza il valore
    {"values": [1], "ramp": {"start": 0, "stop": 1, "step": 1}},   # due marcatori
    {"linear_env": {"values": [1, 2]}},         # wrapper di ruolo, non un asse piatto
    {"base": 1, "n": 2, "distribution": "boh"},  # distribuzione sconosciuta
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
