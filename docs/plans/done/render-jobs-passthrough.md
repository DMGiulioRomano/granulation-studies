# Il render dello studio girava a un core solo

Issue #73. Porting da mare-nostrum (DMGiulioRomano/mare-nostrum@3d81f41 e
DMGiulioRomano/mare-nostrum@1357ec2), dove il problema è stato trovato e
misurato. Nessun cambio di sintassi `study.yml` e nessun cambio udibile
nell'audio: dove passa dal chunk path dell'engine cambia al più di 1 LSB a
24 bit (cambia solo l'ordine delle somme float64).

## Il sintomo

In mare-nostrum `make render STUDY=grana-001-41 FORCE=1` impiegava circa 6
minuti su una macchina a 12 core, con 11 core fermi. Lo sweep di quello studio
ha un solo `ordering`: 168 gradini da 20s, cioè **56 minuti di audio in un
unico file continuo**. È il modo giusto di ascoltare uno studio a un asse — un
solo file da percorrere — ma è anche il motivo per cui il parallelismo *tra
varianti* non serve a niente: di varianti ce n'è una. Qui vale lo stesso per
ogni scala che collassa in pochi documenti lunghi (`brano01_v2`, 10 minuti).

## La causa

Il sistema ha due livelli di parallelismo e con una variante sola non se ne
attivava nessuno.

**Livello 1, tra varianti.** `render_variants` (`src/granstudies/render.py`) ha
un `ProcessPoolExecutor` che dà una variante a ogni worker. Con una variante
sola il pool è degenere: un worker, un core.

**Livello 2, dentro una variante.** L'engine ha già il chunk-parallel
dell'overlap-add dei grani (`engine/src/pge/rendering/numpy_parallel.py`,
attivato da `NumpyAudioRenderer._overlap_add` quando `jobs > 1` e i grani
superano `DEFAULT_MIN_PARALLEL_GRAINS = 1024`). Ma `engine_bridge.render`
chiamava `pge.api.render(...)` **senza mai passare `jobs`**, e il default
dell'API è `jobs=1`: codice funzionante e mai raggiunto da `granstudies`.

## La soluzione

`--jobs` diventa il **budget totale di processi**, non più "quante varianti in
parallelo". `_split_jobs(budget, n_pending)` lo ripartisce tra i due livelli:

```python
workers     = max(1, min(budget, n_pending))
engine_jobs = max(1, budget // workers)
```

| caso | workers | engine_jobs |
|------|---------|-------------|
| una variante lunga | 1 | budget |
| varianti ≥ budget | budget | 1 (come prima) |
| `--jobs 1` | 1 | 1 (sequenziale puro) |

`workers * engine_jobs` non supera mai il budget, quindi quando i due pool si
annidano non c'è oversubscription. `_render_one` passa `jobs` a entrambe le
pass (mix e stem).

Il default del budget è **tutti i core che il processo può usare**, non più
`min(8, cpu)`. Il cap a 8 proteggeva la RAM da molti buffer lunghi in memoria
insieme, e quel rischio non sparisce con una variante sola.

"Che il processo può usare" vuol dire l'affinity dove esiste
(`_available_cores`, la stessa regola di `numpy_parallel._available_cores`
nell'engine), e `os.cpu_count()` solo dove manca, come su macOS.
`os.cpu_count()` conta i core della macchina anche quando il processo ne ha
meno (taskset, cpuset di un container, quote di CI): lì il budget supera i
core disponibili, l'assenza di oversubscription promessa sopra non vale più, e
la RAM della pass STEMS si moltiplica per core che il processo non può usare. Prima il cap a 8 limitava il danno; senza cap,
il danno cresce con la macchina.

Un minuto di buffer stereo float64 a 48 kHz pesa ~46 MB, ma il picco di un
render è ~3.5 volte il buffer, perché il `dc_block` ne fa una copia e lavora
su temporanei per canale. Misurato con `tracemalloc` su `render_stream_to_file`
di un task da 60 s: 161 MB di picco contro 46 MB di buffer. Nella pass STEMS,
attiva di default, l'engine con `jobs > 1` rende **gli stream in parallelo**,
uno per worker e ciascuno col suo buffer a durata piena. `brano01_v2` è un
documento solo con 7 stream da 600 s: prende un worker e tutto il budget va
all'engine. Il picco è ~1.6 GB per stream, quindi fino a ~11 GB con 7 core o
più. Prima della modifica gli stem giravano in sequenza, con un picco di
~1.6 GB. La pass di mix non si moltiplica: il buffer intero sta solo nel
padre, i chunk dei worker ne coprono ~1/N ciascuno.

Se la memoria non basta, `JOBS=n` abbassa il budget; `STEM=false` salta la
pass che si moltiplica.

## Quanto rende, misurato (su mare-nostrum)

A/B sulla sola variante da 56 minuti, `STEM=false`, 12 core:

| | wall | CPU medio |
|---|---|---|
| `JOBS=1` (identico al pre-modifica) | 3m47 | 99% |
| `JOBS=12` | 2m36 | 180% |

**1.45×.** Meno di quanto 12 core farebbero sperare: per Amdahl solo ~34% del
tempo sta nell'overlap-add, l'unica parte che questo cambiamento parallelizza.
Il resto è irriducibile qui — la generazione dei grani vive nel processo padre
(consuma il `random` seminato, e parallelizzarla romperebbe la
riproducibilità), più `dc_block`, clip, scrittura su disco e il travaso dei
buffer di chunk dai worker al padre via pickle.

## Cosa è stato toccato

- `src/granstudies/engine_bridge.py` — `render(..., jobs=1)` inoltrato a
  `api.render(jobs=...)`.
- `src/granstudies/render.py` — `_split_jobs`, `_render_one` che passa `jobs`
  a entrambe le pass, default del budget a tutti i core (`_available_cores`).
- `src/granstudies/__main__.py`, `Makefile`, `docs/study-yml-reference.md` —
  help di `--jobs`/`JOBS`.

Il submodule `engine/` **non è stato toccato**: l'API `jobs` esisteva già.

## Test

- `tests/test_render.py::test_split_jobs_*` — la ripartizione, incluso
  l'invariante che il prodotto non superi mai il budget.
- `tests/test_render.py::test_render_passes_engine_jobs_to_bridge` — regressione
  diretta sul bug: il budget arriva davvero al bridge.
- `tests/test_render.py::test_render_jobs_one_is_sequential_on_both_levels` —
  `JOBS=1` con più varianti: tutte in-process, tutte con `jobs=1`.
- `tests/test_render.py::test_render_default_budget_*` — senza `jobs` il
  budget sono i core concessi al processo: l'affinity se c'è, altrimenti
  `os.cpu_count()` (anche quando l'affinity c'è ma non risponde).
- `tests/test_engine_bridge.py::test_render_jobs_activates_parallel_path_without_changing_audio`
  — integrazione reale sull'engine con un documento abbastanza denso da
  superare la soglia dei 1024 grani (1913 grani), audio identico entro 1 LSB a
  24 bit tra `jobs=1` e `jobs=4`. Uno spy su `chunk_grains` verifica che il
  path parallelo sia preso con `jobs=4`, e solo lì. Senza lo spy il test
  passava anche con un bridge che non inoltrava `jobs`, cioè col bug di questa
  issue: due render sequenziali coincidono comunque.

## Quel che resta sul tavolo

**La doppia pass.** Con `STEM=true` (il default) ogni variante passa **due
volte** dall'engine: una per il mix, una per gli stem. Per un documento a uno
stream con `onset: 0` lo stem è lo stesso audio del mix — un 2× quasi puro.
Eliminarlo intreccia la semantica di `sv export` (vuole sia il pane mix sia
quello stem) e il manifest di cache che governa lo skip incrementale: merita un
branch suo. Nel frattempo la via senza codice esiste già:
`make render STUDY=... STEM=false`.
