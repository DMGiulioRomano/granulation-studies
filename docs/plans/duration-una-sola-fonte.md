# `duration`: una sola fonte, e che dica la verità — documento di design

Discussione del 2026-07-29, nata da un caso concreto: in `stack_1-50smp` tre
gruppi (`fratelli`/`cugini`/`cugini_old`) occupano 0-50, 50-100, 100-150 sulla
stessa timeline, e per farli concatenare senza sovrapposizioni si è dovuto
scrivere `duration: 150` in testa al documento — un numero che non è la durata
di niente. Il documento generato dura 3600 s.

Ogni affermazione sul comportamento attuale è marcata **[eseguito]** (verificata
lanciando il codice o ispezionando lo YAML generato) o **[dedotto]** (letta nel
sorgente, non eseguita).

Prerequisito di lettura: `docs/plans/done/duration-onset-override.md` (issue
#26), che ha introdotto l'override per-stream e le chiavi riservate di
`versions:`. Questo documento non lo contraddice: ne completa un pezzo rimasto
a metà.

---

## Il problema in una riga

Il `duration:` top-level si chiama "durata del documento" e **non lo è mai**.

## I tre sintomi

1. **La durata del documento è sempre dedotta, mai dichiarata.** [eseguito]
   - stack: `duration = max(onset + duration)` sugli stream — `stack.py:203`
   - versions: idem — `versions.py:640`
   - percorso: idem — `percorso.py:741`
   - envelope sweep: `N*plateau + (N-1)*transition`, e `spec.duration` non
     viene proprio guardata — `envelope_sweep.py:165-177`

   L'unico ramo in cui `spec.duration` finisce davvero come durata di un
   documento è **discrete** (`sweep.py:52`): file statici, senza envelope, dove
   non c'è niente da cui dedurla. E lì `render.py:54` la chiama già
   `base.duration`.

2. **`base.duration` è una trappola silenziosa nel ramo `streams:`.**
   `stack.py:134` fa `base["duration"] = spec.duration` senza guardare cosa
   c'era: una `base: {duration: 50}` scritta dentro una entry non fa nulla e
   non avvisa. [eseguito — è esattamente l'errore commesso scrivendo i
   `fratelli`, scoperto solo portando il top-level da 50 a 100]

   Non è ipotetico: `studies/stack/study.yml:18` ha `base: {duration: 6}`
   accanto a `duration: 30` top-level. [eseguito: presenza verificata;
   **[dedotto]** che sia inerte — da controllare in fase di migrazione, quel
   file mescola `sweep:` e `streams:`]

3. **La stessa chiave significa cose diverse in rami diversi.**
   `base.duration` = "durata dei file discrete" in un ramo (`render.py:54`,
   con tanto di warning dedicato), inerte nell'altro.

## La causa

Il top-level `duration:` fa **due lavori**, nessuno dei quali è quello che il
nome promette:

- **default della durata di stream**, ereditato da chi non ne dichiara una;
- **passo di concatenazione di `versions:`**, come fallback quando
  `versions.duration` manca (`versions.py:576-582`).

Il secondo è quello che ha prodotto il numero-bugia: `duration: 150` non
descrive né il documento né uno stream, descrive il passo della griglia.

---

## Il disegno proposto

Ogni `duration` sta accanto alla cosa di cui è la durata.

| Cos'è | Dove si scrive | Chi la legge |
|---|---|---|
| durata di **uno stream** (default di documento) | `base: {duration: N}` | tutti i rami |
| durata di **uno stream** (override) | `duration:` di entry | `stack.py` |
| durata di una **versione** | `versions: {duration: N}` | `versions.py` |
| durata di una **istanza** di percorso | `percorso: {duration: ...}` | `percorso.py` (già così) |
| durata del **documento** | non si scrive | dedotta, `max(onset + duration)` |

Simmetrico con `onset`, che già funziona così: `base.onset` è il default di
documento (il top-level è vietato per scelta, `study_spec.py:470`), `onset:` di
entry è l'override.

Il top-level `duration:` non ha più un lavoro e sparisce.

**`percorso:` è il precedente che regge la proposta**: ha già la sua `duration`
dentro il proprio blocco, con unit propria (`percorso.py:173-196`). `versions:`
farebbe lo stesso, e `base:` farebbe quello che già fa per `onset`.

---

## Le decisioni da prendere PRIMA di scrivere codice

Nessuna di queste è ovvia. Non vanno decise dall'implementazione.

**D1 — `versions.duration` scalare.** Oggi pretende un generatore
(`values`/`ramp`/banda) e rifiuta lo scalare: `versions: {duration: 100}` dà
`'duration' deve avere un generatore (dict), trovato 100`. [eseguito] Va fatta
accettare uno scalare broadcastato sulle N versioni — è il caso di gran lunga
più comune e oggi è l'unico che non si può scrivere.

**D2 — `versions.duration` fa anch'essa doppio lavoro.** È il passo *e* viene
iniettata come `duration:` del documento della versione (`versions.py:595`),
cioè come default per i suoi stream. Stessa conflazione, un livello più in
basso. Tre opzioni:
  - (a) lasciarla doppia — una versione è un contenitore, ha senso che detti la
    durata di default di chi ci sta dentro;
  - (b) renderla solo passo, e i default degli stream vengono da `base.duration`;
  - (c) due chiavi separate.

  La (a) è la meno invasiva e probabilmente la giusta, ma va detto
  esplicitamente, perché è la stessa ambiguità che stiamo togliendo sopra.

**D3 — deprecazione o rimozione del top-level `duration:`.** Con warning per
una release, o errore secco con messaggio che indica dove spostarla? Sono 14
studi, tutti tuoi, nessun consumatore esterno: l'errore secco è praticabile e
si migra in un pomeriggio.

**D4 — `onset` top-level resta vietato?** Il divieto (`study_spec.py:470`,
"un onset globale che sposta tutti gli stream insieme è ambiguo") è coerente
con `base.onset` come default. Confermare, o riaprirlo insieme al resto.

**D5 — il ramo discrete.** Lì `base.duration` è già la chiave giusta e
`spec.duration` è già la durata reale del documento prodotto. Confermare che
resta com'è e che l'unico cambio è la **fonte** di `spec.duration`
(`base.duration` invece del top-level).

---

## Fasi

### Fase 1 — `study_spec.py`: la fonte di `spec.duration`

Test (`tests/test_study_spec.py`):
- documento con `base: {duration: N}` e nessun `duration:` top-level →
  `spec.duration == N` per ogni stream che non ne dichiara una propria;
- entry con `duration:` propria → vince su `base.duration`;
- nessuna delle due → `spec.duration is None`, e l'errore "stack: lo stream non
  risolve nessuna duration" (`study_spec.py:791`) scatta col messaggio
  aggiornato che indica `base.duration`;
- validazioni `> 0` e di tipo, oggi su `data["duration"]`
  (`study_spec.py:669-676`), spostate/duplicate su `base.duration`;
- (secondo D3) `duration:` top-level → warning o errore con rimedio esplicito.

Implementazione: `parse_study_spec` legge la duration da
`data["base"]["duration"]` con fallback al top-level fino alla rimozione.
Attenzione: dopo il merge la entry *diventa* il documento, quindi la catena
entry > base va risolta sul documento merged, come già fa `onset`.

### Fase 2 — `stack.py`: smettere di sovrascrivere

Test (`tests/test_stack.py`):
- `base.duration` di entry sopravvive alla costruzione dello stream;
- `duration:` di entry vince su `base.duration`;
- durata documento invariata: `max(onset + duration)`.

Implementazione: `stack.py:134` diventa condizionale, come già è la riga
gemella per `onset` (`stack.py:135-137`). È il fix del sintomo 2.

### Fase 3 — `versions.py`: passo esplicito

Test (`tests/test_versions.py`):
- `versions: {duration: 100}` scalare → N versioni concatenate a passo 100
  (oggi errore);
- generatore invariato (retrocompatibilità della forma esistente);
- senza `versions.duration` e senza top-level → errore che dice dove scriverla;
- (secondo D2) se la (b): `versions.duration` non viene più iniettata come
  `duration:` del documento della versione.

Implementazione: `_resolve_reserved` accetta lo scalare e lo broadcasta su N;
il messaggio di `versions.py:566-573` va riscritto (oggi suggerisce
`'duration:' top-level`, che dopo non esisterà).

### Fase 4 — migrazione dei 14 studi

[eseguito] Inventario: **tutti e 14** dichiarano `duration:` top-level e
`base.onset`; **nessuno** ha `base.duration` tranne `stack` (che ha entrambi);
solo `stack_1-50smp` usa `duration:` di entry; 6 usano `versions:`.

- 7 studi sweep/envelope (`1-10ms`, `1-50smp`, `10-50ms`, `50-300ms`,
  `300-1000ms`, `brano01`, `brano01_v2`): `duration: 30` → dentro `base:`.
  Meccanico.
- 6 studi stack con `versions:` (`stack_1-10ms`, `stack_10-50ms`,
  `stack_50-300ms`, `stack_100-300ms`, `stack_300-1000ms`, `stack_1-50smp`):
  il top-level si scinde in `base.duration` (durata dello stream) +
  `versions.duration` (passo). Per i cinque gemelli i due numeri coincidono
  (50 e 50); per `stack_1-50smp` no ed è il caso interessante: 50 e 150.
- `stack`: da ispezionare a mano, è l'unico che mescola `sweep:` e `streams:`
  e l'unico che ha già una `base.duration`.

Ogni studio va rigenerato e **diffato contro il documento prodotto prima della
migrazione**: il target è zero differenze nell'audio. Il `.sv` è il modo più
rapido per accorgersi di uno slittamento.

### Fase 5 — documentazione

- `docs/study-yml-reference.md`: la tabella delle quattro `duration`;
- docstring di `stack.py`, `versions.py`, `study_spec.py` (parlano tutte del
  `duration:` top-level come default);
- `CLAUDE.md` di progetto se la regola merita di stare lì.

---

## Rischi

- **Slittamenti silenziosi.** Uno studio migrato male non esplode: produce
  audio di durata diversa. La difesa è il diff dei documenti generati, fase 4,
  non i test unitari.
- **`sv_export`** ha `doc.get("duration", 1.0)` come fallback in quattro punti
  (`sv_export.py:435,470,716,729`). [dedotto] Il documento generato continuerà
  ad avere il suo `duration:` calcolato, quindi non dovrebbe cambiare nulla —
  ma è il posto dove un fallback a `1.0` maschererebbe un bug.
- **`gainmap.py:199`** calcola le finestre di sovrapposizione da
  `onset + duration` per-stream. Non cambia, ma dipende dal fatto che ogni
  stream *abbia* una duration risolta: la fase 1 non deve poter produrre
  `None` silenziosi.
- **La cache degli stem** è per-stream: cambiare la fonte della duration senza
  cambiarne il valore non deve invalidare nulla. Da verificare, non da
  assumere.

## Impatto cross-repo

**Scatta `.claude/rules/gl-ls-impact.md`**: questo cambia la sintassi
osservabile dello `study.yml`. A fine lavoro serve una issue su
`DMGiulioRomano/gl-ls`, previa conferma, che copra: `base.duration` diventa
significativa nel ramo `streams:`; `versions.duration` accetta uno scalare;
il `duration:` top-level è deprecato/rimosso; la catena di precedenza
entry > `base` per `duration` e `onset`.

Nessun impatto su PGE: il documento engine prodotto continua ad avere
`onset`/`duration` per-stream e `duration:` di documento, che è quello che
l'engine richiede (`engine/docs/reference/yaml.md:197-205`).

## Fuori scope

- La discussione sui rapporti armonici di density (`(x+i)/x`) — è materiale
  musicale, non tocca questo.
- `percorso.duration`: già coerente, non si tocca.
- Il ramo discrete: cambia la fonte, non la semantica (D5).
