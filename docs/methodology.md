# Metodologia

Questo documento descrive il modello concettuale del framework e i formati dei
file usati a ogni stadio. L'obiettivo e' rendere la ricerca compositiva
**riproducibile e ispezionabile**: ogni trasformazione legge e scrive file di
testo versionabili.

## La pipeline a stadi

```
study.yml ──sweep──▶ varianti/discrete/*.yml ──render──▶ audio + partitura
                     varianti/envelope/*.yml ──┘    │
                                                    ▼
                                              descriptors (results.yml)
                                                    │
                                        (ascolto + tag manuali)
                                                    ▼
                                               states.yml ──matrix──▶ kinship.json
                                                    │
                            composition.yml ──compose──▶ final.yml ──render──▶ brano
```

### 1. Studio (`studies/<id>/study.yml`)

Si sceglie un **gruppo di parametri** (gli *assi*) e, per ciascuno, un valore di
*baseline* e una lista di *valori di test*. Tutto il resto dello stream e' fisso
nel blocco `base`.

Il `baseline` puo' essere **omesso** se l'engine definisce un default per quel
path: in quel caso viene risolto automaticamente dal registry dell'engine. I path
`pitch.*` (unit-driven, nessun default) e i parametri con `default: null`
(es. `density`) richiedono un baseline esplicito.

I valori di test si danno con **una** chiave-generatore per asse tra `values`
(lista esplicita), `ramp` (rampa aritmetica) e `rand` (banda casuale seeded).
Sintassi e forme di banda: vedi `study-yml-reference.md`.

### 2. Sweep (OAT → fattoriale)

`sweep` supporta tre modalita', scelte via `sweep.mode` in `study.yml`:

- `discrete` (default) — un file YAML statico per combinazione, scritti in
  `varianti/discrete/`;
- `envelope` — un file per combinazione di assi, in cui i parametri attraversano
  tutti i valori in sequenza tramite breakpoint temporali sincronizzati, scritti
  in `varianti/envelope/`;
- `both` — entrambe le sotto-cartelle.

In tutte le modalita' gli assi vengono mossi a **ordini crescenti**:

- ordine 1 (OAT, *one-at-a-time*): un asse alla volta, gli altri alla baseline;
- ordine 2: tutte le coppie di assi;
- ordine 3: tutte le terzine;
- ordine 4: il fattoriale completo.

**Modalita' `discrete`**: ogni variante e' completamente specificata (tutti gli
assi hanno un valore scalare), quindi le varianti sono direttamente
confrontabili. Il numero di varianti per N assi con v valori ciascuno e'
`1 + Σ_k C(N,k)·v^k` (la baseline piu' le combinazioni).

**Modalita' `envelope`**: un file per combinazione di *k* assi, in cui quei *k*
assi attraversano i loro valori in ordine lessicografico. Con
`sweep.combine: cartesian` (default) si prende il **prodotto cartesiano** dei
valori; con `sweep.combine: parallel` gli assi si muovono **insieme** (zip: il
plateau *i* usa l'*i*-esimo valore di ogni asse, richiede assi di ugual
lunghezza). Ogni valore occupa un *plateau* (ascolto stabile) e il passaggio al successivo
avviene tramite una *transition* lineare. I tempi sono normalizzati in `[0, 1]`
(`time_mode: normalized`); la durata reale dello stream e' `N·plateau + (N-1)·transition`.
I parametri `plateau` e `transition` (in secondi, default 5.0) si impostano
sotto `axes:` in `study.yml` come chiavi riservate.

I valori fuori dai bounds dell'engine vengono *clampati* in entrambe le modalita'.

### 3. Render

`render` compila ogni variante in audio (renderer NumPy) e in una partitura PDF.
L'audio finisce in `generated/<id>/audio/discrete/` o `audio/envelope/` a seconda
della modalita'; le partiture in `score/discrete/` o `score/envelope/`.
Con `mode: both` entrambe le sotto-cartelle sono popolate.

### 4. Descrittori + curation (`generated/<id>/results.yml`)

`describe` calcola descrittori audio elementari (RMS, picco, crest factor, zero
crossing rate, centroide spettrale, *active ratio*) e li unisce in `results.yml`,
una riga per variante. L'utente **ascolta** e annota a mano i campi:

- `kept`: `true`/`false`/`null` (interessante o no);
- `tags`: etichette soggettive (es. `denso`, `acuto`, `statico`);
- `notes`: testo libero.

Il merge e' idempotente: rieseguire `describe` aggiorna i descrittori senza
perdere le annotazioni.

### 5. Stati (`studies/<id>/states.yml`)

Le varianti tenute diventano **stati**: un punto nello spazio parametri piu' una
dinamica temporale.

```yaml
- id: grani_radi
  params: {density: 5, grain.duration: 0.2, pitch.semitones: 0, distribution: 1.0}
  dwell: [4, 10]            # permanenza min/max in secondi
  transition_speed: 3.0     # secondi per migrare verso il prossimo stato
  tags: [sparso, lento]     # alimentano la similarity
  # parents/children: opzionali; se omessi, derivati dalla kinship
```

### 6. Matrice di parentela (`generated/<id>/kinship.json`)

`matrix` calcola la **similarity** fra ogni coppia di stati come combinazione
pesata di:

- distanza nello spazio parametri (normalizzata sui bounds dell'engine);
- distanza nei descrittori audio (se presenti);
- complemento dell'overlap dei tag (Jaccard).

Da una **soglia** si derivano gli archi del grafo (chi e' abbastanza simile da
poter essere genitore/figlio). Gli stati possono comunque imporre archi
espliciti via `children`.

### 7. Composizione (`composition.yml` → `final.yml`)

`compose` genera un **percorso** fra stati:

- `mode: walk` — random-walk *seedabile* sul grafo (riproducibile);
- `mode: path` — percorso autoriale esplicito.

Ogni tappa tiene lo stato per il suo `dwell`, poi migra al successivo
interpolando i parametri lungo la `transition`. I valori nel tempo diventano
**envelope** a breakpoint `[[t, v], ...]` in `time_mode: absolute`. Il risultato
e' `final.yml`, un singolo stream che l'engine compila in audio con
`render-final`.

## Riproducibilita'

- Il submodule `engine/` e' pinnato a un commit: gli studi girano sempre sullo
  stesso motore finche' non lo si bumpa esplicitamente.
- Lo `study.yml` e la `composition.yml` portano un `seed`: a parita' di seed,
  sweep e random-walk producono lo stesso risultato.
