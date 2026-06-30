# CLAUDE.md — granulation-studies

**Lingua:** rispondi sempre in italiano.

## Diario di ascolto

Ogni studio ha una cartella `ascolto/` dentro la sua directory:

```
studies/{studio_id}/ascolto/
├── YYYY-MM-DD.md   ← log della sessione (uno per giorno)
└── index.md        ← sintesi cronologica, aggiornata su richiesta
```

### Creare il log di oggi

Quando l'utente dice "crea il log di oggi" o simile:

1. Recupera l'hash corrente con `git rev-parse --short HEAD`
2. Crea `studies/{studio_id}/ascolto/YYYY-MM-DD.md` con questo frontmatter:

```yaml
---
data: YYYY-MM-DD
studio: {studio_id}
study_yml_commit: {hash}
parametri_esplorati: []
temi_percettivi: []
sample:
durata_sessione:
---
```

3. Lascia il corpo vuoto o con un placeholder — è l'utente che scrive le osservazioni.

### Aggiornare l'index

Quando l'utente dice "aggiorna l'index": leggi tutti i log `YYYY-MM-DD.md` della cartella, rielabora `index.md` aggiornando la tabella cronologica e la sezione temi emergenti.
