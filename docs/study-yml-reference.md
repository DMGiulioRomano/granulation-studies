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
                                 # tra {values, ramp, base} (vedi "Generatori" sotto).
                                 # values = lista esplicita (rimpiazza, non concatena).
    interpolation: step          # opzionale: override per-asse (default = quello di studio)

  grain_duration:
    path: grain.duration         # path annidato con notazione punto
    # baseline omesso → risolto dal default engine
    n: 40                        # banda piatta: base/range/n/seed accanto a path
    base: [[0, .001], [1, .05]]  # la banda [base, base+range] genera i valori
    range: .002
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
  nome_asse:                     # un asse con camminata-X: la X possiede n, la
    base:  [[0, 3], [1, 10]]     #   sua Y dev'essere una banda senza n. base/range
    range: [[0, 1], [1, 1]]      #   = frequenza di generazione (Hz, durata reale)
    seed: 7                      # seed-X per-asse (vince sul globale)
  # asse assente dal blocco -> linear (n dai valori Y). Dettagli: sezione "stack".

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
tra `values`, `ramp`, `base` (mutuamente esclusive: zero o più di una è errore).
Il generatore si riconosce dalla **forma**, non più da un wrapper con nome: la
presenza di `base` marca la banda. In una stream, il generatore dell'override
rimpiazza quello ereditato sullo stesso asse (non si sommano); passare a
`values`/`ramp` toglie anche le chiavi della banda ereditate.

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

### `base` — banda, seeded (piatta sull'asse)

`n` valori estratti uniformemente dentro una banda `[base, base + range]` che
può essere fissa o mobile lungo la sequenza. Le chiavi stanno **piatte** nel
dict dell'asse (accanto a `path`/`baseline`/`interpolation`), non più sotto un
wrapper. Deterministico: stesso `seed` → stessa sequenza (serve al ciclo
rigenera-e-confronta).

> **Tre `base` diversi.** La parola compare in tre punti che non c'entrano tra
> loro: la chiave di banda `base` qui descritta (pavimento della banda, marca il
> generatore); il blocco engine `base:` di uno stream (override di parametri a
> riposo, es. `base: {volume: 0}` per mutarlo); e l'eventuale stream *chiamato*
> `base` in `streams:` (solo un id). I livelli sono distinti nello YAML, ma
> leggendo un file conviene tenerli separati in testa.

```yaml
density:
  path: density
  n: 50                        # quanti valori (>= 1); OMESSO se la X è una camminata (vedi stack)
  base: .001                   # estremo inferiore della banda (vedi forme sotto)
  range: .009                  # ampiezza della banda; opzionale (default 0 = banda
                               # collassata: la sequenza segue `base` deterministicamente)
  seed: 1988                   # opzionale (default: `axes.seed`, poi auto per-stream)
```

`n` appartiene a chi possiede il conteggio dei punti (*n-ownership*): con la
camminata-X del processo stack i tempi — e quindi `n` — emergono dalla frequenza,
e la banda Y va dichiarata **senza** `n` (viene campionata ai tempi reali dei
breakpoint). Fuori da quel caso `n` è obbligatorio.

`base` e `range` sono un **envelope di 2° ordine** (una banda che genera
valori); un `range` negativo in un punto della sequenza è errore. Ognuno dei
due accetta queste forme:

| Forma | Significato |
|-------|-------------|
| scalare `.003` | banda a livello costante |
| `[a, b]` | rampa lineare `a → b` lungo la sequenza (esattamente due scalari) |
| `[[t, v], ...]` | breakpoint temporizzati, `t` in `[0, 1]`, interpolati **linear** (hold fuori dai bordi) |
| `{type, points, curve}` | breakpoint con `type` esplicito (`linear`/`step`) ed eventuale `curve` (vedi sotto) |

Esempio con banda mobile (si apre dopo il 60% della sequenza):

```yaml
density:
  n: 50
  base: [[0, 10], [.6, 2], [1, .1]]
  range: [[0, 10], [.6, 3], [1, 2.9]]
  seed: 1988
```

> Nel processo `stack` più assi generati con lo stesso `n` e la stessa strategy-X
> si muovono insieme (breakpoint agli stessi tempi): si sentono più modulazioni
> contemporaneamente, senza il prodotto cartesiano.

### `curve` — piega non lineare del segmento

`curve` vive nella **forma dict** di un `Env` (`base`/`range`) e piega la frazione
locale del segmento prima di interpolare (`u' = u^k`), cioè cambia *come* la banda
si muove tra i suoi breakpoint — non è l'`interpolation` dell'asse (che è come
l'engine unisce i breakpoint *già* generati).

```yaml
base: {points: [[0, 10], [1, 90]], curve: 2}   # sale lento, accelera in coda
```

- `curve: 1` = lineare (default); `> 1` parte lento e accelera; `< 1` parte ripido
  e si appiattisce. Deve essere `> 0`.
- Piega **ogni segmento** indipendentemente (la `u` locale di ciascun tratto).
- Con `type: step` non c'è rampa da piegare: `curve` diverso da 1 è un errore.
- Disponibile ovunque compaia un `Env` — `base`/`range` di X **e** di Y. Nota che
  il `[0, 1]` su cui l'`Env` è letto misura cose diverse: in Y è la posizione del
  punto sull'asse dello stream, in X è il tempo reale normalizzato della
  camminata. La piega è la stessa, il dominio no.
- **`curve` e override di stream.** La forma dict di un `Env` segue la regola
  generale del merge («i dict si fondono»): uno stream che sovrascrive
  `base: {points: [...]}` su una base che aveva `base: {points: [...], curve: 2}`
  **eredita** `curve: 2` — ridefinire i punti non azzera la piega. Per tornare
  alla rampa lineare dichiararlo esplicitamente (`curve: 1`); per rimpiazzare
  l'envelope in blocco usare una forma lista (`[a, b]` o `[[t, v], ...]`), che
  come tutte le liste rimpiazza invece di fondersi.

## Il blocco `stack:`

Il processo stack è il gemello verticale dello sweep: **collassa** tutti gli
stream di `streams:` in un solo documento engine (`yaml/stack/stack.yml`),
sommati. Parte solo se il blocco `stack:` è presente (anche vuoto: `stack: {}`);
richiede `duration:` top-level (la durata condivisa su cui normalizza i tempi).
Per escludere uno stream dall'ascolto lo si muta con il suo `base.volume`
(meccanismo engine); il blocco `stack:` è solo config della camminata-X, non un
gate di partecipazione.

Schema piatto: `seed` è l'unica chiave riservata (seed-X globale); ogni altra
chiave è un **nome d'asse**. Non c'è più un nome-strategy: la strategy-X si
riconosce dalla **presenza** dell'asse nel blocco.

| Strategy-X | Come si dichiara | Chi possiede `n` |
|------------|------------------|-------------------|
| `linear` | asse **assente** dal blocco | la **Y** (`values`/`ramp`/banda con `n`); tempi equispaziati `t_i = i/(n-1)`, estremo `t=1` incluso |
| camminata (`walk`, alla `rspline`) | asse **presente** con `{base: <env>, range?: <env>, seed?: int}` | la **X**: `n` emerge dalla frequenza integrata sulla durata |

Con la camminata la frequenza si pesca a ogni punto nella banda
`[base(t), base(t)+range(t)]` (Hz sulla durata reale; `base`/`range` accettano
le stesse forme della banda di Y) e il punto successivo cade a `t + 1/f`. La Y
dev'essere una **banda senza** `n`, campionata ai tempi reali dei breakpoint.
`range` assente = camminata **deterministica** (segue `base`, il seed non
influisce sui tempi). Le due direzioni sbagliate (camminata-X con Y che enumera; banda Y
senza `n` con X lineare) sono errori di parse (*n-ownership*).

> **Due equispaziati diversi.** «`base` costante = tempi equispaziati» vale per la
> **camminata** ed è un equispaziato *per frequenza*: `n` emerge da `durata × f` e
> l'ultimo punto non cade mai su `t = 1`. È cosa diversa dall'equispaziato della
> **X-linear** (assenza dal blocco): lì `n` viene dalla Y, `t_i = i/(n-1)` ed
> `t = 1` è incluso. Convivono — uno è la camminata, l'altro il default implicito.

Per riportare un asse a `linear` in una stream (annullando una camminata
ereditata) si **annulla l'entry**: `stack: {asse: null}`.

In stack gli assi **non si combinano** (niente prodotto cartesiano): ogni asse
diventa un envelope indipendente. Due assi con la stessa strategy-X e lo stesso
`n` restano accoppiati — è l'ex `combine: parallel` dello sweep. Un asse con un
solo valore resta **scalare** (stream statici/drone legittimi); l'interpolation
per-asse (`linear`/`cubic`/`step`) vale anche qui.

**Seed, precedenza (il più specifico vince):**

- Y: `seed` della banda (per-asse) → `axes.seed` globale → auto-derivato per-stream;
- X: `stack.<asse>.seed` → `stack.seed` globale → auto-derivato per-stream.

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
