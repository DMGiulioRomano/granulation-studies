# granulation-studies

Ciclo di studi compositivi sui parametri dell'elaborazione granulare.

Framework di **ricerca compositiva** sopra
[PythonGranularEngine](https://github.com/DMGiulioRomano/PythonGranularEngine)
(incluso come git submodule in `engine/`). Permette di esplorare metodicamente
lo spazio dei parametri del motore granulare, curare i risultati interessanti,
organizzarli in *stati* con una loro dinamica, e comporre brani come percorsi tra
quegli stati — il tutto producendo YAML che l'engine compila in audio.

## Pipeline

```
study.yml ──sweep────▶ yaml/sweep/*.yml ───────────┬─render──▶ audio + partitura
          ──stack────▶ yaml/stack/stack.yml ───────┤       │
          ──versions─▶ yaml/versions/versions.yml ─┤       │
          ──percorso─▶ yaml/percorso/percorso.yml ─┘       │
                              (ascolto + tag manuali)
                                          ▼
                                     results.yml ──┐
                                                   ▼
                                     states.yml ──matrix──▶ kinship.json
                                          │
                  composition.yml ──compose──▶ final.yml ──render──▶ brano
```

Vedi `docs/methodology.md` per il modello concettuale completo e i formati file.

## Avvio rapido

```bash
make setup                              # venv + submodule + dipendenze
# metti un file audio in samples/ (es. corpus.wav, vedi samples/README.md)
make sweep   STUDY=grain_1-10ms
make stack   STUDY=grain_1-10ms
make render  STUDY=grain_1-10ms
make describe STUDY=grain_1-10ms
# cura generated/base/results.yml (kept/tags), poi compila states.yml
make matrix  STUDY=grain_1-10ms
make compose STUDY=grain_1-10ms
make render-final STUDY=grain_1-10ms
```

## Struttura

- `src/granstudies/` — il pacchetto (uno stadio per modulo).
- `studies/<id>/` — input versionati: `study.yml`, `states.yml`, `composition.yml`.
- `generated/<id>/` — output rigenerabile (git-ignorato).
- `samples/` — corpus audio (file git-ignorati, solo manifest versionato).
- `engine/` — submodule del motore (pin su commit).
- `tests/` — suite pytest (mirror di `src/`).

## Test

```bash
make tests        # gate obbligatorio prima di ogni commit
```
