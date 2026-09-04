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
