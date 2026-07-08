# Piano — generatori annidati negli envelope di soglia

**Repo:** `granulation-studies` (branch `claude/nested-generators-granulation-s7cowp`)
**Stato:** proposta di design, **nessun codice scritto**. Le decisioni marcate
*(proposta)* vanno confermate; le *Questioni aperte* in fondo vanno discusse
prima di implementare. Lingua: italiano, no emoji.

---

## 1. Intento

Oggi i parametri-banda di `rand` (`base`/`range` nella Y, `cps.base`/`cps.range`
nella X-rand dello stack) accettano quattro forme statiche: scalare, `[a, b]`,
`[[t, v], ...]`, `{type, points}`. La richiesta: poter scrivere **un generatore
dentro quei parametri**, ricorsivamente — un `rand` dentro il `base` di un
`rand`, un `ramp` dentro il `range` di una X-rand, a profondità arbitraria.

Dopo il PR #9 (`feat(rand)!`) Y-rand e X-rand condividono la stessa semantica
di banda `[base(t), base(t) + range(t)]` (`_band_at`): il design qui sotto vale
verbatim per entrambe, senza casi speciali.

Vincolo di confine: **l'engine non si tocca**. I generatori annidati si
risolvono interamente in granstudies; l'engine continua a ricevere envelope
ordinari (`[[t, v], ...]` + `type`). Nessuna modifica a `yaml_builder`, ai
documenti generati, o al submodule.

## 2. Il punto d'appoggio: l'envelope di 2° ordine esiste già

`value_generators._threshold_at(spec, frac)` valuta già oggi una banda mobile:
è l'"envelope di secondo ordine" documentato in `study-yml-reference.md`. Il
tipo `Threshold` è il punto esatto dove innestare la ricorsione — non serve
inventare un livello nuovo, serve rendere ricorsivo un livello che c'è già.

Le tre seam dove un generatore viene invocato, tutte col **seed effettivo già
risolto** in mano:

| Seam | File | Cosa risolve |
|---|---|---|
| sweep / Y | `study_spec.py` (`resolved_cfg` + `resolve_values`) | `rand` con `n` al parse |
| stack / Y | `stack.axis_envelope` (entrambi i rami: `rand_at` e `GENERATORS[y_key]`) | Y all'assemblaggio |
| stack / X | `stack.axis_envelope` → `x_strategies.rand` | tempi da `cps` |

## 3. L'idea cardine: una banda è un mini-asse

Un generatore produce `List[float]` (n valori). Un envelope è una funzione
`frac -> float`. Il ponte tra i due esiste già nel progetto: è quello che fa la
strategy-X `linear` — n valori si stendono su tempi equispaziati
`t_i = i/(n-1)` e diventano breakpoint `[[t_i, v_i], ...]`.

Quindi: **un generatore annidato si compila in breakpoint**, cioè in una delle
forme che `Threshold` accetta già. Il bordo di una banda diventa un asse in
miniatura: stesso vocabolario Y (`values`/`ramp`/`rand`), X implicita lineare,
curva scelta con `type` (`linear`/`step`, come nella forma `{type, points}`).

Tre conseguenze che rendono il design piccolo:

1. **Le firme dei generatori non cambiano.** `rand(n, base, range, seed)`
   accetta già breakpoint in `base`/`range`; idem `cps.base`/`range` in X-rand.
   Il generatore annidato è zucchero che si desugara nella grammatica di oggi.
2. **La ricorsione vive in un punto solo**: una funzione di espansione in
   `value_generators.py`, chiamata alle tre seam prima di invocare il
   generatore. `_threshold_at`, `rand`, `rand_at`, `x_rand` restano puri e
   intoccati.
3. **Niente arriva all'engine.** I breakpoint annidati servono solo a
   disegnare la banda mentre si estraggono i valori esterni; nello YAML engine
   finisce, come oggi, soltanto l'envelope dell'asse.

### Alternativa scartata: valutazione lazy in `_threshold_at`

Insegnare a `_threshold_at` a riconoscere un nodo-generatore e risolverlo al
volo significherebbe rieseguire il generatore a ogni `frac` (O(n·m) invece di
O(n+m)) e infilare il contesto seed dentro una funzione oggi pura e calda.
Scartata: si **compila una volta**, si valuta n volte.

### Alternativa scartata: espansione al parse per tutto

Espandere tutto in `study_spec` (macro-expansion a monte) è pulito ma rompe
l'invariante dello stack: la Y `rand` senza `n` e la X si risolvono
all'assemblaggio, col seed per precedenza per-stream. L'espansione sta dove
sta già l'iniezione del seed: al momento dell'invocazione, per ciascuna seam.
(Per lo sweep quel momento coincide col parse — nessuna differenza pratica.)

## 4. Grammatica

```
Env ::= scalare                            # banda a livello costante
      | [a, b]                             # rampa lineare a -> b
      | [[t, v], ...]                      # breakpoint, interpolazione linear
      | {type: linear|step, points: [[t, v], ...]}
      | {type?: linear|step, GEN}          # NUOVO: bordo generato

GEN ::= values: [v, ...]                   # stesi su t_i = i/(n-1)
      | ramp:   {start, stop, step: Env}   # step mobile: accelerando/ritardando (§4.1)
      | rand:   {n, base: Env, range?: Env, seed?}   # base/range ricorsivi
```

`GEN` non è una lista chiusa: è **l'intero registry** (`values` + tutto ciò che
sta in `GENERATORS`). L'espansione è registry-driven — il predicato di nodo e
il walk generico sui parametri non conoscono le singole strategie — quindi ogni
generatore futuro aggiunto al registry diventa annidabile gratis, e ogni suo
parametro di tipo `Env` accetta a sua volta generatori.

La forma dict si generalizza: `{type, points}` e `{type, <generatore>}` sono
lo stesso nodo — `points` dà i breakpoint letterali, la chiave-generatore li
genera. Predicato di riconoscimento: dict con **esattamente una** chiave tra
`{values, ramp, rand}`, più l'opzionale `type`. Nessuna collisione con le
forme esistenti (`type`/`points` non sono nomi di generatore; le liste restano
liste).

Regole:

- **`n` obbligatorio nel `rand` annidato.** La n-ownership è una faccenda del
  coupling X/Y degli assi; dentro un envelope non c'è coupling: il nodo deve
  poter produrre da solo la sua lista finita. `rand` senza `n` in un `Env` è
  errore di parse. (`ramp` e `values` la posseggono per costruzione.)
- **X implicita lineare.** I valori del nodo si stendono equispaziati. Dare al
  mini-asse una sua strategy-X (tempi non equispaziati dentro la banda) è
  l'estensione naturale v2 — la forma a dict ha spazio per una chiave in più —
  ma resta fuori da questa iterazione.
- **Ricorsione ovunque c'è un `Env`**: quindi in `base`/`range` del `rand`
  annidato stesso — profondità arbitraria. Guardia di profondità esplicita
  (proposta: 8) nella filosofia di `MAX_POINTS`: meglio un errore chiaro che
  una config degenere (gli alias YAML ricorsivi esistono).

### 4.1 `ramp` con `step: Env` — accelerando e ritardando

Verificato sul codice: il `ramp` di oggi è **solo aritmetico**
(`ramp(start, stop, step)`, `step` scalare costante `> 0`). Accelerando e
ritardando non esistono ancora; questa estensione li introduce promuovendo
`step` da scalare a `Env` — la stessa mossa di `base`/`range`, quindi anche
`step` accetta le quattro forme statiche *e i generatori annidati*.

Semantica: `step` è una funzione del **progresso in valore**,
`frac = |v − start| / |stop − start|` (non dell'indice: il conteggio dei passi
non è noto a priori). Si itera `v += sign · step(frac(v))` finché si raggiunge
`stop`; `n` **emerge** dall'integrazione, come i tempi della X-rand.

```yaml
ramp: {start: 5, stop: 100, step: 5}          # oggi: passo costante
ramp: {start: 5, stop: 100, step: [10, 1]}    # accelerando: i passi si stringono
ramp: {start: 5, stop: 100, step: [1, 10]}    # ritardando: i passi si allargano
ramp:
  start: 5
  stop: 100
  step:
    rand: {n: 4, base: 1, range: 6}           # rampa a passo stocastico (ricorsione)
```

Guardie: `step(frac) <= 0` in qualunque punto → errore (passo nullo = loop
infinito, come la frequenza non positiva di X-rand); tetto punti alla
`MAX_POINTS`. `ramp` resta deterministico e continua a possedere `n`; il caso
scalare resta identico al comportamento attuale (retrocompatibile, conteggio
anti-drift incluso).

Nota di disambiguazione, importante per non confondersi con lo stack: questo è
l'accelerando **dei valori** (la griglia di Y si infittisce). L'accelerando
**nel tempo** (breakpoint che si addensano sulla timeline) è dominio della
strategy-X: una futura X-`ramp` accanto a `linear`/`rand` in `X_STRATEGIES` —
coerente col registry, ma fuori da questa iterazione (v. Questioni aperte).

## 5. Esempi

Y-rand con bordi generati (sweep o stack, identico):

```yaml
axes:
  density:
    path: density
    rand:
      n: 40
      base:
        rand: {n: 6, base: 2, range: 6}    # il pavimento della banda: random walk a 6 punti
      range:
        type: step
        rand: {n: 6, base: 4, range: 10}   # la larghezza: salti netti tra 4 e 14
```

X-rand dello stack con frequenza di generazione essa stessa stocastica — il
caso citato nella richiesta (`base`/`range`), con un terzo livello:

```yaml
stack:
  density:
    rand:
      cps:
        base:
          rand: {n: 8, base: 2, range: 4}  # la base salta tra 2 e 6 Hz
        range:
          rand:
            n: 5
            base: 0.5
            range:
              ramp: {start: 1, stop: 4, step: 1}   # terzo livello
```

## 6. Semantica: cosa aggiunge (e cosa no)

Musicalmente l'annidamento è **controllo della varianza a più scale
temporali**: il `rand` esterno dà la fluttuazione punto-per-punto, il `rand`
annidato dà la deriva a media scala, un livello ancora sotto disegna la
macro-forma. La scomposizione `base`/`range` del PR #9 rende le due leve
ortogonali anche qui: annidare in `base` muove il **centro** della tessitura
(la banda trasla come un corpo solo, larghezza intatta), annidare in `range`
ne fa **respirare la varianza** (il centro sta fermo, la dispersione si apre e
si chiude). È l'idea rspline-di-rspline; col vocabolario del progetto: un
`range` con `type: step` costruisce **plateau di banda** — si fa sedere lo
stream in una regione stocastica, poi si salta a un'altra.

Casi degeneri, da documentare per onestà:

- `ramp` annidato **a passo costante** con interpolazione linear ≡
  `[start, stop]`: non aggiunge nulla. Aggiunge con `type: step` (banda a
  scalini) o con `step: Env` (§4.1): l'accelerando curva la rampa, e annidata
  in un bordo dà una banda che deriva con morfologia non lineare.
- `values` annidato ≡ `[[t, v], ...]` con tempi equispaziati: solo comodità.
- la banda che si muove a larghezza costante non richiede trucchi: `base`
  annidato + `range` scalare. Con il vecchio vocabolario `min`/`max` sarebbe
  servito correlare due generatori con lo stesso seed; la scomposizione del
  PR #9 lo dà per costruzione, e l'annidamento la eredita.

## 7. Seed: derivazione gerarchica

Requisiti: deterministico tra run e macchine (ciclo rigenera-e-confronta),
decorrelato tra `base` e `range` e tra profondità, esplicito che vince ovunque.
Stessa filosofia della catena esistente (il più specifico vince; auto-derivazione
CRC32 con salt).

*(proposta)* Ogni nodo `rand` annidato senza `seed` proprio deriva:

```
seed_figlio = stable_seed(f"{seed_effettivo_del_padre}:{path_locale}")
```

dove `path_locale` è `base`, `range`, `cps.base`, `cps.range` (e si concatena
scendendo: `base.range`, ...). Proprietà:

- cambiare il seed esterno **riseeda l'intero sottoalbero**: l'oggetto si
  rigenera coerente;
- fissare un seed a un nodo **congela solo quel sottoalbero**;
- `base` e `range` si decorrelano da soli (path diversi);
- il padre ha sempre un seed effettivo definito, perché l'espansione avviene
  alla seam dove la catena per-asse → globale → auto per-stream è già risolta.

`ramp` e `values` non consumano seed: la derivazione attraversa i nodi
deterministici senza consumare nulla (il path però li include, così un `rand`
sotto un `ramp` resta stabile se si riordina il resto).

## 8. Dove vive nel codice

Tutto in granstudies, tre file toccati più i test:

1. **`value_generators.py`** — il cuore, ~3 funzioni nuove:
   - `is_generator_node(spec) -> bool`: il predicato del §4;
   - `expand_env(spec, *, seed, path, depth) -> Threshold`: compila un nodo in
     breakpoint (o `{type, points}` se il nodo ha `type`), ricorsivo;
   - `expand_params(params, *, seed, path) -> dict`: cammina i parametri di un
     generatore e espande ogni valore che è un nodo (walk generico sui dict,
     così `cps.base` si trova senza schema per-generatore);
   - `ramp` riscritto per `step: Env` (§4.1): iterazione a passo mobile con
     guardie, ramo scalare identico all'attuale.
2. **`study_spec.py`** — seam sweep/Y: `expand_params` su `resolved_cfg` subito
   dopo l'iniezione del seed di default, prima di `resolve_values`.
3. **`stack.py`** — seam stack: `expand_params` su `y_kwargs` (entrambi i rami)
   e su `x_params` dopo i rispettivi `setdefault("seed", ...)`.
4. **`x_strategies.py`** — invariato: riceve `cps` già espanso.
5. **`docs/study-yml-reference.md`** — la tabella delle forme di banda guadagna
   la riga del generatore annidato, con gli esempi del §5 e il trucco dei bordi
   correlati.

Nota di doppia risoluzione: per un asse sweep con Y-rand, il parse espande e
risolve i valori, ma `Axis.generator` conserva la config grezza per lo stack,
che ri-espande all'assemblaggio. Stesso seed → stessi breakpoint: le due
espansioni non possono divergere.

### Walk generico vs schema esplicito

Un'alternativa più rigida: dichiarare per ogni generatore quali parametri sono
di tipo `Env` (`ENVELOPE_PARAMS = {"rand": {"base", "range"}, ...}`) ed espandere
solo quelli. Più contratto, più boilerplate, e ogni generatore futuro deve
registrarsi due volte. Col predicato stretto del §4 il walk generico non ha
falsi positivi sul vocabolario attuale. *(proposta: walk generico; se un giorno
un generatore avrà un parametro dict che può confondersi, si passa allo schema.)*

## 9. Validazione ed errori

- **path negli errori**: l'espansione porta con sé il path di config
  (`axes.density.rand.base.rand`) e ne decora i `ValueError`; il runtime
  `range negativo a frac=...` di `_band_at` resta l'ultima rete.
- `rand` annidato senza `n` → errore al parse (§4).
- due chiavi-generatore in un nodo → errore standard (riuso del messaggio di
  `resolve`).
- profondità oltre la guardia → errore esplicito.
- i valori estratti dal `rand` esterno restano clampati ai bounds engine dove
  già avviene (stack); i breakpoint *interni* non si clampano: sono soglie, non
  valori di parametro.

## 10. Piano di test (TDD, `tests/test_value_generators.py` + `test_stack.py`)

- unit espansione: `values`/`ramp`/`rand` annidati → breakpoint attesi; nodo
  con `type: step`; profondità 3; passthrough delle forme statiche esistenti.
- seed: stessa config → stessi breakpoint tra due run; `base`/`range`
  decorrelati di default; seed esplicito nel nodo vince; cambiare il seed
  esterno cambia il sottoalbero; banda a larghezza costante con `base` annidato
  e `range` scalare.
- ramp accelerando: `step: [a, b]` produce passi monotoni attesi; ramo scalare
  invariato bit-a-bit (regressione anti-drift); `step` che tocca 0 → errore;
  tetto punti; generatore annidato dentro `step`.
- errori: `rand` annidato senza `n`; due chiavi-generatore; profondità oltre
  guardia; `range` negativo con path nel messaggio.
- integrazione stack: study di prova con nested in `cps.base` → `stack.yml`
  identico tra due generazioni; le combinazioni di n-ownership esistenti non
  cambiano output (regressione con i 4 study `study_stack_test_*`).
- una volta implementato: `study_stack_test_5` come studio-documentazione dei
  generatori annidati, nello stile dei quattro esistenti.

## 11. Questioni aperte

1. **Accelerando nel tempo**: una strategy-X `ramp` in `X_STRATEGIES` (tempi
   che si addensano/diradano sulla timeline dello stack) e, in seconda battuta,
   una strategy-X per il mini-asse (tempi non equispaziati dentro la banda).
   La grammatica ha spazio per entrambe; v2. L'accelerando dei valori (§4.1)
   copre già parte del bisogno?
2. **Nome della chiave di curva nel nodo**: `type` (coerente con
   `{type, points}`) o `interpolation` (coerente con gli assi)? Proposta:
   `type`, perché il nodo vive nel mondo `Env`. E `type: cubic` dentro una
   banda: lo si ammette o si resta su `linear|step`? (Oggi `_threshold_at`
   conosce solo quelle due.)
3. **`values` annidato**: lo includiamo per simmetria (proposta: sì, costa una
   riga) o si tiene il vocabolario minimo `ramp|rand`?
4. **Guardia di profondità**: 8 basta e avanza, o si vuole più margine?
