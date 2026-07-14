# Diario di ascolto — study01_grain_density

Sintesi cronologica delle sessioni di ascolto. Aggiornato dall'AI su richiesta leggendo tutti i log giornalieri.

---

## Temi emergenti

### Pitch come parametro dominante
`density alta + distribution ≈ 0`

Quando la density è alta in banda audio e la distribution è prossima a zero, il parametro percettivo che emerge è l'altezza. La granularità si dissolve: l'orecchio non percepisce più la grana singola ma un suono continuo con pitch definito. Osservato per la prima volta il **2026-06-30**.

### Density come unica altezza, accordi come rapporti di stream
Nessun parametro di pitch dedicato: l'altezza nasce dalla frequenza di emissione dei grani (density). Sotto ~20 Hz si sente come ritmo, sopra come altezza, in mezzo flutter. Armonia e polimetrie nascono dallo stesso gesto — impilare stream con density in rapporto tra loro — letto in banda audio (accordi) o sub-audio (polimetrie). Rapporti semplici = ridondanti/consonanti, rapporti complessi = informativi/ruvidi. Messo a fuoco il **2026-07-01**.

### Zona d'ombra di grain.duration al variare della density
La sensibilità percettiva a un passo fisso di variazione su `grain.duration` non è uniforme: esistono fasce ("zone d'ombra") dove il gradiente percepito è ≈ 0, robuste al punto di lettura del buffer. Mappate su density 5–60 il **2026-07-05**.

### Differenza in Hz tra stream: da battimento a roughness a due toni
Esplorando stack di due soli stream a pochi Hz di differenza (0.1–3 Hz finora), l'asse "differenza in Hz" attraversa più regioni percettive: battimento lento, poi roughness, poi due altezze distinte oltre la banda critica (~20 Hz, variabile con la frequenza centrale). Da mappare lungo tutta la banda, sessione aperta il **2026-07-14** con il nuovo sistema version (stack multi-stem con onset/durata per-stream, export Sonic Visualiser).

---

## Cronologia

| Data | Parametri esplorati | Temi percettivi | Note |
|------|---------------------|-----------------|------|
| 2026-06-30 | density, distribution | pitch, altezza | Alta density + distribution≈0 → emergenza del pitch |
| 2026-07-01 | density, grain.duration (messa a fuoco, no ascolto) | ritmo↔pitch, accordi come rapporti | Vincolo a 2 parametri fissato; drammaturgia rimandata |
| 2026-07-05 | grain.duration × density | zona d'ombra, asimmetria di forma d'onda | Mappate zone d'ombra da density 5 a 60; asimmetria spiegata da fase/pointer fermo |
| 2026-07-14 | Hz di differenza tra due stream (stack a 2 stem) | battimento, roughness, soglia banda critica | Aperta esplorazione sistema version; da estendere a tutta la banda e a valori estremi |
