# Promemoria — cose rimaste da fare

Cose che vengono in mente durante le sessioni ma non si fanno subito. Quando
una voce è fatta, si sposta in fondo sotto `## Fatto` con la data, non si
cancella.

## Da fare

- [ ] Riascoltare le 4 zone d'ombra compartimentate (stream `zona_ombra_d05`,
  `zona_ombra_d10_20`, `zona_ombra_d25_50`, `zona_ombra_d55_60` — study.yml:66-105)
  con i 7 cugini pointer.start (indice→secondi: 1=0.1 2=0.25 3=0.4 4=0.55 5=0.8
  6=0.915 7=1.1), sostituiscono la mappa precedente in `riepilogo.md`. In
  particolare per `zona_ombra_d55_60` verificare l'estensione grain.dur fino a
  0.008 (prima non coperta, segnalata come "da verificare" nel vecchio riepilogo).
- [ ] `zona_ombra_d55_60`: la ramp density ora arriva a **80**
  (`study.yml:101`, valori 55 e 80). Ho sentito finora solo fino a density 60;
  density 80 è ancora da sentire.
- [ ] Ascolto differenza di density tra due stream in stack (versions),
  ripetuto a diverse densità di base: 20–30 Hz, 30–50 Hz, 50–100 Hz,
  100–1000 Hz. (Il range 30–50 Hz con differenze 0.01/0.1/1 è già stato
  fatto — vedi ascolto/2026-07-14.md, sessione 3. Manca: affinare la soglia
  di transizione tra 0.1 e 1 nel range già fatto, e ripetere lo stesso
  protocollo negli altri range.)
- [ ] Ascolto sweep con il parametro `distribution`: riprendere ad usarlo e
  sentire come si comporta il movimento della distribution a diverse
  densità che si muovono nel tempo (density come sweep, non fissa).
- [ ] Chiarire Sessione 1 del 2026-07-14: "3 Hz (terzi)" — capire se
  intendevo terzi di tono o Hz di differenza.
- [ ] Fare tutti gli ascolti dei grani della scala **short** e della scala **long**.
- [ ] Scrivere la scala **meso** (ancora da fare) e poi farne gli ascolti.

## Fatto

- [x] 2026-07-18 — Diario di ascolto spostato in `studies/ascolto/` (unico per lo
  studio) e struttura `studies/` appiattita: le scale sono cartelle dirette
  (`base`, `short`, `long`, `stack`) invece che `study01_*`. Il repo è lo studio;
  in futuro diventerà un template. `STUDY=base` sostituisce
  `STUDY=study01_grain_density`.
