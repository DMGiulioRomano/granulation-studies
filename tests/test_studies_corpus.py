"""Canarino sul corpus reale: gli study curati a mano restano non ambigui.

Il resto della suite non legge ``studies/`` di proposito — quei file sono
dell'utente e cambiano liberamente, un test che ne asserisse il *contenuto*
diventerebbe rosso a ogni sessione di ascolto (per questo
``test_study01_file.py`` usa una fixture). Qui l'asserzione e' di natura
diversa: non «lo study dice X» ma «nessuno study cade in questa trappola».
Un invariante non si rompe quando l'utente lavora, si rompe quando la
trappola torna — che e' esattamente il segnale voluto.

La trappola e' PGE #222: ``pointer.loop_unit`` non eredita piu' da
``time_mode``, quindi una posizione nel sample scritta sotto
``time_mode: normalized`` senza unita' significa secondi dove prima
significava frazione. Nessun errore, suono diverso — la categoria di guasto
che nessun test coglie da solo.
"""
import glob
import os

import pytest
import yaml

from granstudies.diagnostics import check_loop_unit
from granstudies.yaml_loc import load as load_with_locations

_STUDIES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studies"
)
_CORPUS = sorted(glob.glob(os.path.join(_STUDIES, "*", "study.yml")))


def test_il_corpus_non_e_vuoto():
    """Se il glob smette di trovare gli study, il canarino tace per sbaglio."""
    assert len(_CORPUS) >= 10


@pytest.mark.parametrize("path", _CORPUS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_nessuna_posizione_senza_loop_unit(path):
    data, locs = load_with_locations(path)
    items = check_loop_unit(data, locs)
    assert items == [], "\n\n".join(d.format_block() for d in items)


@pytest.mark.parametrize("path", _CORPUS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_ogni_loop_unit_e_del_vocabolario_dell_engine(path):
    """``LOOP_UNITS`` del PointerController: fuori di li' l'engine alza."""
    from granstudies.bounds import LOOP_UNITS

    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "loop_unit":
                    assert v in LOOP_UNITS, f"{path}: loop_unit '{v}'"
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(yaml.safe_load(text))


# --- il laboratorio sul corpus vero (#77) ----------------------------------
#
# Stessa natura delle asserzioni qui sopra: non «lo studio dice X» ma «il
# laboratorio non cade in questa trappola su nessuno studio». Le tacche sono
# numeri dell'utente e cambiano a ogni sessione d'ascolto; che la pagina si
# apra, e che ci sia una manopola per ogni asse dichiarato, non cambia.


@pytest.mark.parametrize("path", _CORPUS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_il_laboratorio_si_apre_su_ogni_studio(path):
    """``lab_data`` e' totale: un generatore che non si risolve costa le sue
    tacche, mai la pagina. Un'eccezione qui sarebbe un `make serve` che non
    parte su uno studio che renderizza benissimo."""
    from granstudies.graph import lab_data

    with open(path, "r", encoding="utf-8") as fh:
        lab = lab_data(yaml.safe_load(fh))

    paths = [p["path"] for p in lab["params"]]
    assert len(paths) == len(set(paths)), f"{path}: manopola doppia in {paths}"
    for p in lab["params"]:
        # La pagina fa `Number(...)` su un `num`: un nome fra quei valori
        # scriverebbe NaN nel documento.
        if p["kind"] == "num":
            assert all(isinstance(v, (int, float)) for v in p["values"]), f"{path}: {p}"
        # Senza tacche il campo si scrive a mano, e il menu `▾` non compare.
        assert bool(p["values"]) != bool(p.get("free")), f"{path}: {p}"


@pytest.mark.parametrize("path", _CORPUS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_ogni_asse_dichiarato_e_una_manopola_del_laboratorio(path):
    """Il parametro che lo studio sta studiando sta sul banco, con o senza
    tacche, e sul suo path engine (``path:`` e' un alias del nome). Gli assi
    li contano ``study_spec.axis_names`` e ``axis_path`` — le regole del
    parse, lette dal documento e non da ``lab_data``, altrimenti il test si
    confronterebbe con se stesso."""
    from granstudies.graph import lab_data
    from granstudies.study_spec import axis_names, axis_path

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    manopole = {p["path"] for p in lab_data(data)["params"]}
    dichiarati = {axis_path(n, data["axes"][n]) for n in axis_names(data)}
    assert dichiarati <= manopole, f"{path}: assi senza manopola"
