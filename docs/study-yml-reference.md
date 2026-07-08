# Riferimento: `study.yml`

Sintassi completa con tutti i campi. I campi marcati `*` sono obbligatori.

```yaml
study_id: study01_grain_density   # * identificatore, usato come nome cartella
title: "Studio 01 — ..."          # libero, finisce nell'header dei file generati
seed: 1988                        # seed globale engine (finisce nei documenti generati)
duration: 30                      # durata condivisa (s): obbligatoria se c'è `stack:`
samples_dir: samples              # path relativo alla root del repo (default: samples/)

# Parametri fissi dello stream: tutto ciò che non è un asse.
base:                             # *
  onset: 0
  duration: 6                    # usato solo dalle varianti discrete
  sample: corpus.wav             # *
  time_mode: normalized
  volume: -6
  grain:
    envelope: hanning
  pointer:
    speed_ratio: 0
    start: 0.3

# Assi (parametri sotto osservazione). axes conosce solo Y: quali parametri si
# muovono, con che valori e con che curva. Il timing (plateau/transition) è del
# processo sweep e vive sotto `sweep:`.
axes:                             # * almeno un asse
  interpolation: linear          # linear | cubic | step (default studio, default linear)
                                 # step: nessuna rampa, ogni valore è tenuto e salta
                                 # netto al successivo. È il DEFAULT ereditato dagli assi
                                 # che non specificano un proprio `interpolation`.
                                 # Ogni asse può fare override (vedi sotto): nello stesso
                                 # file assi diversi possono avere forme diverse.
                                 # Collasso durata (plateau ignorato, stream = N*transition,
                                 # un solo punto per valore) SOLO se TUTTI gli assi mossi
                                 # del file sono step; in caso misto la durata resta piena
                                 # (N*plateau + (N-1)*transition) e l'asse step tiene-e-salta
                                 # sui confini di plateau, sincronizzato con gli altri.

  density:                       # nome dell'asse (libero)
    path: density                # * path YAML nell'engine
    baseline: 20                 # valore a riposo; obbligatorio se l'engine non ha default
    values: [5, 10, 20, 50]      # * i valori di test. UNA sola chiave-generatore per asse
                                 # tra {values, ramp, rand} (vedi "Generatori" sotto).
                                 # values = lista esplicita (rimpiazza, non concatena).
    interpolation: step          # opzionale: override per-asse (default = quello di studio)

  grain_duration:
    path: grain.duration         # path annidato con notazione punto
    # baseline omesso → risolto dal default engine
    values: [0.001, 0.01, 0.05]
    interpolation: cubic         # es. density a scalini + grain morbido nello stesso file

# Configurazione dello sweep (il processo possiede X: timing e durata derivata).
sweep:
  mode: envelope                 # discrete | envelope | both (default discrete)
  plateau: 5                     # secondi di ascolto stabile per valore (default 5.0)
  transition: 5                  # secondi di transizione tra plateau (default 5.0)
                                 # Lo sweep fa SOLO il prodotto cartesiano (N^k plateau).
                                 # Per muovere assi INSIEME (accoppiati) si usa il
                                 # processo `stack:` (stessa strategy-X, stesso n).
  orders: [1, 2, 3]             # ordini da generare: 1=OAT, 2=coppie, 3=terzine…
  orderings:                     # permutazioni esplicite (funziona per e2, e3, qualsiasi ordine)
    - [density, grain_duration]                # primo = asse lento (outer), ultimo = veloce (inner)
    - [grain_duration, density]                # stessa coppia, ordine invertito

# Processo stack (attivo per presenza del blocco): tutti gli stream sommati in
# UN documento multi-stream. Vedi la sezione "Il blocco stack" sotto.
stack:
  seed: 42                       # seed-X globale (chiave riservata; opzionale)
  density:                       # nome d'asse -> config della strategy-X
    rand:                        # X-rand (rspline): i tempi emergono dalla frequenza
      cps:
        base:  [[0, 3], [1, 10]] # frequenza di generazione (Hz sulla durata reale)
        range: [[0, 1], [1, 1]]  # banda = [base(t), base(t)+range(t)]
      seed: 7                    # seed-X per-asse (vince sul globale)
  # grain_duration assente -> strategy-X di default `linear` (n dai valori Y)

# Stream: varianti di ascolto con override parziali sul documento sopra.
# Regole del merge: i dict si fondono ricorsivamente, le liste rimpiazzano.
# Se questa sezione è assente, sweep genera un'unica versione senza sotto-cartella.
streams:
  base: {}                       # nessun override — identica alla base

  nome_stream:                   # chiave libera → diventa la sotto-cartella dell'output
    base:                        # override parziale di base (deep-merge)
      volume: -3
      pointer:
        start: 0.7               # sovrascrive solo start; gli altri campi restano
    axes:                        # override parziale di axes
      density:
        values: [100, 200, 300]  # rimpiazza l'intera lista
    sweep:                       # override parziale di sweep
      orders: [1, 2]             # es. salta le terzine
      plateau: 10                # cambia il plateau per questa stream
    stack:                       # override parziale di stack (deep-merge)
      seed: 43                   # es. riseeda solo i tempi di questa stream
```

## Generatori di valori d'asse

I valori di test di un asse si danno con **esattamente una** chiave-generatore
tra `values`, `ramp`, `rand` (mutuamente esclusive: zero o più di una è errore).
In una stream, la chiave-generatore dell'override rimpiazza quella ereditata
sullo stesso asse (non si sommano).

### `values` — lista esplicita

```yaml
values: [5, 10, 20, 50]        # i valori così come sono
```

### `ramp` — rampa aritmetica

```yaml
ramp: {start: 5, stop: 100, step: 5}   # 5, 10, 15, ..., 100
```

- `step` deve essere `> 0`. La direzione si deduce da `start`/`stop`
  (discendente se `start > stop`).
- Uno `stop` che cade sulla griglia è incluso; uno che non ci cade non viene
  mai oltrepassato (conteggio intero anti-drift float).

### `rand` — banda casuale, seeded

`n` valori estratti uniformemente dentro una banda `[base, base + range]` che
può essere fissa o mobile lungo la sequenza — stessa semantica della `cps` di
X-rand. Deterministico: stesso `seed` → stessa sequenza (serve al ciclo
rigenera-e-confronta).

```yaml
rand:
  n: 50                        # quanti valori (>= 1); OMESSO se la X è `rand` (vedi stack)
  base: .001                   # estremo inferiore della banda (vedi forme sotto)
  range: .009                  # ampiezza della banda; opzionale (default 0 = banda
                               # collassata: la sequenza segue `base` deterministicamente)
  seed: 1988                   # opzionale (default: `axes.seed`, poi auto per-stream)
```

`n` appartiene a chi possiede il conteggio dei punti (*n-ownership*): con la
strategy-X `rand` del processo stack i tempi — e quindi `n` — emergono dalla
frequenza, e la Y `rand` va dichiarata **senza** `n` (viene campionata ai tempi
reali dei breakpoint). Fuori da quel caso `n` è obbligatorio.

`base` e `range` sono un **envelope di 2° ordine** (una banda che genera
valori); un `range` negativo in un punto della sequenza è errore. Ognuno dei
due accetta queste forme:

| Forma | Significato |
|-------|-------------|
| scalare `.003` | banda a livello costante |
| `[a, b]` | rampa lineare `a → b` lungo la sequenza |
| `[[t, v], ...]` | breakpoint temporizzati, `t` in `[0, 1]`, interpolati **linear** (hold fuori dai bordi) |
| `{type, points}` | breakpoint con `type` esplicito: `linear` (rampa) o `step` (tieni-e-salta) |

Esempio con banda mobile (si apre dopo il 60% della sequenza):

```yaml
rand:
  n: 50
  base: [[0, 10], [.6, 2], [1, .1]]
  range: [[0, 10], [.6, 3], [1, 2.9]]
  seed: 1988
```

> Nel processo `stack` più assi generati con lo stesso `n` e la stessa
> strategy-X si muovono insieme (breakpoint agli stessi tempi): si sentono più
> modulazioni contemporaneamente, senza il prodotto cartesiano.

## Il blocco `stack:`

Il processo stack è il gemello verticale dello sweep: **collassa** tutti gli
stream di `streams:` in un solo documento engine (`yaml/stack/stack.yml`),
sommati. Parte solo se il blocco `stack:` è presente (anche vuoto: `stack: {}`);
richiede `duration:` top-level (la durata condivisa su cui normalizza i tempi).
Per escludere uno stream dall'ascolto lo si muta con il suo `base.volume`
(meccanismo engine); il blocco `stack:` è solo config della strategy-X, non un
gate di partecipazione.

Schema piatto: `seed` è l'unica chiave riservata (seed-X globale); ogni altra
chiave è un **nome d'asse** → config della strategy-X.

| Strategy-X | Config | Chi possiede `n` |
|------------|--------|-------------------|
| `linear` (default, asse assente dal blocco) | `{}` — nessun parametro | la **Y** (`values`/`ramp`/`rand` con `n`); tempi equispaziati `t_i = i/(n-1)` |
| `rand` (alla `rspline`) | `{cps: {base: <env>, range: <env>}, seed?: int}` | la **X**: `n` emerge dalla frequenza integrata sulla durata |

Con la X-rand la frequenza si pesca a ogni punto nella banda
`[base(t), base(t)+range(t)]` (Hz sulla durata reale; `base`/`range` accettano
le stesse forme della banda di Y-rand) e il punto successivo cade a `t + 1/f`.
La Y dev'essere `rand` **senza** `n`, campionata ai tempi reali dei breakpoint.
Le due direzioni sbagliate (X-rand con Y che enumera; Y-rand senza `n` con X
lineare) sono errori di parse (*n-ownership*).

In stack gli assi **non si combinano** (niente prodotto cartesiano): ogni asse
diventa un envelope indipendente. Due assi con la stessa strategy-X e lo stesso
`n` restano accoppiati — è l'ex `combine: parallel` dello sweep. Un asse con un
solo valore resta **scalare** (stream statici/drone legittimi); l'interpolation
per-asse (`linear`/`cubic`/`step`) vale anche qui.

**Seed, precedenza (il più specifico vince):**

- Y: `rand.seed` per-asse → `axes.seed` globale → auto-derivato per-stream;
- X: `stack.<asse>.rand.seed` → `stack.seed` globale → auto-derivato per-stream.

L'auto-derivazione è un hash stabile (CRC32) dell'id dello stream, con salt
distinti per Y e X: senza seed globali gli stream impilati si **decorrelano da
soli**, restando riproducibili tra run.

## Layout di `generated/`

Primo livello = tipo di artefatto, secondo livello = **processo** (`sweep` /
`stack`). Il nome della stream è incorporato nel basename dei file sweep (non
solo nella sotto-cartella) per facilitare l'identificazione in Sonic
Visualiser; il documento stack è uno solo (gli stream vi sono collassati).

```
generated/<study_id>/
  yaml/sweep/envelope/<stream_id>/e1__density.yml
  yaml/stack/stack.yml
  audio/sweep/envelope/<stream_id>/<stream_id>_e1__density.aif
  audio/stack/stack.aif
  sv/sweep/envelope/<stream_id>/<stream_id>_e1__density.sv
```

`generated/` è rigenerabile: dopo un aggiornamento basta rilanciare
`make sweep` / `make stack`.

## Comandi Make

```bash
make sweep  STUDY=<id>                    # genera tutte le stream
make sweep  STUDY=<id> STREAM=nome        # genera solo quella stream
make stack  STUDY=<id>                    # genera il documento multi-stream (stack)
make render STUDY=<id>                    # renderizza gli YAML cambiati (incrementale, in parallelo)
make render STUDY=<id> FORCE=1            # rirenderizza tutto (es. dopo update engine o sample)
make render STUDY=<id> JOBS=4             # limita i worker paralleli (default: min(8, cpu))
make sv     STUDY=<id>                    # genera .sv per tutte le stream
make sv     STUDY=<id> STREAM=nome        # genera .sv per una stream
```

### Flag del comando `sv`

| Flag | Valori | Default | Descrizione |
|------|--------|---------|-------------|
| `--layout` | `multi`, `single` | `multi` | `multi`: un pannello per asse; `single`: tutti in un pannello |
| `--markers-scope` | `waveform`, `all` | `waveform` | Dove appaiono i marker di plateau: solo nel pane waveform o in ogni pane |
| `--no-markers` | — | — | Disabilita completamente i marker di plateau |
| `--stream` | nome stream | tutte | Genera `.sv` solo per la stream indicata |

Il pane waveform di ogni sessione `.sv` include automaticamente uno strato
spectrogram (finestra 8192, overlap 75%, White on Black, scala logaritmica)
sovrapposto alla forma d'onda.
