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
  unit: s                        # unita' globale della banda (chiave riservata;
                                 #   hz = frequenza, default | s = periodo in secondi)
  nome_asse:                     # un asse con camminata-X: la X possiede n, la
    base:  [[0, 20], [1, 4]]     #   sua Y dev'essere una banda senza n. base/range
    range: [[0, 5], [1, 1]]      #   nell'unita' scelta (qui: secondi tra breakpoint)
    seed: 7                      # seed-X per-asse (vince sul globale)
    unit: s                      # unit per-asse (vince sul globale; opzionale)
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

  ventaglio:                     # entry-spread: genera n stream con una regola
    spread:                      # (chiave riservata; vedi la sezione "spread")
      n: 8
      over:
        base.pointer.start:
          ramp: {start: 0.1, step: 0.1}
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
- `step` è un **`Env`** (le stesse forme di `base`/`range`, generatori annidati
  compresi): con un `step` mobile la rampa accelera o ritarda. È letto sul
  **progresso in valore** `|v − start| / |stop − start|`, non sull'indice: il
  numero di gradini emerge dall'integrazione. Un `step` che tocca `0` è errore;
  tetto anti-runaway sui punti generati. Il caso scalare resta identico.

```yaml
ramp: {start: 5, stop: 100, step: [10, 1]}   # accelerando: i passi si stringono
ramp: {start: 5, stop: 100, step: [1, 10]}   # ritardando: i passi si allargano
```

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
> `base` in `streams:` (solo un id). Con i generatori annidati se ne aggiunge
> un quarto: il `base` **dentro** un bordo di banda (`base: {n: 6, base: 2, ...}`,
> il pavimento del pavimento — vedi «Generatori annidati» sotto). I livelli sono
> distinti nello YAML, ma leggendo un file conviene tenerli separati in testa.

```yaml
density:
  path: density
  n: 50                        # quanti valori (>= 1); OMESSO se la X è una camminata (vedi stack)
  base: .001                   # estremo inferiore della banda (vedi forme sotto)
  range: .009                  # ampiezza della banda; opzionale (default 0 = banda
                               # collassata: la sequenza segue `base` deterministicamente)
  seed: 1988                   # opzionale (default: `axes.seed`, poi auto per-stream)
  distribution: gaussian       # opzionale: come si pesca (uniform, il default | gaussian)
  drift: {step: 0.1}           # opzionale: pescaggio correlato (random walk, vedi sotto)
```

`n` appartiene a chi possiede il conteggio dei punti (*n-ownership*): con la
camminata-X del processo stack i tempi — e quindi `n` — emergono dalla frequenza
(o dal periodo, con `unit: s`), e la banda Y va dichiarata **senza** `n` (viene
campionata ai tempi reali dei breakpoint). Fuori da quel caso `n` è obbligatorio.

`base` e `range` sono un **envelope di 2° ordine** (una banda che genera
valori); un `range` negativo in un punto della sequenza è errore. Ognuno dei
due accetta queste forme:

| Forma | Significato |
|-------|-------------|
| scalare `.003` | banda a livello costante |
| `[a, b]` | rampa lineare `a → b` lungo la sequenza (esattamente due scalari) |
| `[[t, v], ...]` | breakpoint temporizzati, `t` in `[0, 1]`, interpolati **linear** (hold fuori dai bordi) |
| `{type, points, curve}` | breakpoint con `type` esplicito (`linear`/`step`) ed eventuale `curve` (vedi sotto) |
| nodo generatore (`{values}` \| `{ramp}` \| `{n, base, range, seed}`, più `type`/`curve` opzionali) | breakpoint **generati** invece che scritti a mano (vedi «Generatori annidati») |

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

### `distribution` — come si pesca dentro la banda

Sibling di `base`/`range` (sia nella banda di Y sia nella camminata-X del
blocco `stack:`): governa **come** si estrae dentro `[base, base+range]`,
indipendentemente dal fatto che il pescaggio sia correlato (`drift`) o no.

- `uniform` (default) — il comportamento storico, ogni punto della banda è
  equiprobabile. Bit-identico ai file generati finora.
- `gaussian` — media al **centro banda**, deviazione standard pari a un sesto
  della larghezza (i bordi cadono a 3 sigma); il ~0.3% di estrazioni fuori
  banda si appiattisce sul bordo (clamp). I valori si addensano sul centro
  invece di riempire la banda uniformemente.

Con banda collassata (`range` 0) non c'è varianza: entrambe seguono `base`.

### `drift` — pescaggio correlato (random walk)

Marcatore sibling di `base`/`range`, valido negli stessi due registri di
`distribution`. Quando presente, il valore non è più un pescaggio indipendente
a ogni punto ma `precedente + passo_casuale` — il «passo dell'ubriaco»: niente
su-e-giù a scatti dentro la banda, ma una deriva organica.

```yaml
drift:
  step: 0.1        # frazione della banda per passo; è un Env: [[0,.02],[.5,.2]]
  seed: 7          # opzionale: deriva dal seed della banda se assente
```

Meccanica:

- **valore iniziale**: il pescaggio di sempre (`uniform`/`gaussian` secondo
  `distribution`), poi da lì in poi cammina;
- **passo**: `step(frac) * larghezza_banda(frac)` — `step` è **frazione della
  banda corrente**, si adatta da solo se la banda si allarga o si restringe.
  `step` è un `Env` (stesse forme di `base`/`range`, **nodi-generatore
  annidati compresi**), consultato a ogni passo sul dominio del registro:
  posizione sull'asse per la banda-Y, tempo reale normalizzato per la
  camminata-X. Negativo in un punto → errore; `0` congela il valore;
- **distribuzione del passo**: la stessa `distribution` della banda —
  `uniform` → passo uniforme in `[-s, +s]`, `gaussian` → passo gaussiano con
  sigma `s`;
- **bordo banda**: **riflessione** — il valore rimbalza su `[base, base+range]`
  invece di appiattirsi;
- **banda mobile**: se la banda trasla e il valore corrente resta fuori,
  clamp immediato dentro i nuovi limiti, poi si riparte a camminare;
- **seed**: l'RNG del passo è separato da quello della banda; senza `seed`
  proprio deriva dalla catena gerarchica (`stable_seed` del seed effettivo
  della banda con salt `:drift`, come per i nodi annidati): cambiare il seed
  della banda rigenera anche la deriva, fissare `drift.seed` congela solo la
  forma della camminata.

Design completo: `docs/plans/done/drift-distribution.md` (issue #16).

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

### Generatori annidati — un bordo di banda generato

I `points` di un bordo (`base`/`range` di banda Y, `base`/`range` della
camminata-X, `step` di `ramp`) si possono **generare** invece di scriverli a
mano: al posto della forma statica si mette un **nodo**, un dict nella stessa
grammatica piatta dell'asse — `values`, `ramp`, oppure la banda
(`n`/`base`/`range`/`seed`), più le opzionali `type` (`linear`/`step`) e
`curve`. Il nodo si compila in breakpoint su tempi equispaziati (X implicita
lineare) e da lì in poi si comporta esattamente come dei `points` scritti a
mano. Ricorsivo: i `base`/`range` del nodo accettano a loro volta nodi
(guardia di profondità: 8).

```yaml
density:
  path: density
  n: 40
  base:                      # il pavimento vaga: 6 quote pescate tra 2 e 8
    n: 6
    base: 2
    range: 6
  range:                     # la larghezza salta a plateau tra 4 e 14
    type: step
    n: 6
    base: 4
    range: 10
```

E nella camminata-X (frequenza di generazione essa stessa stocastica):

```yaml
stack:
  density:
    base: {n: 8, base: 2, range: 4}     # la base salta tra 2 e 6 Hz
    range: 0.5
```

Regole:

- **`n` obbligatorio** nella banda annidata (dentro un `Env` non c'è coupling
  X/Y: il nodo deve produrre da solo la sua lista). `ramp` e `values` lo
  posseggono per costruzione.
- **Seed gerarchico.** Un nodo-banda senza `seed` deriva un seed stabile dal
  seed effettivo del generatore padre e dal percorso (`base`, `range`,
  `base.range`, ...): `base` e `range` si decorrelano da soli, cambiare il seed
  esterno rigenera l'intero sottoalbero coerentemente, un `seed` esplicito nel
  nodo congela solo quel sottoalbero.
- **Bordi correlati gratis**: banda che trasla a larghezza costante = `base`
  annidato + `range` scalare (nessun seed da coordinare).
- **`type`/`curve` nel nodo** valgono come nella forma `{type, points, curve}`:
  `type: step` fa saltare il bordo tra le quote generate (plateau di banda),
  `curve` piega i segmenti. Solo `linear`/`step` (niente `cubic` nelle bande).
- Il nodo è un dict: negli override di stream **si fonde** come ogni dict
  (ridefinire `base` interno non azzera `type`/`curve` ereditati); per
  rimpiazzare in blocco usare una forma lista.
- Niente arriva all'engine: l'espansione è tutta in granstudies, nello YAML
  engine finisce il solito envelope dell'asse.

Design completo: `docs/plans/done/nested-generators.md`.

## Il blocco `stack:`

Il processo stack è il gemello verticale dello sweep: **collassa** tutti gli
stream di `streams:` in un solo documento engine (`yaml/stack/stack.yml`),
sommati. Parte solo se il blocco `stack:` è presente (anche vuoto: `stack: {}`);
richiede `duration:` top-level (la durata condivisa su cui normalizza i tempi).
Per escludere uno stream dall'ascolto lo si muta con il suo `base.volume`
(meccanismo engine); il blocco `stack:` è solo config della camminata-X, non un
gate di partecipazione.

Schema piatto: `seed` (seed-X globale) e `unit` (unità globale della banda)
sono le chiavi riservate; ogni altra chiave è un **nome d'asse**. Non c'è più
un nome-strategy: la strategy-X si riconosce dalla **presenza** dell'asse nel
blocco.

| Strategy-X | Come si dichiara | Chi possiede `n` |
|------------|------------------|-------------------|
| `linear` | asse **assente** dal blocco | la **Y** (`values`/`ramp`/banda con `n`); tempi equispaziati `t_i = i/(n-1)`, estremo `t=1` incluso |
| camminata (`walk`, alla `rspline`) | asse **presente** con `{base: <env>, range?: <env>, seed?: int, unit?: hz\|s, distribution?, drift?}` | la **X**: `n` emerge dalla banda integrata sulla durata |

Con la camminata a ogni punto si pesca un valore nella banda
`[base(t), base(t)+range(t)]` (`base`/`range` accettano le stesse forme della
banda di Y). Con `unit: hz` (default) il valore è una **frequenza di
generazione** e il punto successivo cade a `t + 1/f`; con `unit: s` è il
**periodo** in secondi e il punto cade a `t + p` — comodo quando gli intervalli
sono nell'ordine delle decine di secondi e le frequenze frazionarie (0.0x Hz)
diventano scomode. Anche `distribution` e `drift` valgono qui, con la stessa
semantica della banda di Y (il dominio degli `Env` è il tempo reale
normalizzato): con `drift` la frequenza (o il periodo) di generazione deriva
invece di saltare — accelerandi/ritardandi stocastici ma organici. La Y
dev'essere una **banda senza** `n`, campionata ai tempi reali dei breakpoint.
`range` assente = camminata **deterministica** (segue `base`, il seed non
influisce sui tempi). Le due direzioni sbagliate (camminata-X con Y che
enumera; banda Y senza `n` con X lineare) sono errori di parse (*n-ownership*).

> **`unit` sceglie lo spazio della camminata, non una notazione.** Uniforme in
> periodo non è uniforme in frequenza: la banda `[10, 30]` s ha intervallo
> medio 20 s, la "equivalente" `[1/30, 1/10]` Hz produce intervalli sbilanciati
> verso il corto. E gli `Env` di `base`/`range` si interpolano nello spazio
> scelto: `base: [20, 2]` con `unit: s` è un accelerando lineare *nel periodo*,
> `base: [0.05, 0.5]` in Hz è lineare *nel rate* — curve percettive diverse.
> Anche `drift.step` (frazione della banda corrente) cammina nello spazio
> scelto.

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

**Seed e unit, precedenza (il più specifico vince):**

- Y: `seed` della banda (per-asse) → `axes.seed` globale → auto-derivato per-stream;
- X: `stack.<asse>.seed` → `stack.seed` globale → auto-derivato per-stream;
- unit: `stack.<asse>.unit` → `stack.unit` globale (per-stream via il deep-merge
  di `streams.<id>.stack`) → default `hz` (retrocompatibile).

L'auto-derivazione è un hash stabile (CRC32) dell'id dello stream, con salt
distinti per Y e X: senza seed globali gli stream impilati si **decorrelano da
soli**, restando riproducibili tra run.

## Il blocco `spread:` (stream generati)

`spread` è il terzo asse del sistema, quello della **macro-forma**: Y
distribuisce valori nel tempo (micro-forma), la camminata-X distribuisce i
tempi, `spread` distribuisce valori **nella popolazione di stream**. Una entry
di `streams:` con la chiave riservata `spread` non descrive un solo stream ma
ne **genera** `n`, distribuendo i valori di uno o più parametri secondo una
strategy — con lo stesso vocabolario dei generatori Y.

```yaml
streams:
  base: {}

  ventaglio:
    base:
      pointer:
        speed_ratio: 0          # override normale: vale per tutti i generati
    spread:
      n: 8                      # opzionale se una strategy possiede il conteggio
      over:                     # {path puntato nel documento: strategy}
        base.pointer.start:
          ramp: {start: 0.1, step: 0.1}    # 0.1, 0.2, ... 0.8
        base.onset:
          values: [0, 1, 2.5, 4, 6, 8, 10, 12]
        base.volume:
          base: -12             # banda: n estrazioni in [-12, -12+6]
          range: 6
          seed: 42              # opzionale (default stabile per-path)

  ventaglio_5:                  # patch: ritocca il quinto generato
    base:
      volume: -20
```

L'espansione avviene **prima** del merge delle stream: `ventaglio` sparisce e
al suo posto compaiono `ventaglio_1` … `ventaglio_8` (indice 1-based,
zero-padded alla larghezza di `n`: con `n: 12` si ha `ventaglio_01`), entry
ordinarie a tutti gli effetti (sotto-cartelle, seed per-stream, override). Lo
`study.yml` sorgente non viene riscritto: il dict espanso si può ispezionare
in `generated/<study>/yaml/streams_expanded.yml`, rigenerato da `sweep`/`stack`.

**Strategies e chi possiede `n`.** Una sola chiave-generatore per path, come
per gli assi:

| Strategy | Forma | Possiede `n`? | Valori |
|----------|-------|---------------|--------|
| `values` | lista esplicita | sì (`len`) | così com'è, anche non numerici (es. `sample`) |
| `ramp` | `{start, stop, step}` | sì (griglia) | il ramp pieno degli assi |
| `ramp` | `{start, step}` | no | progressione aritmetica `start + i·step` (offset additivo) |
| `ramp` | `{start, stop}` | no | suddivisione lineare in `n` punti |
| banda | `base`/`range`/`seed`/`distribution`/`drift` (+`n` opz.) | solo con `n` proprio | `n` estrazioni nella banda |

`spread.n` esplicito e conteggi posseduti devono **coincidere**; se `n` è
omesso lo definisce l'unico conteggio posseduto; nessuna fonte → errore. Con
più path in `over` i valori si appaiano **per indice** (niente prodotto
cartesiano, come in stack): lo stream i-esimo prende il valore i-esimo di ogni
strategy. Le forme-Env dentro le strategy (banda che scorre, nodi-generatore
annidati) valgono anche qui: `frac` corre sulla popolazione di stream.

**Ordine del merge** (il più specifico vince): override comune dell'entry →
valore della strategy → patch esplicita. Una entry esplicita omonima di un
generato è una **patch**: deep-merge sopra il generato e viene consumata (non
diventa uno stream in più), ovunque compaia nel documento. Una patch che è a
sua volta una spread è un errore (ambigua).

**Sweep spento di default.** Il senso di uno spread è l'ascolto verticale: i
generati entrano nel documento stack ma, se l'entry non dichiara un proprio
`sweep:`, ricevono `sweep: {orders: [], orderings: []}` e non moltiplicano le
varianti di sweep. Un `sweep:` esplicito nell'entry lo riattiva per tutti i
generati (una patch può riattivarlo per uno solo).

**Seed.** La banda senza `seed` deriva `stable_seed("<entry>:spread:<path>")`:
deterministico tra run, path diversi decorrelati da soli. I generati hanno poi
ciascuno il proprio `stream_id`, quindi i seed Y/X per-stream si
auto-decorrelano col meccanismo esistente.

## Layout di `generated/`

Primo livello = tipo di artefatto, secondo livello = **processo** (`sweep` /
`stack`). Il nome della stream è incorporato nel basename dei file sweep (non
solo nella sotto-cartella) per facilitare l'identificazione in Sonic
Visualiser; il documento stack è uno solo (gli stream vi sono collassati).

```
generated/<study_id>/
  yaml/sweep/envelope/<stream_id>/e1__density.yml
  yaml/stack/stack.yml
  yaml/streams_expanded.yml      # solo per studi con spread: il dict streams espanso
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
