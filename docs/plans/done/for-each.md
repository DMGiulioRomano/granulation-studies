# `for_each:` — un asse che moltiplica i file, non i gradini

Portato da mare-nostrum (piano concordato con l'utente il 2026-09-08,
`docs/plans/done/for-each.md` di quel repo; commit
DMGiulioRomano/mare-nostrum@abc81d8, @b3aebe3, @b8b9022, @bdf195e, @811781d,
più @c86b6ce per `sv`). Issue di questo repo: #74.

Là `for_each:` sostituiva la **modalità take** (`TAKE=true`, cartelle a data in
`takes/`), che veniva rimossa. Qui la modalità take non è mai esistita: del
piano originale resta la parte che costruisce, non quella che toglie. Le
sezioni sotto sono quelle del piano, con i riferimenti alle take tolti o
spiegati.

## Il problema

Gli `axes:` di uno studio sono assi **interni**: scorrono nel tempo dentro lo
stesso file. Ogni asse in più moltiplica i plateau: aggiungere `distribution`
come terzo asse a uno sweep `density × grain.duration` triplicherebbe la durata
di un file già lungo, e il confronto fra `distribution: 0` e `distribution: 1`
finirebbe a minuti di distanza dentro lo stesso ascolto.

Ma il confronto che serve è: **lo stesso sweep, rifatto per intero con quel
parametro diverso**. N valori, N file, ognuno percorre gli stessi assi.

## La forma della soluzione

Un blocco top-level `for_each:`, con la **grammatica di `versions:`** (assi
ortogonali, prodotto cartesiano lessicografico nell'ordine di dichiarazione),
ma il prodotto si materializza in **file separati** invece che nel tempo.

Ogni combinazione è una **patch sullo `study.yml`**: chiavi = path puntati su
tutto il documento, non solo su `base:`. Il documento patchato è quello che
tutti i processi leggono, quindi `for_each` vale per sweep, stack, versions e
percorso senza toccarne nessuno.

```yaml
for_each:
  base.distribution: {values: [0, 0.5, 1]}   # asse a manopola singola
  griglia:                                    # stati nominati, per override non scalari
    fitta: {axes.grain.duration.values: [0.001, 0.002, 0.005, 0.01]}
    rada:  {axes.grain.duration.values: [0.001, 0.01]}
```

→ 3 × 2 = 6 render in `generated/<study>/<combo>/`, con `<combo>` =
`distribution=0.5__griglia=rada`.

### Perché serve anche fuori dallo sweep

Ci sono chiavi che **non possono** essere assi interni, per costruzione:

- **stack** — le camminate-X sono stocastiche (`seed`, `range`, `drift`).
  Ascoltare cinque realizzazioni dello stesso impasto è cinque file, mai uno:
  `for_each: {stack.seed: {values: [1, 2, 3, 4, 5]}}`.
- **percorso** — idem per `seed`/`drift`, più `arco:` e `passo:`: la timeline
  *è* il file, quindi «la stessa legge distesa su 90, 180, 360 secondi» esiste
  solo come asse esterno.
- **versions** — valvola di sfogo del cartesiano interno: `grana × densita` = 16
  versioni concatenate, una terza variabile porta a 48 e il file diventa
  inascoltabile. La si sposta fuori e si ottengono N file da 16.

Il criterio, che è anche la riga di doc del blocco:

> Interno se il confronto sta nella **giustapposizione** (lo senti cambiare
> mentre suona). Esterno se sta nel **riascolto** (devi risentire la stessa cosa
> da capo), o se la chiave definisce il file stesso — `seed`, `sample`, `arco`,
> la durata.

### Naming delle cartelle

- Valore **scalare** → `chiave=valore`, sanificato (`[^A-Za-z0-9._-]` → `_`),
  senza il prefisso di sezione (`base.`, `axes.`) né il nome del generatore in
  coda (`.values`).
- Qualunque altra cosa (lista, dict, breakpoint, banda) → l'asse **deve** essere
  a stati nominati: il nome lo dà l'utente. Niente indici anonimi `d0/ d1/`: un
  nome di cartella che non dice cosa contiene non serve a niente.
- `for_each` assente = una combinazione vuota = `generated/<study>/` piatto,
  identico a prima. È il caso degenere, non un ramo speciale.

### Combinazioni orfane

Togliere un valore da `for_each` lascia la sua cartella con dentro l'audio
vecchio. Stesso trattamento delle varianti orfane dello sweep
(`_warn_orphans`): **avviso, nessuna cancellazione**. Una combinazione orfana è
spesso proprio quella che si vuole tenere — il «prima» da riascoltare.

## L'interfaccia

```zsh
study 1-10ms                                   # rigenera e apre TUTTE le combinazioni
COMBO=distribution=1 study 1-10ms              # solo la fetta a distribution 1
COMBO=griglia=rada__distribution=0.5 study ... # l'intersezione di due vincoli
make where STUDY=1-10ms                        # stampa le root, una per riga
```

`COMBO` è un filtro di sessione, non un interruttore di modalità: senza, si fa
tutto. I vincoli sono **segmenti di label**, separati da `__` e in and fra loro;
il match è per segmento intero (`distribution=0` non prende
`distribution=0.5`). Serve a due cose che sono la stessa: non rirenderizzare
decine di varianti per sentirne una, e non aprire decine di sessioni di Sonic
Visualiser insieme.

Il render resta incrementale per mtime dentro ogni combinazione, quindi
rigenerare tutto dopo una modifica che tocca una sola combo costa poco.

## Cosa si tocca

| File | Modifica |
|---|---|
| `src/granstudies/for_each.py` (nuovo) | Parse del blocco, prodotto cartesiano, label della combinazione, patch del documento. Funzione pura: nessun I/O, così gl-ls può consumarla. |
| `src/granstudies/__main__.py` | Due choke point e un loop. `gen_dir()` appende il segmento-combo; `_read_study()` è l'unico punto che legge `study.yml` e applica la patch (`_load_data`, `_load_specs`, `cmd_versions`, `cmd_percorso` passano da lì). Il loop sta in `_dispatch`: ogni comando gira N volte con il contesto-combo impostato, e i `cmd_*` non si toccano. `sv_combo_suffix()` per i `.sv`, `cmd_where`, lo snapshot dello `study.yml` patchato a fine render. |
| `make/studies.mk` | Target `where` (qui nuovo: in mare-nostrum esisteva già per le take). `sv` non dipende più da `render`. |
| `.zsh_completions/_study` | `study` interroga `make where` invece di costruirsi `generated/<s>/`, e apre i `.sv` di tutte le root. |
| `docs/study-yml-reference.md`, `README.md`, `CLAUDE.md` | Sezione `for_each:`; il livello in più nel layout di `generated/`; `make where` e `COMBO` fra i comandi. |
| `tests/test_for_each.py`, `tests/e2e/test_for_each_e2e.py` | Portati i test di mare-nostrum; in più i casi elencati sotto e un e2e col render vero. |

## Deviazioni dal piano di mare-nostrum

Le due emerse implementando là (restano per storia, qui non si applicano):
`/takes/` restava nel `.gitignore` perché la cartella era ancora sul disco, e
lo sgancio dell'hardlink in `render.py`/`sv_export.py` è diventato codice
morto. Nessuna delle due cose è mai esistita in questo repo.

Quelle di questo porting:

- **Nomi d'asse dotted.** In mare-nostrum il path della patch si spezzava su
  ogni punto: `axes.fill_factor.values` funzionava, `axes.grain.duration.values`
  no (cercava un asse `grain`). Qui `grain.duration` è l'asse di quasi ogni
  scala, quindi `_set_path` risolve a ogni livello la chiave che il documento ha
  davvero fra i prefissi del resto del path; due prefissi presenti insieme sono
  un errore di ambiguità, come per le chiavi puntate di `streams:`.
- **Path annidati fra assi diversi.** Due assi su `base.grain` e
  `base.grain.duration` sono errore come due assi sullo stesso path: il valore
  si assegna, quindi quello finale dipenderebbe dall'ordine.
- **L'avviso sulle combinazioni orfane c'è.** Il piano e la doc di mare-nostrum
  lo promettevano, il codice no. Qui `_warn_orphan_combos` gira una volta per
  `render`, confronta con tutte le combinazioni dichiarate (non con la fetta di
  `COMBO`) e segnala anche l'albero piatto rimasto da prima di `for_each:`.
- **Il rimedio di `COMBO` elenca le combinazioni a virgole**, non a capo: il
  blocco d'errore rimpagina il rimedio con `textwrap.fill`, che fonde gli a-capo
  e incollava le label. L'errore porta anche la riga del blocco `for_each:`.
- **Lo snapshot `study.yml`** in mare-nostrum c'era già (lo scriveva la
  modalità take); qui è nuovo, e c'è anche nell'albero piatto: il render lo
  scrive per ogni combinazione, vuota compresa.

## Impatto su gl-ls

Il blocco è sintassi nuova osservabile nello `study.yml`: chiave top-level
`for_each:`, path puntati come chiavi (forma che nessun altro blocco usa),
regola «non-scalare → stato nominato obbligatorio», le guardie su etichette e
path, e il rifiuto dei path che non esistono nel documento. Issue aperta su
`DMGiulioRomano/gl-ls` (regola `.claude/rules/gl-ls-impact.md`).

## Scartato

- **`scope: file` come flag sull'asse** (`axes: {distribution: {values: [...],
  scope: file}}`): diff minimo, ma un asse che non scorre nel tempo non è un
  asse — andrebbe escluso dagli `orderings`, ignorerebbe `interpolation`, e ogni
  regola sugli assi acquisterebbe un'eccezione.
- **`for_each` dentro `sweep:`**: vero che è lo sweep a essere moltiplicato, ma
  lo legherebbe a un processo solo — stack, versions e percorso ne hanno
  bisogno quanto lui.
- **La modalità take** di mare-nostrum: là è stata sostituita da `for_each` e
  rimossa, qui non va portata.
- **Cancellazione automatica delle combinazioni orfane**: vedi sopra.
