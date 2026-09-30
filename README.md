# granulation-studies

Ciclo di studi compositivi sui parametri dell'elaborazione granulare.

Framework di **ricerca compositiva** sopra
[PythonGranularEngine](https://github.com/DMGiulioRomano/PythonGranularEngine)
(incluso come git submodule in `engine/`). Permette di esplorare metodicamente
lo spazio dei parametri del motore granulare, curare i risultati interessanti,
organizzarli in *stati* con una loro dinamica, e comporre brani come percorsi tra
quegli stati — il tutto producendo YAML che l'engine compila in audio.

## Pipeline

```
study.yml ──sweep────▶ yaml/sweep/*.yml ───────────┬─render──▶ audio + partitura
          ──stack────▶ yaml/stack/stack.yml ───────┤       │
          ──versions─▶ yaml/versions/versions__*.yml┤       │
          ──percorso─▶ yaml/percorso/percorso.yml ─┘       │
                              (ascolto + tag manuali)
                                          ▼
                                     results.yml ──┐
                                                   ▼
                                     states.yml ──matrix──▶ kinship.json
                                          │
                  composition.yml ──compose──▶ final.yml ──render──▶ brano
```

Vedi `docs/methodology.md` per il modello concettuale completo e i formati file.

## Avvio rapido

```bash
make setup                              # venv + submodule + dipendenze
# metti un file audio in samples/ (es. corpus.wav, vedi samples/README.md)
make sweep   STUDY=1-10ms
make stack   STUDY=1-10ms
make render  STUDY=1-10ms
make describe STUDY=1-10ms
# cura generated/base/results.yml (kept/tags), poi compila states.yml
make matrix  STUDY=1-10ms
make compose STUDY=1-10ms
make render-final STUDY=1-10ms
```

## `for_each:` — n valori del parametro, n file

Gli `axes:` di uno studio scorrono **dentro** il file: ogni valore è un plateau
dello sweep, e ogni asse in più moltiplica la durata. Un terzo asse
triplicherebbe il file, e il confronto fra `distribution: 0` e
`distribution: 1` finirebbe a minuti di distanza dentro lo stesso ascolto.

`for_each:` è l'asse **esterno**: non allunga il file, ne fa uno per valore.

```yaml
for_each:
  base.distribution: {values: [0, 0.5, 1]}   # 3 render dello stesso sweep
```

```bash
study 1-10ms                                # genera e apre tutte le combinazioni
COMBO=distribution=1 study 1-10ms           # solo la fetta a distribution 1
make where STUDY=1-10ms                     # dove si sta scrivendo, una riga per combinazione
```

Ogni combinazione ha il suo albero completo sotto
`generated/<studio>/distribution=0.5/`, con dentro anche lo snapshot dello
`study.yml` patchato che l'ha prodotta e i suoi `.sv` (la label è nel basename:
Sonic Visualiser identifica la sessione dal nome, e con due `.sv` omonimi la
seconda non si apre — proprio il confronto per cui gli assi esterni esistono).
Senza `for_each:` l'albero resta quello piatto di sempre,
`generated/<studio>/`.

`COMBO` taglia una **fetta**: i vincoli sono segmenti di label separati da
`__`, in and fra loro (`COMBO=griglia=rada__distribution=0.5`), e il match è
per segmento intero (`distribution=0` non prende `distribution=0.5`). Con più
assi esterni le combinazioni sono decine e generarle tutte non ha senso: il
documento dichiara lo spazio, `COMBO` sceglie cosa materializzare oggi.

Le chiavi sono path su tutto il documento, non solo su `base:` — quindi
funziona anche dove un asse interno non potrebbe esistere: `stack.seed` (cinque
realizzazioni della stessa camminata stocastica), `percorso.arco` (la stessa
legge distesa su tre durate), `axes.*.values` (due griglie diverse dello stesso
studio, anche su un asse dotted come `grain.duration`). Per gli override non
scalari serve un nome:

```yaml
for_each:
  griglia:
    fitta: {axes.grain.duration.values: [0.001, 0.002, 0.005, 0.01]}
    rada:  {axes.grain.duration.values: [0.001, 0.01]}
```

Dettagli, guardie e forme in `docs/study-yml-reference.md`. Togliere un valore
dal blocco non cancella la sua cartella: resta lì con l'audio già ascoltato,
segnalata come orfana dal render.

> Dopo un aggiornamento del repo, la funzione `study` già caricata in una shell
> aperta resta quella vecchia: il precmd di `setup.sh` ricarica
> `.zsh_completions/` solo al cambio di repo. Per prendere la nuova senza
> riaprire il terminale: `source .zsh_completions/_study`.

## Il laboratorio del singolo stream (`make serve`)

Lo sweep fa sentire gli assi in fila; il laboratorio fa l'inverso: si compone
**uno** stream a breakpoint, lo si rende al volo e lo si ascolta e guarda.

```bash
make serve STUDY=10-50ms            # scrive la pagina, la serve e la apre in Safari
make serve STUDY=10-50ms PORT=8001  # su un'altra porta
```

`make serve` scrive `generated/<studio>/graph.html` (`make graph`, una pagina
per studio anche con `for_each:`) e avvia `granstudies serve` su
`http://localhost:8000`, solo su `127.0.0.1`. Un server rimasto orfano da una
sessione precedente si chiude da solo; una porta tenuta da un altro programma
non si tocca, e il messaggio dice chi la tiene.

- **Parametri.** Le tacche fra cui si sceglie sono i `values:` dello
  `study.yml` (in `axes:` e in `for_each: base.*`); i sample sono i file della
  cartella dei sample; volume, pan e `pan_range` si scrivono a mano. Gli assi a
  `ramp:`/banda e quelli dentro `streams:` non danno ancora tacche (#77).
- **Breakpoint.** `+ breakpoint` fotografa tutti i parametri a un tempo;
  interpolazione `linear`/`cubic`/`step` per tutti, per breakpoint o per
  parametro; `genera breakpoint` ne mette n in un tratto (regolari, casuali o
  sulle tacche dello `study.yml`); undo/redo, selezione a banda, lucchetto della
  durata.
- **Anche:** le voci (`voices:`), `grain.envelope` automatizzato come
  `{states, curve}`, start e loop del pointer (il loop si disegna sulla forma
  d'onda del sample).
- **File.** Il progetto è lo YAML stesso, un documento engine puro: `nuovo`,
  `apri…`, `apri recente…`, `salva`, `salva con nome…` con i pannelli nativi di
  macOS, dove si vuole sul disco; l'audio (`.aif`) nasce accanto, con lo stesso
  nome. Senza un file scelto, tutto va in `generated/<studio>/live/`.

Dopo il render, a destra:

| vista | cosa mostra |
|---|---|
| sonogramma | x tempo, y frequenza: STFT propria, scala lin/log, finestra 256…8192 |
| forma d'onda | picchi min/max per colonna |
| spectroscope | x frequenza (log), y dinamica, in tempo reale |
| stereoscope | goniometro L/R |
| inviluppi | le curve che lo stream ha **davvero** percorso (dall'engine, derivate e offset per-voce compresi) |
| grani | x tempo, y posizione di lettura nel sample, colore = pitch, opacità = volume; accanto la forma d'onda del sample |

**Barra spaziatrice**: play/pausa (fuori dai campi di testo). Si cerca nel
file cliccando su sonogramma, forma d'onda, inviluppi o grani.

Vincoli: **solo macOS** (`osascript` per i pannelli, Safari che decodifica
AIFF). Il documento del laboratorio non porta un `seed`: le curve di una
strategia stocastica sono un'altra realizzazione rispetto a quella che ha
suonato. La descrizione completa, pezzo per pezzo, è in `CLAUDE.md`.

## Struttura

- `src/granstudies/` — il pacchetto (uno stadio per modulo).
- `studies/<id>/` — input versionati: `study.yml`, `states.yml`, `composition.yml`.
- `generated/<id>/` — output rigenerabile (git-ignorato).
- `samples/` — corpus audio (file git-ignorati, solo manifest versionato).
- `engine/` — submodule del motore (pin su commit).
- `tests/` — suite pytest (mirror di `src/`); `tests/e2e/` — end-to-end.

## Test

```bash
make tests        # suite veloce: gate obbligatorio prima di ogni commit
make e2e-tests    # end-to-end: study.yml -> CLI -> YAML -> audio
```

Le due suite sono separate. `make tests` gira su unit e golden e non tocca
disco fuori da `tmp_path`. `make e2e-tests` (marker `e2e`, cartella
`tests/e2e/`) parte da uno `study.yml` **su disco** in un repo temporaneo,
passa dalla CLI vera — `sweep`, `stack`, `versions`, `percorso`, `render` — e
dove il submodule `engine/` è inizializzato arriva al file audio, che verifica
non vuoto e non silenzioso. Senza il submodule i test che renderizzano si
skippano da soli, quelli sulla generazione restano.
