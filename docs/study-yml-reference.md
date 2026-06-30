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
  interpolation: linear          # linear | cubic (default linear)

  density:                       # nome dell'asse (libero)
    path: density                # * path YAML nell'engine
    baseline: 20                 # valore a riposo; obbligatorio se l'engine non ha default
    values: [5, 10, 20, 50]      # * lista valori di test (rimpiazza, non concatena)

  grain_duration:
    path: grain.duration         # path annidato con notazione punto
    # baseline omesso → risolto dal default engine
    values: [0.001, 0.01, 0.05]

# Configurazione dello sweep.
sweep:
  mode: envelope                 # discrete | envelope | both (default discrete)
  orders: [1, 2, 3]             # ordini da generare: 1=OAT, 2=coppie, 3=terzine…
  orderings:                     # permutazioni esplicite per l'ordine 3 (opzionale)
    - [density, grain_duration, distribution]   # primo = asse lento, ultimo = veloce

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

## Output con `streams:`

```
generated/<study_id>/
  variants/envelope/<stream_id>/e1__density.yml
  audio/envelope/<stream_id>/e1__density.aif
  sv/envelope/<stream_id>/e1__density.sv
```

## Comandi Make

```bash
make sweep  STUDY=<id>                    # genera tutte le stream
make sweep  STUDY=<id> STREAM=nome        # genera solo quella stream
make render STUDY=<id>                    # renderizza tutto (ricorsivo, tutte le stream)
make sv     STUDY=<id>                    # genera .sv per tutte le stream
make sv     STUDY=<id> STREAM=nome        # genera .sv per una stream
```
