# granulation-studies — Contesto

Vocabolario condiviso del progetto. Solo termini specifici; ogni definizione dice
cosa una cosa **è**, non cosa fa. Un termine canonico per concetto; i sinonimi da
non usare stanno sotto _Evita_. Il linguaggio è tenuto coerente con la matematica
(spazio, campo, regione, metrica). I termini della psicoacustica che fondano questo
lavoro entreranno qui man mano che vengono studiati, non prima.

## Parametri

**density**:
L'unica altezza del sistema. Frequenza di emissione dei grani; percorre un unico
continuum — sotto ~20 Hz ritmo, sopra pitch, in mezzo flutter. Scegliere le altezze
vuol dire scegliere valori di density.
_Evita_: pitch come parametro autonomo (il pitch è un percetto che emerge, non una leva)

**grain.duration**:
Durata del singolo grano. Con density è uno dei due soli parametri dello study01.

**duty** (fattore di riempimento):
Grandezza derivata `density × grain.duration`: la frazione di tempo coperta dai grani.
Sotto 1 i grani hanno buchi, sopra 1 si sovrappongono. È un campo scalare sullo spazio
dei valori.

## Costruzione

**stream**:
Una voce = un file yaml. Accordi e polimetrie nascono impilando più stream con density
in rapporto tra loro (in banda audio → accordi, in sub-audio → polimetrie);
l'orchestratore li riunisce in un unico yaml per l'engine.

## Lo sweep nel tempo

Termini che vivono sull'asse **tempo**: sono le leve dell'envelope nello sweep, non
fatti percettivi.

**plateau**:
Un tratto di **tempo** in cui un parametro resta fermo, così da poterne ascoltare la
morfologia senza parametri in movimento. È la tenuta piatta dell'envelope
(`plateau: 5` = 5 secondi di stasi).
_Evita_: usare "plateau" per la regione percettiva ferma → quella è **zona d'ombra**

**transition**:
Il tratto di **tempo** in cui l'envelope muove un parametro da un valore al successivo
(`transition: 5` = 5 secondi di rampa). Sull'asse tempo, non da confondere con la
**transizione** percettiva.

## Lo spazio e il campo

**spazio dei valori** (spazio dei parametri):
Il **dominio**: l'insieme delle configurazioni possibili, un asse per parametro (per
study01: density, grain.duration). Un punto = una configurazione concreta. Geometria
pura dei settaggi, senza percezione. In matematica un sottoinsieme di ℝⁿ.

**campo**:
Una **funzione definita sullo** spazio dei valori: a ogni punto associa un percetto.
"Campo" nel senso matematico — una grandezza distribuita sullo spazio.

**metrica percettiva** (spazio curvo):
La distanza tra due punti misurata in *quanto cambia il percetto*, non in unità di
parametro. Non-euclidea: la stessa distanza parametrica vale molto sulle soglie, ≈ 0
nelle zone d'ombra. La **curvatura** del campo è la mappa di questo gradiente percettivo.

## Regioni e confini

**regione**:
Un **sottoinsieme** connesso del campo dove una proprietà resta costante. Su un asse è
un **intervallo** `[min, max]`; nel 2D è un'area delimitata da soglie. È un insieme di
punti, non un numero.

**delta**:
La **misura** di una regione, `max − min` su un asse. Ogni regione ne ha due: il *delta
parametrico* (euclideo, sui valori) e il *delta percettivo* (il gradiente percettivo
integrato sulla regione). Lo scarto tra i due è la curvatura.

**zona d'ombra**:
Una regione col **delta parametrico grande e delta percettivo ≈ 0**: si può muovere il
parametro molto senza che l'orecchio senta differenza. È ciò che si scopre *stando* in un plateau.
_Evita_: regione statica, zona morta

**soglia**:
Il confine tra due regioni percettive, dove il percetto cambia o salta a un'altra
qualità (es. ritmo↔pitch). Idealizzata come punto/linea `(density, grain.dur)`;
nel 2D è una **curva di livello** del percetto. Atomo del diario, arco del grafo futuro
(le due regioni = nodi).

**transizione**:
La **banda di larghezza finita** attorno a una soglia, dove il percetto sta cambiando.
Larghezza ≈ 1/gradiente: soglia netta = banda stretta, sfumata = banda larga. La
`qualità` nel riepilogo la misura. Vive sull'asse percetto (≠ **transition**, che è tempo).

**cresta**:
Nomignolo per la soglia buchi→continuo, che coincide con la **curva di livello
`duty = 1`** (`density × grain.duration ≈ 1`). La cosa rigorosa è un'isolinea di duty.

**incrocio di soglie**:
Punto dove due soglie si intersecano — due confini che scattano insieme. Nodo speciale
del campo, raro.

**flutter**:
La zona intermedia attorno a ~20 Hz dove density non è ancora né ritmo né pitch: le due
percezioni si confondono.

## Il gesto

**transetto** (sezione):
La **restrizione del campo a una retta**: si fissa un parametro e si muove l'altro (è
ciò che genera lo sweep). È il modo di sondare il campo 2D una linea alla volta, perché
si ascolta nel tempo, non un'area.

## Forma

**drammaturgia**:
Il ritmo con cui si racconta il rapporto tra ridondanza e novità dell'informazione
(forma, percepito, "cadenza evitata"). NON una curva di parametri. La leva, con questo
materiale, è la complessità dei rapporti di density tra stream. Da affrontare più avanti.
