"""``prune``: l'audio e gli YAML rimasti da una versione precedente dello studio.

Succede quando si **cambia** il valore di un asse invece di aggiungerne uno:
lo sweep scrive la variante nuova e lascia la vecchia, e finche' il vecchio
YAML resta il render lo rifa'. Il confronto e' con cio' che lo ``study.yml``
genera **oggi** (``render.variant_paths``), non con il disco, e il nome
dell'audio viene dall'unica regola del render (``render.audio_for``).
"""
import os
import shutil
import subprocess

import pytest
import yaml

from granstudies import __main__ as cli
from granstudies import for_each
from granstudies import render as render_mod
from granstudies.render import audio_for, variant_paths


DOC = {
    "study_id": "s_prune",
    "samples_dir": "samples",
    "base": {"onset": 0, "duration": 5, "sample": "corpus.wav"},
    "axes": {"a": {"path": "density", "baseline": 20, "values": [5, 50]}},
    "sweep": {"mode": "discrete", "orders": [1]},
}


def _studio(tmp_path, monkeypatch, doc=None):
    monkeypatch.setattr(cli, "REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("COMBO", raising=False)
    doc = doc or DOC
    sdir = tmp_path / "studies" / doc["study_id"]
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "study.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    return doc["study_id"]


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").close()


def _prune_tree(tmp_path, monkeypatch):
    """Le varianti attese con il loro mix e uno stem, piu' una variante di una
    versione precedente (YAML, mix e stem) e i file che prune non deve vedere."""
    study = _studio(tmp_path, monkeypatch)
    g = cli.gen_dir(study)
    yaml_root = os.path.join(g, "yaml", "sweep")
    attesi = variant_paths(cli._load_spec(study), yaml_root)
    assert len(attesi) == 2

    def mix_di(p):
        return audio_for(p, os.path.join(g, "yaml"), os.path.join(g, "audio"), study)[1]

    audio = []
    for p in attesi:
        _touch(p)
        audio.append(mix_di(p))
        _touch(audio[-1])
    stem = os.path.splitext(audio[0])[0] + "__stream.aif"
    _touch(stem)

    # la variante di prima: il valore 50 era 70
    vecchia = attesi[1].replace("=50", "=70")
    assert vecchia != attesi[1]
    orfani = [vecchia, mix_di(vecchia), os.path.splitext(mix_di(vecchia))[0] + "__stream.aif"]
    for p in orfani:
        _touch(p)

    # fuori dal conto: gli altri processi, il marcatore di provenienza, lo yaml
    # di ispezione degli spread, un file che non e' audio
    fuori = [
        os.path.join(g, "yaml", "stack", "stack.yml"),
        os.path.join(g, "audio", "stack", "stack.aif"),
        os.path.join(yaml_root, ".sorgente"),
        os.path.join(g, "yaml", "streams_expanded.yml"),
        os.path.join(os.path.dirname(audio[0]), "appunti.txt"),
    ]
    for p in fuori:
        _touch(p)
    return study, attesi + audio, stem, orfani, fuori


def test_prune_tiene_gli_stem_e_toglie_solo_gli_orfani(tmp_path, monkeypatch):
    study, buoni, stem, orfani, fuori = _prune_tree(tmp_path, monkeypatch)
    assert cli.cmd_prune(study, apply=True) == 0
    assert not any(os.path.exists(p) for p in orfani)   # YAML, mix e il suo stem
    assert os.path.exists(stem)                          # segue il suo mix, che resta
    assert all(os.path.exists(p) for p in buoni + fuori)


def test_prune_stems_toglie_gli_stem_ma_non_i_mix(tmp_path, monkeypatch):
    """--stems prende di mira proprio cio' che il prune normale protegge."""
    study, buoni, stem, orfani, fuori = _prune_tree(tmp_path, monkeypatch)
    assert cli.cmd_prune(study, apply=True, stems=True) == 0
    assert not os.path.exists(stem)
    assert not any(os.path.exists(p) for p in orfani)
    assert all(os.path.exists(p) for p in buoni + fuori)


def test_prune_senza_apply_elenca_e_non_cancella(tmp_path, monkeypatch, capsys):
    study, buoni, stem, orfani, fuori = _prune_tree(tmp_path, monkeypatch)
    assert cli.cmd_prune(study) == 0
    assert cli.cmd_prune(study, stems=True) == 0
    assert all(os.path.exists(p) for p in buoni + [stem] + orfani + fuori)
    out = capsys.readouterr().out
    g = cli.gen_dir(study)
    for p in orfani:
        assert os.path.relpath(p, g) in out
    assert "APPLY=1" in out


def test_prune_riconosce_il_file_non_il_nome(tmp_path, monkeypatch):
    """Sul filesystem di default di macOS ``a=Uno.yml`` e ``a=uno.yml`` sono un
    file solo: dopo aver cambiato un valore solo nelle maiuscole, sul disco
    resta il nome vecchio della variante che il giro ha appena confermato.
    Confrontati per nome, prune la cancellerebbe. Qui il caso e' riprodotto con
    un hard link: due nomi, un file."""
    study, buoni, stem, orfani, fuori = _prune_tree(tmp_path, monkeypatch)
    alias = []
    for p in buoni:
        d, f = os.path.split(p)
        a = os.path.join(d, f.replace("=", "=X"))
        os.link(p, a)
        alias.append(a)
    # lo stem il cui mix ha, sul disco, solo il nome vecchio
    mix = buoni[len(buoni) // 2]
    alias_mix = alias[len(alias) // 2]
    os.remove(stem)
    stem_alias = os.path.splitext(alias_mix)[0] + "__stream.aif"
    _touch(stem_alias)
    assert os.path.samefile(mix, alias_mix)

    assert cli.cmd_prune(study, apply=True) == 0
    assert all(os.path.exists(p) for p in buoni + alias + [stem_alias])
    assert not any(os.path.exists(p) for p in orfani)


def test_prune_senza_blocco_sweep_tutto_lo_sweep_e_residuo(tmp_path, monkeypatch):
    """Oggi lo studio non genera nessuno sweep: quello su disco viene tutto da
    prima, e il render (che discende tutto ``yaml/``) continuerebbe a rifarlo."""
    study, buoni, stem, orfani, fuori = _prune_tree(tmp_path, monkeypatch)
    senza = {k: v for k, v in DOC.items() if k != "sweep"}
    senza["stack"] = {}
    _studio(tmp_path, monkeypatch, senza)
    assert cli.cmd_prune(study, apply=True) == 0
    assert not any(os.path.exists(p) for p in buoni + [stem] + orfani)
    assert all(os.path.exists(p) for p in fuori)


def test_prune_toglie_le_cartelle_che_svuota(tmp_path, monkeypatch, capsys):
    """Una stream tolta dallo studio ha una cartella sotto ``yaml/`` e una sotto
    ``audio/``: tolti i file, restava lo scheletro di cio' che lo studio non
    genera piu'. Se ne vanno solo le cartelle che prune ha svuotato: una gia'
    vuota prima non e' sua, e le cartelle vive hanno ancora i loro file."""
    study, buoni, stem, orfani, fuori = _prune_tree(tmp_path, monkeypatch)
    g = cli.gen_dir(study)
    tolta_y = os.path.join(g, "yaml", "sweep", "discrete", "tolta", "o1__a=5.yml")
    tolta_a = os.path.join(g, "audio", "sweep", "discrete", "tolta",
                           f"{study}_tolta_o1__a=5.aif")
    for p in (tolta_y, tolta_a, os.path.splitext(tolta_a)[0] + "__tolta.aif"):
        _touch(p)
    gia_vuota = os.path.join(g, "audio", "sweep", "discrete", "gia_vuota")
    os.makedirs(gia_vuota)

    assert cli.cmd_prune(study) == 0          # senza APPLY non si tocca niente
    assert os.path.isdir(os.path.dirname(tolta_y))

    assert cli.cmd_prune(study, apply=True) == 0
    assert not os.path.exists(os.path.dirname(tolta_y))
    assert not os.path.exists(os.path.dirname(tolta_a))
    assert os.path.isdir(gia_vuota)
    assert all(os.path.exists(p) for p in buoni + [stem] + fuori)
    # il riepilogo dice che le ha tolte, non che sono rimaste li' vuote
    assert "tolte 2 cartelle" in capsys.readouterr().out


def test_prune_senza_niente_su_disco_non_fa_niente(tmp_path, monkeypatch):
    study = _studio(tmp_path, monkeypatch)
    assert cli.cmd_prune(study, apply=True) == 0
    assert not os.path.exists(cli.gen_dir(study))


# --- il giro vero: sweep, render, cambio di un valore, prune ----------------

def _fake_engine(monkeypatch):
    def fake(yaml_path, output_path, samples_dir, output_sr=48000,
             per_stream=False, use_cache=False, cache_dir=None, jobs=1):
        out = (os.path.splitext(output_path)[0] + "__stream.aif") if per_stream else output_path
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w") as fh:
            fh.write(open(yaml_path).read())
        return [out]

    monkeypatch.setattr(render_mod.engine_bridge, "render", fake)


FE_DOC = dict(DOC, study_id="s_fe", for_each={"base.volume": {"values": [0, 6]}})


def _files(root):
    return sorted(os.path.relpath(os.path.join(r, f), root)
                  for r, _d, fs in os.walk(root) for f in fs)


def _giro_e_cambio(tmp_path, monkeypatch):
    study = _studio(tmp_path, monkeypatch, FE_DOC)
    _fake_engine(monkeypatch)
    assert cli.main(["sweep", study]) == 0
    assert cli.main(["render", study, "--no-score", "--jobs", "1"]) == 0
    root = tmp_path / "generated" / study
    prima = {c: _files(root / c) for c in ("volume=0", "volume=6")}
    assert all(any("a=50" in f for f in fs) for fs in prima.values())

    # si cambia un valore invece di aggiungerne uno, e si rigenera
    cambiato = dict(FE_DOC, axes={"a": {"path": "density", "baseline": 20, "values": [5, 60]}})
    _studio(tmp_path, monkeypatch, cambiato)
    assert cli.main(["sweep", study]) == 0
    assert cli.main(["render", study, "--no-score", "--jobs", "1"]) == 0
    return study, root


def test_prune_gira_su_ogni_combinazione(tmp_path, monkeypatch):
    study, root = _giro_e_cambio(tmp_path, monkeypatch)
    assert cli.main(["prune", study, "--apply"]) == 0
    for c in ("volume=0", "volume=6"):
        fs = _files(root / c)
        assert not any("a=50" in f for f in fs), c
        # la variante nuova resta: YAML, mix e stem
        assert len([f for f in fs if "a=60" in f]) == 3, fs


def test_prune_rispetta_il_filtro_combo(tmp_path, monkeypatch):
    study, root = _giro_e_cambio(tmp_path, monkeypatch)
    monkeypatch.setenv("COMBO", "volume=6")
    assert cli.main(["prune", study, "--apply"]) == 0
    assert not any("a=50" in f for f in _files(root / "volume=6"))
    assert any("a=50" in f for f in _files(root / "volume=0"))


def test_prune_nomina_le_combinazioni_orfane_senza_toccarle(tmp_path, monkeypatch, capsys):
    """Una combinazione che ``for_each:`` non dichiara piu' e' un residuo anche
    lei, ma intero: prune non ci entra (e' spesso il «prima» da riascoltare,
    come dice l'avviso del render) e la nomina, perche' chi lancia prune per
    fare pulizia la vuole vedere."""
    study, root = _giro_e_cambio(tmp_path, monkeypatch)
    vecchia = root / "volume=12"
    shutil.copytree(root / "volume=6", vecchia)
    prima = _files(vecchia)
    capsys.readouterr()
    assert cli.main(["prune", study, "--apply"]) == 0
    assert _files(vecchia) == prima
    assert str(vecchia) in capsys.readouterr().err


# --- make: APPLY e STEMS si accendono solo quando lo dicono -----------------

@pytest.mark.skipif(shutil.which("make") is None, reason="make non disponibile")
@pytest.mark.parametrize("variabili, attesi", [
    ([], []),
    (["APPLY=1"], ["--apply"]),
    (["APPLY=true"], ["--apply"]),
    (["APPLY=0"], []),        # un valore che dice "no" non cancella
    (["APPLY=false"], []),
    (["APPLY="], []),
    (["STEMS=1", "APPLY=1"], ["--apply", "--stems"]),
    (["STEMS=0"], []),
])
def test_make_prune_passa_i_flag_solo_se_accesi(variabili, attesi):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {k: v for k, v in os.environ.items()
           if k not in ("APPLY", "STEMS", "MAKEFLAGS", "MFLAGS")}
    out = subprocess.run(
        ["make", "-n", "-C", root, "prune", "STUDY=uno"] + variabili,
        capture_output=True, text=True, env=env, check=True,
    ).stdout.replace("\\\n", " ")     # la ricetta va a capo con '\'
    riga = next(r for r in out.splitlines() if "granstudies prune" in r)
    argv = riga.split("granstudies prune", 1)[1].split()
    assert argv[0] == "uno"
    assert sorted(argv[1:]) == sorted(attesi)
