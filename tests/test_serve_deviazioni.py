"""Le deviazioni di ``serve.py`` da mare-nostrum, emerse in review (#94).

Stanno qui e non in ``test_serve.py`` perche' quello resta identico al suo
originale: le modifiche successive di mare-nostrum si riportano con un diff.
"""
import http.client
import json
import os
import subprocess
import threading

import pytest

from granstudies import serve as S


DOC = {"duration": 4, "streams": [{"stream_id": "lab"}]}


@pytest.fixture
def server(tmp_path):
    """Un ``granstudies serve`` vero su una porta libera, sullo studio ``gen``."""
    gen = tmp_path / "gen"
    gen.mkdir()
    srv = S.crea(str(gen), str(tmp_path), 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def _req(srv, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read()


JSON = {"Content-Type": "application/json"}


# --- il pannello: il nome e' testo, non AppleScript ------------------------

def _letterali(script):
    """``(stringhe, resto)``: i letterali AppleScript dello script e il codice
    fuori da essi. ``\\`` dentro un letterale protegge il carattere dopo."""
    stringhe, resto, i = [], [], 0
    while i < len(script):
        if script[i] != '"':
            resto.append(script[i])
            i += 1
            continue
        i += 1
        s = []
        while script[i] != '"':
            if script[i] == "\\":
                i += 1
            s.append(script[i])
            i += 1
        stringhe.append("".join(s))
        i += 1
    return stringhe, "".join(resto)


def test_il_nome_nel_pannello_non_esce_dalla_stringa(monkeypatch, tmp_path):
    """Il nome del file arriva dalla pagina ed entrava nello script com'era:
    una virgoletta chiudeva la stringa, e il resto era AppleScript eseguito —
    ``do shell script`` compreso. Ora resta il nome, virgolette comprese."""
    script = []
    monkeypatch.setattr(S.subprocess, "run", lambda cmd, **k: script.append(cmd[-1])
                        or subprocess.CompletedProcess(cmd, 1, "", "(-128)"))
    nome = 'a" & (do shell script "touch /tmp/x") & "\\b.yml'
    cartella = tmp_path / 'con "virgolette"'
    cartella.mkdir()
    S.pannello("save", nome, str(cartella))
    stringhe, codice = _letterali(script[0])
    assert nome in stringhe and str(cartella) in stringhe
    assert "shell" not in codice


# --- il pannello: il path che torna e' quello che si scrivera' ------------

def test_salva_con_nome_senza_estensione_resta_autorizzato(monkeypatch, tmp_path):
    """`choose file name` non impone l'estensione: scelto `brano`, il server
    scriveva `brano.yml` ma autorizzava `brano`. La pagina tiene il path che
    le torna dal render, e il salvataggio dopo veniva rifiutato."""
    scelto = str(tmp_path / "brano")
    monkeypatch.setattr(S.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, scelto + "\n", ""))
    path, err = S.pannello("save", "stream.yml")
    assert (path, err) == (scelto + ".yml", "")
    out = S.render_doc(DOC, "x", str(tmp_path / "gen"), str(tmp_path),
                       render=False, path=path)
    assert out["ok"] and out["path"] == scelto + ".yml"
    # Il secondo salvataggio, sul path che la pagina ha tenuto.
    assert S.render_doc(DOC, "x", str(tmp_path / "gen"), str(tmp_path),
                        render=False, path=out["path"])["ok"]
    assert S._RECENTI[0] == scelto + ".yml"


# --- l'audio di uno stream salvato fuori dallo studio ----------------------

def test_l_audio_reso_fuori_dallo_studio_si_puo_ascoltare(server, monkeypatch, tmp_path):
    """Il file si salva dove si vuole, e l'audio nasce accanto: fuori dallo
    studio `src` e' un path assoluto, che la pagina chiede cosi' com'e'. Il
    server lo cercava sotto lo studio: 404, e niente da ascoltare."""
    fuori = tmp_path / "altrove dal disco" / "stream.yml"
    fuori.parent.mkdir()
    S._AUTORIZZATI.add(str(fuori))

    def engine(cmd, **k):
        with open(cmd[3], "wb") as fh:          # main.py <yaml> <out> ...
            fh.write(b"FORM")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(S.subprocess, "run", engine)
    monkeypatch.setattr(S, "_analisi", lambda *a: {"inviluppi": [], "grani": None})
    out = S.render_doc(DOC, "x", server.RequestHandlerClass.keywords["directory"],
                       str(tmp_path), path=str(fuori))
    assert out["ok"] and os.path.isabs(out["src"])
    # Come lo chiede la pagina: `audio.src = src + "?t=..."`, spazi codificati.
    url = out["src"].replace(" ", "%20") + "?t=1"
    assert _req(server, "GET", url) == (200, b"FORM")
    # Solo quello: un altro file del disco resta fuori.
    (tmp_path / "altrove dal disco" / "altro.aif").write_bytes(b"NO")
    url = str(tmp_path / "altrove dal disco" / "altro.aif").replace(" ", "%20")
    assert _req(server, "GET", url)[0] == 404


# --- le rotte POST rispondono solo alla pagina -----------------------------

def test_un_post_da_un_altra_pagina_non_apre_il_pannello(server, monkeypatch):
    """Un sito qualunque aperto nel browser puo' mandare un POST `text/plain`
    a localhost senza preflight: arrivava fino a `osascript`. La pagina manda
    `application/json`, che da un'altra origine richiede un preflight che
    questo server non concede."""
    chiamato = []
    monkeypatch.setattr(S, "pannello", lambda *a, **k: chiamato.append(a) or ("", ""))
    body = json.dumps({"mode": "open"})
    assert _req(server, "POST", "/pick", body, {"Content-Type": "text/plain"})[0] == 415
    assert _req(server, "POST", "/pick", body)[0] == 415
    assert not chiamato
    assert _req(server, "POST", "/pick", body, JSON)[0] == 200    # la pagina
    assert len(chiamato) == 1


def test_un_nome_che_non_e_localhost_non_passa(server):
    """DNS rebinding: un dominio estraneo che risolve su 127.0.0.1 e' la stessa
    origine per il browser, ma non e' localhost per l'header Host."""
    h = dict(JSON, Host="attaccante.example:8000")
    assert _req(server, "POST", "/stato", "{}", h)[0] == 403
    assert _req(server, "GET", "/.recenti.json", None, {"Host": "attaccante.example"})[0] == 403
    for host in ("localhost:8000", "127.0.0.1:8000"):
        assert _req(server, "POST", "/stato", "{}", dict(JSON, Host=host))[0] == 200


def test_un_corpo_che_non_e_un_oggetto_e_un_400(server):
    """Una lista JSON faceva saltare `.get` dentro il thread: niente risposta."""
    assert _req(server, "POST", "/render", "[1]", JSON)[0] == 400
    assert _req(server, "POST", "/render", "{}", dict(JSON, **{"Content-Length": "x"}))[0] == 400
