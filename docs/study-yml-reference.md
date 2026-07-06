# Riferimento: `study.yml`

Sintassi completa con tutti i campi. I campi marcati `*` sono obbligatori.

```yaml
study_id: study01_grain_density   # * identificatore, usato come nome cartella
title: "Studio 01 — ..."          # libero, finisce nell'header dei file generati
seed: 1988                        # seed globale (sweep + render riproducibili)
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

# Assi (parametri sotto osservazione) + timing envelope.
axes:                             # * almeno un asse
  plateau: 5                     # secondi di ascolto stabile per valore (default 5.0)
  transition: 5                  # secondi di transizione tra plateau (default 5.0)
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

# Configurazione dello sweep.
sweep:
  mode: envelope                 # discrete | envelope | both (default discrete)
  combine: cartesian             # cartesian | parallel (default cartesian)
                                 # cartesian: prodotto — un asse fermo mentre l'altro
                                 #   scorre, N^k plateau.
                                 # parallel: zip — gli assi si muovono INSIEME (plateau i
                                 #   = i-esimo valore di ogni asse), N plateau. Richiede
                                 #   assi di ugual lunghezza (utile con rand a stesso n:
                                 #   si sentono più modulazioni contemporaneamente).
  orders: [1, 2, 3]             # ordini da generare: 1=OAT, 2=coppie, 3=terzine…
  orderings:                     # permutazioni esplicite (funziona per e2, e3, qualsiasi ordine)
    - [density, grain_duration]                # primo = asse lento (outer), ultimo = veloce (inner)
    - [grain_duration, density]                # stessa coppia, ordine invertito

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
      plateau: 10                # cambia il plateau per questa stream
    sweep:                       # override parziale di sweep
      orders: [1, 2]             # es. salta le terzine
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

`n` valori estratti uniformemente dentro una banda `[min, max]` che può essere
fissa o mobile lungo la sequenza. Deterministico: stesso `seed` → stessa
sequenza (serve al ciclo rigenera-e-confronta).

```yaml
rand:
  n: 50                        # quanti valori (>= 1)
  min: .001                    # estremo inferiore della banda (vedi forme sotto)
  max: .01                     # estremo superiore
  seed: 1988                   # opzionale, default 0
```

`min` e `max` sono un **envelope di 2° ordine** (una banda che genera valori);
ognuno dei due accetta queste forme:

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
  min: [[0, 10], [.6, 2], [1, .1]]
  max: [[0, 20], [.6, 5], [1, 3]]
  seed: 1988
```

> Con `sweep.combine: parallel` (vedi sopra) più assi generati con lo stesso `n`
> si muovono insieme: si sentono più modulazioni contemporaneamente, senza il
> prodotto cartesiano.

## Output con `streams:`

Il nome della stream è incorporato nel basename dei file generati (non solo
nella sotto-cartella) per facilitare l'identificazione in Sonic Visualiser.

```
generated/<study_id>/
  variants/envelope/<stream_id>/e1__density.yml
  audio/envelope/<stream_id>/<stream_id>_e1__density.aif
  sv/envelope/<stream_id>/<stream_id>_e1__density.sv
```

## Comandi Make

```bash
make sweep  STUDY=<id>                    # genera tutte le stream
make sweep  STUDY=<id> STREAM=nome        # genera solo quella stream
make render STUDY=<id>                    # renderizza le varianti cambiate (incrementale, in parallelo)
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
