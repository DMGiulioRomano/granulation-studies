"""e2e di ``for_each:``: due combinazioni, due render veri, due suoni diversi.

Gli unit di ``tests/test_for_each.py`` sostituiscono l'engine con un finto che
ricopia lo YAML nel file audio: dicono che le combinazioni finiscono in
cartelle separate con documenti diversi, non che l'engine accetti il
documento patchato. Qui lo studio passa dalla CLI vera fino all'audio, e il
path della patch attraversa un nome d'asse dotted (``grain.duration``), la
forma che nel repo e' la regola e che mare-nostrum non esercitava.

Guardato dalla presenza del submodule ``engine``, come ``test_render_e2e``.
"""
import copy
import os

import numpy as np
import pytest
import soundfile as sf
import yaml

from granstudies import engine_bridge


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.path.isdir(engine_bridge.ENGINE_SRC),
        reason="submodule engine non inizializzato",
    ),
]

_LABELS = ("griglia=corta", "griglia=lunga")


@pytest.fixture
def for_each_repo(sweep_repo):
    """Lo studio sweep ridotto a un asse, moltiplicato da due griglie esterne."""
    with open(sweep_repo.fixture("e2e_study.yml"), "r", encoding="utf-8") as fh:
        data = copy.deepcopy(yaml.safe_load(fh))
    data["sweep"] = {"mode": "envelope", "orders": [1], "plateau": 0.2, "transition": 0.1}
    data["base"]["duration"] = 0.5
    data["axes"] = {"grain.duration": {"baseline": 0.05, "values": [0.01, 0.05]}}
    data["for_each"] = {"griglia": {
        "corta": {"axes.grain.duration.values": [0.01, 0.05]},
        "lunga": {"axes.grain.duration.values": [0.01, 0.02, 0.05, 0.1]},
    }}
    sweep_repo.write_study(data)
    return sweep_repo


def _audio(repo, label: str) -> str:
    audio_dir = os.path.join(repo.generated, label, "audio")
    found = [
        os.path.join(root, f)
        for root, _, files in os.walk(audio_dir)
        for f in files
        if f.endswith(".aif")
    ]
    assert len(found) == 1, sorted(found)
    return found[0]


def test_ogni_combinazione_e_un_render_vero_e_distinto(for_each_repo):
    repo = for_each_repo
    repo.run("sweep", repo.study)
    repo.run("render", repo.study, "--no-score", "--no-stem", "--no-cache")

    assert sorted(os.listdir(repo.generated)) == list(_LABELS)
    suoni = {}
    for label in _LABELS:
        path = _audio(repo, label)
        data, _ = sf.read(path)
        assert data.size > 0 and float(np.max(np.abs(data))) > 0.0, path
        suoni[label] = data
        # lo snapshot della combinazione dice la griglia che l'ha prodotta
        with open(os.path.join(repo.generated, label, "study.yml")) as fh:
            snap = yaml.safe_load(fh)
        assert "for_each" not in snap
        assert snap["axes"]["grain.duration"]["values"] == (
            [0.01, 0.05] if label.endswith("corta") else [0.01, 0.02, 0.05, 0.1])
    corta, lunga = (suoni[label] for label in _LABELS)
    assert corta.shape != lunga.shape or not np.array_equal(corta, lunga)


def test_sv_di_due_combinazioni_si_aprono_insieme(for_each_repo):
    # Il giro di `study`: all-study, poi sv. Due .sv con lo stesso nome non si
    # aprono insieme in Sonic Visualiser: la label nel basename li separa.
    repo = for_each_repo
    repo.run("sweep", repo.study)
    repo.run("render", repo.study, "--no-score", "--no-stem", "--no-cache")
    repo.run("sv", repo.study)

    nomi = []
    for label in _LABELS:
        sv_dir = os.path.join(repo.generated, label, "sv")
        for root, _, files in os.walk(sv_dir):
            nomi += [f for f in files if f.endswith(".sv")]
    assert len(nomi) == 2, nomi
    assert len(set(nomi)) == 2, nomi
    assert all(any(label in n for label in _LABELS) for n in nomi), nomi
