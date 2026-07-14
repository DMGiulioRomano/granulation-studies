# Riepilogo — study01

Consolida i log giornalieri (`YYYY-MM-DD.md`) in regioni e transizioni.
Aggiornato su richiesta leggendo i log.

- **plateau** = range dove il percetto resta uguale (`density`/`grain.dur` come range)
- **transizione** = range dove cambia (bracket `a→b` sull'asse mosso)
- le frontiere si spostano col `sample`: sempre indicato

## Ascolto a uno stream

Un solo stream, si ascolta la modifica di un solo parametro su di esso
(`density` assoluta, `grain.dur`).

| sample | tipo | density | grain.dur | percetto |
|--------|------|---------|-----------|----------|
| lettura_avanzata_* | plateau | 5 | 0.0035–0.005 | zona d'ombra (poca differenza percepita) |
| lettura_avanzata_* | transizione | 5 | 0.001→0.0035 | ogni passo di 0.00025 si sente |
| lettura_avanzata_* | plateau | 10 | 0.00375–0.00475 | zona d'ombra |
| lettura_avanzata_* | plateau | 15 | 0.00325–0.00425 e 0.0045–0.0055 | zona d'ombra (due fasce) |
| lettura_avanzata_* | plateau | 20 | 0.00325–0.0045 | zona d'ombra |
| lettura_avanzata_* | plateau | 25 | 0.00325–0.00475 | zona d'ombra |
| lettura_avanzata_* | plateau | 30 | 0.00325–0.00475 | zona d'ombra |
| lettura_avanzata_* | plateau | 35 | 0.003–0.005 | zona d'ombra |
| lettura_avanzata_* | plateau | 40 | 0.00325–0.00475 | zona d'ombra |
| lettura_avanzata_* | plateau | 45 | 0.003–0.00475 | zona d'ombra |
| lettura_avanzata_* | plateau | 50 | 0.003–0.005 | zona d'ombra |
| lettura_avanzata_* | plateau | 55 | 0.003–0.00775 | zona d'ombra, forse oltre (da verificare 0.008–0.01) |
| lettura_avanzata_* | plateau | 60 | 0.003–0.00775 | zona d'ombra (= density 55) |

## Ascolto a due stream in stack (delta tra stream)

Due stream suonano verticalmente insieme; l'asse mosso non è il valore
assoluto di un parametro ma il **delta** dello stesso parametro tra i due
stream. Strumento: `versions` (sample `study_versions_test`), che permette
di stackare stem con onset/durata per-stream.

Nota: dal 2026-07-14 si esplora un primo asse così — la differenza in Hz tra
i due stream (battimento/roughness/soglia banda critica) — non ancora
ridotto a plateau/transizioni: la sessione ha solo elencato i valori provati
(0.1, 0.5, 1, 2, 3 Hz) senza annotare il percetto per ciascuno. Da completare,
poi riportare qui con una colonna `Δ Hz`.

Un secondo asse, sempre dal 2026-07-14 (sample `study_versions_test`): la
differenza di **density** tra i due stream in stack (non densità assoluta),
nel range density 30–50 Hz.

| sample | tipo | density (range) | Δdensity | percetto |
|--------|------|------------------|----------|----------|
| study_versions_test | plateau | 30–50 | 0.01–0.1 | percetto stabile: nessun battimento interno, solo lieve spostamento del peso spettrale (es. più/meno nasalità) |
| study_versions_test | transizione | 30–50 | 0.1→1 | compare battimento interno percepibile; punto esatto di soglia non ancora individuato |
