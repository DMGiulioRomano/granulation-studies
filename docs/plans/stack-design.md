# Piano — modo `stack` (multi-stream verticale) in granulation-studies

**Repo:** `granulation-studies` (branch `main`)
**Stato:** design **chiuso** salvo le *Questioni aperte* in fondo. Nessun codice
scritto. Lingua: italiano, no emoji.

> **Questo documento sostituisce** `/private/tmp/granulation-stack-handoff.md`.
> Dove i due divergono, vale questo. La mappa vecchio→nuovo è nella sezione
> *Rapporto col vecchio handoff*.

> **Terminologia:** si parla sempre di **stream**, mai di "voci". Uno stack è un
> insieme di stream con lievi variazioni, sommati in un documento.

---

## 1. L'invariante (il cardine di tutto)

**`axes` conosce solo Y. Il processo possiede X (e la durata).**

- `axes` dichiara *cosa* si anima e *con che valori/curva*: `path`, `baseline`,
  il generatore (`values`/`ramp`/`rand`), `interpolation`. Niente timeline.
- Chi possiede X possiede anche la durata, in modo simmetrico:
  - **sweep** possiede X via `plateau`/`transition` → *deriva* la durata
    (`N*plateau + (N-1)*transition`);
  - **stack** possiede X via la sua strategy-X → *legge* la durata condivisa
    da `duration:` e ci normalizza sopra.

L'ambiguità "un documento, quante durate?" non si arbitra: sparisce perché i due
processi non condividono mai uno stream di output.

## 2. I due processi

Non sono due "modi" che si contendono uno stream: sono **due processi separati e
indipendenti**, distinti dalla cardinalità dell'output.

| | legge | possiede X | output |
|---|---|---|---|
| `axes` | (vocabolario Y, condiviso) | — | — |
| processo **`sweep`** | `axes` + `sweep:` (plateau/transition/orders/orderings/mode) | plateau/transition | **N file** (varianti enumerate, prodotto cartesiano) |
| processo **`stack`** | `axes` + `stack:` (strategy-X per stream) | registry strategy-X, default `linear` | **1 file** (stream sommati in un YAML) |

`streams:` resta il dizionario delle versioni: `sweep` lo **esplode** in file
separati (comportamento di oggi), `stack` **collassa** gli stream che vi hanno
aderito in un documento solo. Stesso materiale, due assemblaggi.

## 3. Decisioni chiuse — non riaprire senza motivo

1. **Stream = versione con lievi variazioni.** Uno stream è una versione
   leggermente diversa dello stesso comportamento sonoro; sono le entry di
   `streams:` (meccanismo `_deep_merge` esistente), non un tipo nuovo. Niente
   "voci": sono streams.
2. **Vincolo 2 parametri.** study01 usa solo `density` e `grain.duration`.
   Verticalità/accordi/polimetrie emergono dallo stacking, non da parametri nuovi.
3. **Tre cose ortogonali**, da non confondere:
   - generatore di **Y** (`values`/`ramp`/`rand`) → la sequenza di valori;
   - strategy di **X** (registry nuovo) → la sequenza di tempi in `[0,1]`;
   - **interpolation** (`linear`/`cubic`/`step`) → la curva tra i breakpoint.
   Attenzione alle due "linear": strategy-X lineare (tempi equispaziati) ≠
   interpolation lineare (retta tra due punti). Puoi avere X accelerando con
   interpolation step.
4. **Registry strategy-X.** La X duration-based NON è "equispaziato": equispaziato
   è *una* strategy (`linear`, il default). Il registry è gemello di
   `value_generators.GENERATORS`: funzioni pure `(n, **params) -> List[float]`
   che ritornano tempi normalizzati in `[0,1]`; una funzione + una riga per
   aggiungerne (`accelerando`, `ritardando`, esponenziale, ...).
5. **In stack gli assi NON si combinano.** Niente prodotto cartesiano, niente
   zip. Ogni asse di uno stream diventa un **envelope indipendente**: density è un
   envelope, grain.duration è un altro, coesistono sulla stessa durata, ognuno coi
   suoi valori e la sua strategy-X. Più assi = più envelope paralleli, non una
   griglia combinatoria. Stack **non tocca** la combinatoria di `sweep.py`/
   `envelope_sweep.py`.
6. **`stack:` è per-stream, come `sweep:`.** È un blocco top-level (il default,
   "lo stack di partenza del base") che ogni stream può override-are via
   `streams:`. Se uno stream aderisce ma non specifica config, eredita quella del
   documento. Questo dà il per-stream gratis: ogni stream ha già la sua strategy-X
   per eredità. Il per-asse dentro uno stream (`x` default + override per singolo
   asse) vive *dentro* quel blocco `stack`, mai in `axes` (invariante).
7. **Attivazione per presenza.** Parte solo ciò che è definito a livello
   documento. Se ci sono sia `sweep:` sia `stack:`, partono entrambi i processi
   (N file + 1 file); se c'è solo uno, parte solo quello. **Nessun selettore
   `mode:`**: la presenza del blocco è l'interruttore.
8. **Sweep resta a timeline singola.** L'envelope-sweep sincronizza i breakpoint
   di tutti gli assi mossi sulla stessa griglia (`envelope_sweep.overrides()`).
   Non si retrofitta il per-asse-X in sweep: romperebbe la sincronizzazione. Il
   per-asse-X è una capacità di **stack**.
9. **Tutti gli stream entrano nello stack di default; l'esclusione è via mute.**
   Il documento engine somma tutti gli stream elencati; per non sentirne uno lo si
   mette in mute con un override del suo `volume` nel `base` (meccanismo nativo
   dell'engine). Niente chiave di opt-in a livello studio: la mappatura `streams:`
   (studio) → `streams:` (engine) è 1:1, e il gain per-stream è già il modo con cui
   si silenzia uno stream. Il blocco `stack:` per-stream resta **solo config** della
   strategy-X — non è un gate di partecipazione; assente = eredita il default
   top-level. **Conseguenza:** study01 ha ~8 stream ereditati dall'era sweep — di
   default entrano tutti; per ascoltarne un sottoinsieme si mutano gli altri.
   **Nota:** il mute su `base.volume` è globale (silenzia lo stream anche
   nell'output sweep); un mute solo-stack vivrebbe nel blocco `stack:`, non lo
   costruiamo ora.
10. **Layout `generated/` per-artefatto (Q1 chiusa).** Primo livello = tipo di
    artefatto, secondo livello = **processo** (`sweep`/`stack`). Oggi il primo
    livello è incoerente (`variants/` sono yaml di sweep, ma `audio/`/`sv/` sono
    tipi di artefatto) e il nome `variants` è output-di-sweep, non un processo;
    si corregge così — il secondo livello prende il nome del processo, simmetrico:

    ```
    generated/<study>/
      yaml/    sweep/{discrete,envelope}/[stream]/   stack/stack.yml
      audio/   sweep/{discrete,envelope}/[stream]/   stack/stack.aif
      score/   sweep/{discrete,envelope}/...
      sv/      sweep/envelope/[stream]/              (stack: se/quando serve)
    ```

    - `yaml/sweep/` = identico a oggi (`discrete`/`envelope`/`stream`), solo
      rinominata la cartella contenitrice da `variants/` a `sweep/`.
    - `yaml/stack/stack.yml` = il documento multi-stream (un solo file: stack
      collassa gli stream, non enumera).
    - **`render` resta generico:** `variant_dir = yaml/`, `audio_dir = audio/` →
      rispecchia da solo `sweep/…` e `stack/…` sotto `audio/`. Stack lo prende
      gratis (render è già `os.walk` ricorsivo, agnostico rispetto al generatore).
    - **Entry point:** `cmd_stack` separato, gemello di `cmd_sweep`, + target make
      `stack`; `all-study: sweep stack render`. Ognuno no-op se il suo blocco
      manca (decisione 7). Nessun accoppiamento tra i due processi.
    - `generated/` è gitignored/rigenerabile → **zero migrazione dati**, basta un
      re-sweep.
    - **Costo:** aggiornare i ~6 join di path in `__main__.py` (describe legge
      `audio/sweep/discrete`, sv `audio/sweep/envelope`) e `render.py`;
      ristringere `_warn_orphans` di `cmd_sweep` a `sweep/` (altrimenti flagga
      `yaml/stack/stack.yml` come orfano). Localizzato.
11. **Modello dei seed (Q2 chiusa) — due manopole globali, cross-cutting.** Il seed
    tocca entrambe le sorgenti di casualità: i generatori di **Y** (`rand`) e le
    **X-strategy stocastiche** (X-rand, decisione 12). Due manopole globali distinte,
    collocate per invariante:
    - **seed-Y in `axes:`** (default per ogni `rand` di Y che non dichiara il suo);
    - **seed-X in `stack:`** (X stocastica è capacità di stack; sweep ha X deterministica).

    Entrambe override-abili per-stream (passano già dal `_deep_merge`). **Precedenza
    (più specifico vince):**
    - Y: `rand.seed` per-asse → `axes.seed` globale (override per-stream) → auto-derivato.
    - X: seed della X-strategy → `stack.seed` globale (override per-stream) → auto-derivato.

    `axes.seed` è **default, non override brutale**: il per-asse vince (Nodo 2). Se un
    seed globale **non** è dichiarato, scatta l'**auto-derivazione per-stream** da
    `hash(stream_id)` (stabile al riordino/rinomina, deterministico): gli stream
    impilati si **decorrelano di default**, senza seedarli a mano. Costo: `hash(stream_id)`
    → int, poche righe.
12. **X-strategy `rand` = emulazione di `rspline` (n-ownership CHIUSA → A).** La X-rand
    genera i **tempi** dei breakpoint da una *frequenza di generazione*, e **possiede `n`**:
    `n` non si dichiara, **emerge** dalla frequenza integrata sulla durata dello stream.
    Questo *è* `rspline` di Csound, non un'approssimazione.
    - **Meccanica (in `[0,1]` normalizzato):** parti da `t=0`, peschi `f₀` nella banda
      `[cpsMin(t),cpsMax(t)]` valutata al punto corrente; il punto dopo cade a
      `t₁=t₀+1/f₀`; ripeti finché superi la fine. `n ≈ ∫ f(t) dt` sulla durata. Banda di
      frequenza alta → punti fitti lì; bassa → radi. La **frequenza è in Hz sulla durata
      reale** (stack la legge da `duration:`), poi i tempi si normalizzano in `[0,1]`.
    - **`base` e `range` inviluppi mobili:** la frequenza ha una base e un range, entrambi
      inviluppi a breakpoint mobili (come Y-rand con min/max), riusando la banda
      `_threshold_at`/`_interp_breakpoints` → **modulo condiviso** Y-rand/X-rand.
    - **Coupling (la regola che rende A fedele a rspline):** quando X possiede `n`, la banda
      della **Y va campionata al tempo reale `t_i`** del punto, non all'indice `i/(n-1)`.
      Y-rand pesca un valore per ogni punto che X ha creato. Y non possiede `n`, segue.
    - **Morbidezza = interp cubica**, già nel motore (`interpolation: cubic`, usata in
      study01). La spline di rspline = cubica sui breakpoint. Zero lavoro nuovo.
    - **Due seed, un bonus su rspline:** rspline pesca X e Y dallo stesso RNG; qui seed-X
      (`stack`) e seed-Y (`axes`) sono distinti → puoi riseedare i tempi senza toccare i
      valori e viceversa.
    - **La separazione Y/X è vocabolario di config, non due clock a runtime.** A runtime un
      asse stocastico ha **un solo proprietario del clock** (la X), e la Y ci si posa. Il
      "disaccoppiamento forte" (due clock indipendenti con `n` diversi) **non produce un
      envelope valido** (`[[t,v]]` pretende tanti `t` quanti `v`): vicolo cieco. In config
      invece puoi mischiare i tipi (`ramp`-Y × `rand`-X, ecc.); rspline è *un* punto in
      questo spazio: `X:rand × Y:rand × interp:cubic`.
    - **Zucchero `rspline:` — RIMANDATO (YAGNI).** Un alias che espande in
      `X:rand × Y:rand × cubic` per non scrivere tre blocchi: prima si prova la forma
      verbosa, poi si valuta.
    - **Conseguenza pratica:** `n` non è noto prima di generare; stream con durata/seed
      diversi ottengono `n` diversi. Va bene: ogni asse è un envelope indipendente. Serve
      una guardia contro frequenze degeneri (banda ~0 → n=0; banda enorme → n runaway):
      dettaglio d'implementazione, non di design.

13. **Stream statici e assi non animati (Q3 chiusa).** Uno stream tutto-fisso (nessun
    asse animato) è **legittimo e di prima classe**: è la voce-drone/pedale sotto quelle
    che si muovono (l'armonia/pedale emerge dalla sovrapposizione). Duplicato esatto del
    base = unisono +6 dB, responsabilità dell'utente, nessuna guardia (come decisione 9).
    Un asse **non animato resta scalare** (numero secco, es. `density: 20`), **non** un
    envelope costante `[[0,v],[1,v]]`. Regola: *sequenza (>1 punto) → envelope; valore
    singolo → scalare*. **Zero codice nuovo:** `build_stream` già wrappa in envelope solo
    i valori-lista e passa gli scalari via `deep_set`; stream misti (alcuni assi envelope,
    altri scalari) e stream tutto-scalare funzionano oggi.

14. **Rimuovere `combine: parallel` da sweep (Q4 chiusa → SÌ, sequenziato).** Sweep
    torna a fare **solo il prodotto cartesiano**, la sua ragione di nascita. Nulla di
    espressivo si perde, per due riproducibilità in stack:
    - **Accoppiamento** (il cuore del parallel): due assi con la **stessa X-strategy e
      stesso `n`** → breakpoint agli stessi `t_i`, valori appaiati per indice. Senza il
      vincolo di ugual lunghezza che `parallel_combinations` impone.
    - **Tenuta del plateau:** la "tenuta" (duplicare il valore nel punto successivo per
      tenerlo fermo) è un comportamento **Y/interpolazione**, non X — è ciò che fa
      `interpolation: step`. In stack lo ricostruisci con valori + X-strategy + step (o
      duplicazione). *Corollario:* plateau/transition è concettualmente una strategy
      y-oriented; non la si estrae ora (decisione 8: resta dentro sweep), ma questo
      conferma che parallel non ha niente che stack non ricrei.
    - **Sequenza (importante):** la rimozione è l'**ultimo passo** dell'implementazione di
      stack, **non il primo**. Rimuovere ora lascerebbe `lettura_avanzata_parallel` e
      `lettura_avanzata_c` senza casa (stack non esiste; cartesian-izzarli esplode 20 →
      20×20=400). Ordine: (1) stack funzionante, (2) migrare i due stream a stack,
      (3) cancellare `parallel_combinations` + campo `combine` + validazione + ramo in
      `combinations_for`. Fino ad allora parallel resta funzionante.

## 4. Decisioni da confermare

Nessuna: tutte confermate (decisione 14 chiude l'ultima). Le questioni di sez. 9
sono tutte risolte.

## 5. Refactor abilitante — plateau/transition da `axes` a `sweep`

Rende esplicito l'invariante (axes = solo Y). Piccolo, non una riscrittura:

- `study_spec.py:37` — `_AXES_RESERVED_KEYS` si restringe da
  `("plateau", "transition", "interpolation")` a `("interpolation",)`.
  `interpolation` resta in axes: è curva di Y, per-asse, non timeline.
- `study_spec.py:226-228` — `plateau`/`transition` si leggono da `sweep_cfg`
  invece che da `axes_raw` (due righe).
- `envelope_sweep.py` — invariato: continua a leggere `spec.plateau`/
  `spec.transition`, che ora arrivano da sweep.
- `studies/study01_grain_density/study.yml` — spostare `plateau`/`transition`
  (righe 32-33) da `axes:` a `sweep:`. Unico file dati da aggiornare.

## 6. Lavoro nuovo per stack (concreto)

1. **Registry strategy-X** — nuovo, gemello di `value_generators.py`. `linear`
   (equispaziato, `t_i = i/(n-1)`) di default. Consumato solo da stack.
2. **Assemblaggio multi-stream** — `yaml_builder.build_document` (`yaml_builder.py:96`)
   oggi hardcoda `streams: [uno]`. Serve mettere N stream mergeati in un documento.
3. **Il processo/comando `stack`** accanto a `cmd_sweep` in `__main__.py`. Riusa
   `resolve_streams` (`study_spec.py:164`) per ottenere tutti gli stream, poi per
   ogni asse di ogni stream risolve i valori (`value_generators.resolve`, già
   esiste) e li posa come envelope via la strategy-X; infine somma tutti gli stream
   in un documento (mute a parte, che è solo `volume` nel base).
4. **Il blocco `stack:` per-stream** cavalca l'override esistente (`_deep_merge`
   in `resolve_streams` lo porta già attraverso): **zero codice di risoluzione
   nuovo**, solo nuovo *consumo*.

## 7. Cosa NON si tocca / si rimanda

- La combinatoria cartesiana di `sweep.py`/`envelope_sweep.py`: intatta (salvo la
  rimozione di `parallel`, decisione 4).
- Per-stream-per-asse con timeline indipendenti oltre l'eredità: escape hatch per
  dopo (uno stream override-a il suo `stack`), il design lascia il posto ma non lo
  costruiamo.
- Sommare fisicamente più stream in un audio unico vs stem separati (STEMS):
  ortogonale, è decisione di assemblaggio/render, non della config `stack`.

## 8. Rapporto col vecchio handoff (mappa vecchio→nuovo)

- **Domanda 4** (Arch.1 vs Arch.2, chi possiede X in `sweep envelope × stack`):
  **dissolta.** Sweep e stack sono processi separati con output diversi; nessuno
  stream ha due proprietari di X. Non si sceglie un'architettura, il conflitto non
  esiste.
- **Q2 → A** (stesso `study.yml`, nuovo dizionario top-level `stack:`):
  **confermata e raffinata.** `stack:` è un blocco top-level come `sweep:`, che fa
  da default e si override-a per-stream via il `_deep_merge` esistente; tutti gli
  stream entrano di default, l'esclusione è via mute engine (decisione 9).
- **Q3 → A** (sweep e stack ortogonali, "attach": per ogni variante sweep si
  attacca lo stesso stack → N documenti × M voci): **RIBALTATA.** Non c'è attach,
  non c'è composizione. Indipendenza totale: `sweep` fa N file, `stack` fa 1 file,
  **mai combinati in un output.** (Il vecchio handoff marcava Q3 "non riaprire": è
  stato riaperto e ribaltato di proposito.)

## 9. Questioni aperte — TUTTE CHIUSE (grilling completato)

1. ~~**Entry point della pipeline.**~~ **CHIUSA → decisione 10.** `cmd_stack`
   separato + target `stack`; `all-study: sweep stack render`; render invariato
   (già ricorsivo); layout `generated/` rinominato per-artefatto/processo
   (`yaml/sweep`, `yaml/stack`, ...).
2. ~~**Seed per-stream con `rand`.**~~ **CHIUSA → decisioni 11-12.** Due seed globali
   (seed-Y in `axes`, seed-X in `stack`), default non-brutale (per-asse vince),
   auto-derivazione per-stream da `hash(stream_id)` in assenza di seed globale.
   Resta da confermare in decisione 12 chi possiede `n` nella X-rand (A vs B).
3. ~~**Stream statico senza assi animati.**~~ **CHIUSA → decisione 13.** Stream
   tutto-fisso legittimo (voce-drone); asse non animato = scalare (numero secco),
   non envelope costante. Zero codice nuovo.
4. ~~**Conferma decisione 4** (rimozione di `parallel` da sweep).~~ **CHIUSA →
   decisione 14.** Sì, rimosso; sweep torna a solo-cartesiano. Sequenziato come
   ultimo passo dell'implementazione stack (migrare i 2 stream, poi cancellare).

## 10. Per la sessione grilling

**Le decisioni della sezione 3 = non riaprire senza motivo. La sezione 4 = da
confermare. Le questioni della sezione 9 = interrogare qui.** Il vecchio handoff è
superato da questo file: se trovi contraddizioni con quello, ignora quello e segui
la sezione 8.
