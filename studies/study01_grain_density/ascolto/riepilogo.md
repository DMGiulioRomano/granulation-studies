# Riepilogo — study01

Consolida i log giornalieri (`YYYY-MM-DD.md`) in regioni e transizioni.
Aggiornato su richiesta leggendo i log.

- **plateau** = range dove il percetto resta uguale (`density`/`grain.dur` come range)
- **transizione** = range dove cambia (bracket `a→b` sull'asse mosso)
- le frontiere si spostano col `sample`: sempre indicato

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

Nota: dal 2026-07-14 si esplora un asse diverso — la differenza in Hz tra due
stream in uno stack (battimento/roughness/soglia banda critica) — non ancora
ridotto a plateau/transizioni: la sessione ha solo elencato i valori provati
(0.1, 0.5, 1, 2, 3 Hz) senza annotare il percetto per ciascuno. Da completare,
poi riportare qui con una colonna `Hz differenza` al posto di `grain.dur`.
