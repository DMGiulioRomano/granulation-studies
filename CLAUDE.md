# CLAUDE.md — granulation-studies

**Lingua:** rispondi sempre in italiano.

## Stato reale del progetto (leggi prima di toccare qualunque cosa)

L'utente ha curato a mano **solo**: il submodule `engine/`, il proprio
`study.yml`, lo `sweep` e l'`sv export`. È fermo a livello **render**: il suo
ciclo di lavoro attuale è `study.yml → audio → ascolto → modifica study.yml →
rigenera`. Niente oltre.

Tutto il resto — `states.yml`, `composition.yml`, `methodology.md`, e i moduli
`states.py` / `kinship.py` / `walk.py` / `compose.py` / `descriptors.py` /
`curation.py` / `bounds.py` — è stato **generato da un comando Claude e NON è
ancora stato studiato, validato né usato** dall'utente. Trattalo come
scaffolding non vagliato, non come design consolidato: lo schema di `states.yml`
e la semantica della kinship/walk vanno discussi e decisi con l'utente, non dati
per buoni. Conferma di questo: in `make/studies.mk` il target `all-study` è
`sweep render #describe matrix compose render-final` — le fasi describe/matrix/
compose/render-final sono **commentate**, quindi fuori dalla pipeline viva.

Non proporre di "continuare" su quei moduli come se fossero scelte dell'utente.

## Struttura di `studies/`

Il repository **è** lo studio (study01). In futuro diventerà un template da
clonare e rendere agnostico per un nuovo parametro. Le cartelle sotto `studies/`
sono le **scale/varianti** dello stesso studio, più i brani; il diario di
ascolto è unico per tutto lo studio, in `studies/ascolto/`. `STUDY` è il nome
della cartella-scala.

| Cartella | Cos'è | `STUDY=` |
|----------|-------|----------|
| `grain_1-10ms` | scala di riferimento, curata a mano (density + grain.duration 1-10 ms) | `grain_1-10ms` |
| `grain_1-50smp` | grani corti, grain.duration in `samples` (1-50 campioni) | `grain_1-50smp` |
| `grain_50-1000ms` | grani lunghi, grain.duration 50-1000 ms | `grain_50-1000ms` |
| `stack` | stream non-cartesiani (ascolto verticale) | `stack` |
| `brano01` | brano musicale (ex `study_stack_test_5`) | `brano01` |
| `brano01_v2` | versione a 10 min di brano01 (ex `study_stack_test_5_10min`) | `brano01_v2` |
| `ascolto` | diario di ascolto dello studio — non è uno `STUDY` | — |

## Diario di ascolto

Il diario è unico per lo studio e vive in `studies/ascolto/`:

```
studies/ascolto/
├── YYYY-MM-DD.md   ← log della giornata, diario di bordo in prosa
├── index.md        ← sintesi cronologica, aggiornata su richiesta
└── riepilogo.md    ← tabella consolidata regioni/transizioni, aggiornata su richiesta
```

Un solo file per giorno: `YYYY-MM-DD.md`. Se in una giornata ci sono più
sessioni di ascolto, non si creano file separati né suffissi — si aggiungono
come sezioni `## Sessione N — <tema> (scala: grain_1-10ms, sample: ...)` dentro lo
stesso file, in ordine cronologico. La **scala** (`base`/`short`/`long`/`stack`)
e il `sample` stanno nell'heading di sessione, non nel frontmatter.

Il log è **prosa libera**. Nel descrivere un oggetto in ascolto, il filo
ricorrente è: **cosa** si ascolta → **range dove il percetto resta uguale**
(plateau) → **range dove cambia** (transizione) → **plateau successivo**. Così
scrivendo si mappano da sé regioni e transizioni.

### Creare il log di oggi

Quando l'utente dice "crea il log di oggi" o simile:

1. Recupera l'hash con `git rev-parse --short HEAD`
2. Crea `studies/ascolto/YYYY-MM-DD.md` con frontmatter minimo:

```yaml
---
data: YYYY-MM-DD
studio: study01
study_yml_commit: {hash}
---
```

3. Corpo vuoto — lo scrive l'utente in prosa, in sezioni `## Sessione N — <tema>
   (sample: ...)` se la giornata ha più sessioni.

### Aggiornare index e riepilogo

Quando l'utente lo chiede, leggi tutti i log `YYYY-MM-DD.md` e rigenera:
- `index.md` — cronologia + temi emergenti;
- `riepilogo.md` — tabella `sample | tipo | density | grain.dur | percetto`, dove
  `tipo` è `plateau` (range dove resta uguale) o `transizione` (bracket `a→b`
  sull'asse mosso).
