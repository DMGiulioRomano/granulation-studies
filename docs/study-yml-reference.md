# Riferimento: `study.yml`

Sintassi completa con tutti i campi. I campi marcati `*` sono obbligatori.

```yaml
study_id: study01_grain_density   # * identificatore, usato come nome cartella
title: "Studio 01 — ..."          # libero, finisce nell'header dei file generati
seed: 1988                        # seed globale engine (finisce nei documenti generati)
duration: 30                      # durata di default (s) degli stream: ogni stream può
                                  #   dichiararne una propria (override, vedi `streams:`).
                                  #   Con `stack:` ogni stream deve risolverne una,
                                  #   propria o ereditata da qui.
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

# Processo versions (attivo per presenza; richiede `stack:`): repliche dello
# stack distribuite nel tempo, una per combinazione delle variabili — di
# default concatenate, con le chiavi riservate `onset`/`duration` posizionate
# liberamente. Vedi la sezione "Il blocco versions" sotto.
versions:
  d: {values: [1, 2, 3]}          # variabile -> generatore Y (values | ramp | banda con n)
  onset: {values: [0, 10, 40]}    # chiave riservata (opzionale): posizioni assolute
  duration: {values: [8, 8, 20]}  # chiave riservata (opzionale): durate per versione

# Processo stack (attivo per presenza del blocco): tutti gli stream sommati in
# UN documento multi-stream. Vedi la sezione "Il blocco stack" sotto.
stack:
  seed: 42                       # seed-X globale (chiave riservata; opzionale)
  unit: s                        # unita' globale della banda (chiave riservata;
                                 #   hz = frequenza, default | s = periodo in
                                 #   secondi | bpm = battiti al minuto)
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
    duration: 60                 # durata propria (s): vince sul default top-level
    onset: 5                     # posizione (s) dello stream nella timeline (default 0).
                                 # SOLO per-stream: `onset:` al top-level del documento
                                 # è rifiutato. Con `versions:` è relativo alla versione.
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
| nodo-expr `{expr, let}` | Env **calcolato** da un'espressione aritmetica su sagome e scalari (vedi «Il nodo-expr») |

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

### Il nodo-expr — aritmetica su Env

`{expr, let}` è una forma di Env che **calcola** i breakpoint invece di
scriverli o generarli: fattorizza forma e livello di una sagoma, per riusarla
a livelli diversi.

```yaml
axes:
  density:
    n: 4
    base:
      expr: "env * 50"              # sempre tra virgolette
      let:
        env: [[0, 1], [0.1583, 1.5]]   # → [[0, 50], [0.1583, 75]]
    range: 0
```

- **Grammatica**: numeri, nomi, `+ - * / // % **`, meno unario, parentesi,
  le chiamate alle **funzioni primitive** e le costanti `pi` / `e`. Niente
  indici, confronti o argomenti keyword — ogni altro costrutto è errore.
- **Funzioni primitive** (whitelist — il set generatore da cui derivare le
  altre): `abs`, `floor`, `ceil`, `sqrt`, `exp`, `log` (naturale, o
  `log(x, b)` per la base), `sin`, `cos`, `tan`, `atan`, `min`, `max`
  (variadiche, almeno 2 argomenti). Una chiamata con un argomento-Env agisce
  **sulle y** come gli operatori — `min(env, 10)` è un clamp del livello,
  `floor(env)` quantizza — e due Env nella stessa chiamata sono errore.
  `%` è il resto con semantica Python (segno del divisore); `//` il
  quoziente intero: `i % 3` e `i // 3` trasformano l'indice dello spread in
  coordinate di griglia. Fuori dominio (`sqrt` di un negativo, `log` di zero,
  potenza frazionaria di un negativo) è errore chiaro, non un NaN.
- **`let`** dichiara i nomi in scope: scalari o forme **statiche** di Env
  (`[a, b]`, `[[t, v], ...]`, `{type, points, curve}`). Un nodo-generatore
  dentro `let` è errore: i due meccanismi non si annidano — con una sola
  eccezione, la **banda-let** della strategy `expr` dello spread (un
  pescaggio random per stream generato, vedi «La strategy `expr`»).
- **Env ⊙ scalare** agisce **sulle y**, i tempi restano intatti; con la forma
  dict, `type`/`curve` si preservano. L'ordine conta dove deve
  (`100 - env`, `env / 2`). **Env ⊙ Env non è supportato** (errore).
- Vale ovunque c'è un Env: `base`/`range` (Y e camminata-X), `step` di
  ramp e di `drift`. Vale anche nei **parametri statici dello stream**
  (`base.volume`, `base.grain.duration`, ...): lì si valuta alla costruzione
  del documento engine e il risultato passa così come lo scriveresti a mano
  — l'engine accetta envelope diretti nei parametri stream, quindi il
  risultato deve essere una forma che l'engine capisce (scalare o envelope).
- Una **patch** di un generato di spread può rimpiazzare il valore calcolato
  con un altro nodo-expr: su un path-Env (`axes.*`/`stack.*`) la valutazione
  avviene alla seam degli assi, su un parametro statico alla costruzione del
  documento. In entrambi i casi mai nello spread.
- Le espressioni vanno **sempre quotate**: `expr: env * 50` senza virgolette
  è YAML valido ma fragile; con `{}` non lo è affatto.

Design completo: `docs/plans/expr-env-arithmetic.md`.

## Il blocco `stack:`

Il processo stack è il gemello verticale dello sweep: **collassa** tutti gli
stream di `streams:` in un solo documento engine (`yaml/stack/stack.yml`),
sommati. Parte solo se il blocco `stack:` è presente (anche vuoto: `stack: {}`);
ogni stream deve **risolvere una `duration`** — propria (override nello stream)
o ereditata dal default `duration:` top-level, che diventa opzionale se ogni
stream dichiara la sua. Camminate-X ed envelope `time_mode: normalized` si
normalizzano sulla duration *propria* dello stream; uno stream con `onset:`
proprio parte spostato nella timeline, e la durata documento copre tutto
(`max(onset + duration)`).
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
| camminata (`walk`, alla `rspline`) | asse **presente** con `{base: <env>, range?: <env>, seed?: int, unit?: hz\|s\|bpm, distribution?, drift?}` | la **X**: `n` emerge dalla banda integrata sulla durata |

Con la camminata a ogni punto si pesca un valore nella banda
`[base(t), base(t)+range(t)]` (`base`/`range` accettano le stesse forme della
banda di Y). Con `unit: hz` (default) il valore è una **frequenza di
generazione** e il punto successivo cade a `t + 1/f`; con `unit: s` è il
**periodo** in secondi e il punto cade a `t + p` — comodo quando gli intervalli
sono nell'ordine delle decine di secondi e le frequenze frazionarie (0.0x Hz)
diventano scomode; con `unit: bpm` sono **battiti al minuto** e il punto cade a
`t + 60/v` — comodo quando il gesto si pensa come pulsazione. Le unità vivono
nel registro `X_UNITS` di `x_strategies`: aggiungerne una nuova è una entry
(convertitore valore → passo in secondi) più doc e test. Anche
`distribution` e `drift` valgono qui, con la stessa
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
> scelto. Le famiglie sono due: **rate** (`hz`, e `bpm` che è hz riscalato per
> 60 — la banda `[60, 120]` bpm è esattamente la banda `[1, 2]` Hz) e
> **periodo** (`s`). `bpm` è zucchero notazionale sullo spazio-rate; `s` è uno
> spazio davvero diverso.

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

## Il blocco `versions:`

Il processo versions è un **processo indipendente** come sweep e stack:
richiede il blocco `stack:` (le versioni sono repliche dello stack) ma ha
sottocomando (`make versions`) e output propri, `yaml/versions/versions.yml`.
`make stack` resta **puro**: produce il materiale com'è scritto in
`yaml/stack/stack.yml`, ignorando il blocco `versions:` — è l'ascolto
dell'istanza di partenza (vedi `percorso`, issue #29). Dove lo stack collassa
gli stream in un documento, versions **replica quel collasso N volte nel
tempo**: una replica per combinazione delle variabili. Di default le versioni
si concatenano; con le chiavi riservate `onset`/`duration` si distanziano o
sovrappongono liberamente.

```yaml
versions:
  f: {values: [50, 100]}          # prima variabile = esterna (lenta)
  d: {values: [1, 2, 3]}          # ultima = interna (veloce)
  onset:    {ramp: {start: 0, stop: 100}}   # riservata: 6 posizioni assolute
  duration: {base: 15, range: 10}           # riservata: 6 durate in [15, 25]
```

- Ogni chiave è un **nome di variabile** (identificatore libero; `i`, `n`,
  `pi`, `e` sono riservati agli scope expr e vengono rifiutati). Il valore è
  un generatore del vocabolario Y: `values`, `ramp`, o banda — qui la banda
  richiede **`n`** (non c'è una camminata-X a possedere il conteggio); senza
  `seed` deriva `stable_seed("<study>:versions:<nome>")`.
- Più variabili → **prodotto cartesiano lessicografico** nell'ordine di
  dichiarazione (come gli `orderings` dello sweep): con l'esempio sopra le
  versioni sono (50,1) (50,2) (50,3) (100,1) (100,2) (100,3).
- Per ogni combinazione i valori vengono **iniettati negli scope `let`** dei
  nodi-expr che *nominano* la variabile, ombreggiando il default dichiarato
  (`let: {d: 0}`). Il default tiene lo studio valido anche senza il blocco;
  una variabile che nessuna espressione referenzia è un errore di parse
  (guardia anti-refuso). L'iniezione vale ovunque un nodo-expr viva: bande di
  Y, camminate-X, parametri statici dello stream.
- Ogni versione replica **tutti** gli stream dello stack, spostati sulla
  posizione della versione e con lo `stream_id` suffissato con l'etichetta
  della combinazione (`mobile__f=50__d=1`). Envelope, camminate e seed passano
  per il builder dello stack **identici**: tra una versione e l'altra cambia
  solo il valore delle variabili — è il confronto pulito del metodo. La durata
  documento è `max(onset + duration)` su tutti gli stream (nel caso classico
  concatenato coincide con `N * duration`).
- **`onset` e `duration` come chiavi riservate** (issue #26): non sono
  variabili — non entrano nel prodotto cartesiano né negli scope `let` — ma
  generatori della **timeline**: producono una sequenza lunga N (numero di
  combinazioni) mappata **1:1** sull'ordine lessicografico delle versioni
  (funzioni di k). Il conteggio lo possiede il prodotto cartesiano: `values`
  deve avere esattamente N elementi; la banda deduce `n = N` (un `n` esplicito
  diverso è errore); `ramp` senza `step` distribuisce N valori equispaziati
  `start → stop`, con `step` la griglia deve contare esattamente N. Una banda
  senza `seed` deriva `stable_seed("<study>:versions:onset")` /
  `"...:duration"`.
  - `onset[k]` è la posizione **assoluta** della versione k. Non monotono è
    legittimo: sovrapposizioni e buchi emergono dai valori (il merge degli
    stem fa overlay-add con clip). L'`onset` per-stream resta **relativo alla
    propria versione**: `onset_finale = onset_versione + onset_stream`.
  - `duration[k]` fa da **default** di `duration:` per gli stream della
    versione k (iniettata prima del parse): una `duration` propria dello
    stream vince comunque.
  - Chiavi assenti → le versioni si **concatenano** sulle durate di versione
    (col solo `duration:` top-level è il classico `onset = k * duration`,
    retrocompatibile). `duration:` top-level serve solo quando nessun'altra
    fonte posiziona le versioni: con `versions.onset` (e durate risolte
    per-stream) o `versions.duration` può mancare.
- Il confine tra versioni è un confine naturale di stream (l'engine chiude
  una granulazione e ne apre un'altra): nessuna transizione interpolata tra
  versioni. Per ammorbidire il bordo si lavora con gli envelope di volume
  degli stream, come sempre.
- **Onset in Sonic Visualiser.** Nel `.sv` del **mix** (`stack_to_sv`) l'onset
  è rispettato: l'audio è un unico file con gli onset già cotti nel buffer, e
  gli envelope sono ancorati al loro onset reale (`onset + t·durata_stream`,
  non stirati sulla durata totale). Nel `.sv` **per-stem**
  (`stack_stems_to_sv`) SV non sa offsettare un file audio nella timeline
  (il parser `.sv` ancora ogni wavefile al frame 0, nessun attributo di
  offset): per gli stream con `onset > 0` l'export genera quindi una **copia
  paddata** dello stem — `onset` secondi di silenzio prepesi — in
  `audio/versions/padded/`, e ancora lì gli envelope. Gli stem originali non
  vengono toccati; le copie si rigenerano solo se l'originale è più nuovo.
- **Stem accorpati per voce logica.** In STEMS mode ogni combinazione produce
  il proprio stem (`versions__fermo__d=1.aif`, `versions__fermo__d=2.aif`, ...):
  con molte combinazioni il `.sv` per-stem avrebbe un pane per file. Dopo la pass
  STEMS il render fa quindi un **post-merge per nome-base** (lo `stream_id`
  prima del primo `__`): le versioni di una stessa voce logica vengono sommate
  al proprio onset (overlay-add con clip: regge anche versioni sovrapposte) in
  un unico file `versions__{voce}.aif`, ancorato al tempo 0 del documento. `stack_stems_to_sv`
  consuma i file accorpati: **un pane per voce logica**, con gli envelope di
  ogni versione offsettati al proprio onset dentro il pane. Gli stem per
  combinazione restano su disco intatti; i file accorpati si rigenerano solo
  se uno stem sorgente è più nuovo.

Il caso d'uso fondativo (due stream con inviluppo condiviso e offset che
cresce di versione in versione) è in `studies/study_versions_test/study.yml`:
l'inviluppo si scrive una volta nel default di `axes:` (`expr: "env + d"`,
`let: {env: ..., d: 0}`), lo stream fermo ridefinisce solo `expr: "env"`
(il `let` si eredita via deep-merge), e `versions: {d: {values: [1, 2, 3]}}`
genera le tre coppie concatenate.

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
| `expr` | `{expr, let}` | no | un eval per stream: `i` (0-based), `n` e le bande-let in scope |

`spread.n` esplicito e conteggi posseduti devono **coincidere**; se `n` è
omesso lo definisce l'unico conteggio posseduto; nessuna fonte → errore. Con
più path in `over` i valori si appaiano **per indice** (niente prodotto
cartesiano, come in stack): lo stream i-esimo prende il valore i-esimo di ogni
strategy. Le forme-Env dentro le strategy (banda che scorre, nodi-generatore
annidati) valgono anche qui: `frac` corre sulla popolazione di stream.

**La strategy `expr`** è il nodo-expr (vedi «Il nodo-expr») con due nomi in
più nello scope: `i`, l'indice 0-based dello stream generato, e `n`, il
conteggio totale (`i / (n - 1)` è il progresso normalizzato). Il risultato —
scalare o Env intero — va così com'è sul path. Ridefinire `i` o `n` in `let`
è errore; il conteggio non è mai posseduto da `expr` (serve `spread.n` o una
strategy sorella che lo possiede).

```yaml
spread:
  n: 4
  over:
    axes.density.base:
      expr: "env * a * (i + 1)"     # livelli 50, 100, 150, 200 — stessa sagoma
      let:
        env: [[0, 1], [0.1583, 1.5]]
        a: 50
```

**La banda-let (random per stream).** Solo nella strategy `expr` dello
spread, una variabile di `let` può essere una **banda**
(`{base, range?, seed?, distribution?, drift?}`): per ogni stream generato
viene pescato un valore nella banda, che entra nello scope dell'espressione
accanto a `i` e `n`. È l'unica eccezione al divieto di nodi-generatore in
`let`; `values`/`ramp` restano fuori (una progressione deterministica si
scrive con l'aritmetica su `i`/`n`). La banda non possiede mai il conteggio
(`n` dentro la banda-let è errore) e `frac` corre sulla popolazione di
stream, come nelle altre strategy: un `base`-Env fa scorrere la banda lungo
i generati (con `range` omesso la segue deterministicamente). Deterministico
via seed: senza `seed` esplicito ogni variabile deriva il proprio (vedi
«Seed» sotto), quindi variabili e path diversi si decorrelano da soli.

```yaml
spread:
  n: 8
  over:
    base.volume:
      expr: "v - 2 * i"             # pescaggio + gradino deterministico
      let:
        v: {base: -12, range: 6}    # banda-let: un random per stream in [-12, -6]
    axes.density.base:
      expr: "env * g"
      let:
        env: [[0, 1], [0.1583, 1.5]]
        g: {base: 40, range: 20, seed: 42}   # stessa sagoma, livello random
```

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

**Seed.** La banda senza `seed` deriva `stable_seed("<entry>:spread:<path>")`;
una banda-let senza `seed` deriva `stable_seed("<entry>:spread:<path>:let:<var>")`:
deterministico tra run, path e variabili diversi decorrelati da soli. I generati
hanno poi ciascuno il proprio `stream_id`, quindi i seed Y/X per-stream si
auto-decorrelano col meccanismo esistente.

## Layout di `generated/`

Primo livello = tipo di artefatto, secondo livello = **processo** (`sweep` /
`stack` / `versions`). Il nome della stream è incorporato nel basename dei
file sweep (non solo nella sotto-cartella) per facilitare l'identificazione
in Sonic Visualiser; i documenti stack e versions sono uno per processo (gli
stream vi sono collassati).

```
generated/<study_id>/
  yaml/sweep/envelope/<stream_id>/e1__density.yml
  yaml/stack/stack.yml
  yaml/versions/versions.yml     # solo per studi con blocco versions
  yaml/streams_expanded.yml      # solo per studi con spread: il dict streams espanso
  audio/sweep/envelope/<stream_id>/<stream_id>_e1__density.aif
  audio/stack/stack.aif
  audio/versions/versions.aif
  sv/sweep/envelope/<stream_id>/<stream_id>_e1__density.sv
```

`generated/` è rigenerabile: dopo un aggiornamento basta rilanciare
`make sweep` / `make stack` / `make versions`.

## Comandi Make

```bash
make sweep  STUDY=<id>                    # genera tutte le stream
make sweep  STUDY=<id> STREAM=nome        # genera solo quella stream
make stack  STUDY=<id>                    # genera il documento multi-stream (stack, puro)
make versions STUDY=<id>                  # genera il documento delle versioni (prodotto cartesiano)
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
