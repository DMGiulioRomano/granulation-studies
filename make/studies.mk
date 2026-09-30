# Stadi della pipeline che producono dati testuali (no audio).

.PHONY: sweep
sweep: _require-study $(MARKER)
	$(PY) -m granstudies sweep $(STUDY) $(if $(STREAM),--stream $(STREAM),)

.PHONY: stack
stack: _require-study $(MARKER)
	$(PY) -m granstudies stack $(STUDY)

.PHONY: versions
versions: _require-study $(MARKER)
	$(PY) -m granstudies versions $(STUDY)

.PHONY: percorso
percorso: _require-study $(MARKER)
	$(PY) -m granstudies percorso $(STUDY)

# Cartella (o cartelle) di output correnti: le risolve granstudies, non lo
# shell, cosi' la regola di `for_each:` e del filtro COMBO vive in un posto
# solo (la usa anche la funzione zsh `study`). Una riga per combinazione.
.PHONY: where
where: _require-study $(MARKER)
	@$(PY) -m granstudies where $(STUDY)

# La pagina del laboratorio del singolo stream: una per studio, non una per
# combinazione di `for_each:` (le tacche sono quelle di tutto lo study.yml),
# in generated/<study>/graph.html. Non legge il disco: la si scrive anche
# prima di qualunque render.
.PHONY: graph
graph: _require-study $(MARKER)
	$(PY) -m granstudies graph $(STUDY)

# La pagina legge i campioni con fetch + decodeAudioData per disegnare
# sonogramma e forma d'onda: da `file://` il browser lo vieta (origine opaca),
# quindi la si serve. Non e' `http.server` perche' il laboratorio fa
# `POST /render`: vedi `granstudies.serve`. macOS: `open -a Safari`, e i
# pannelli Apri/Salva passano da `osascript`.
PORT ?= 8000
.PHONY: serve
serve: graph
	@($(PY) -m granstudies serve $(STUDY) --port $(PORT) & \
	  sleep 1; open -a Safari "http://localhost:$(PORT)/graph.html"; wait)

.PHONY: describe
describe: _require-study $(MARKER)
	$(PY) -m granstudies describe $(STUDY)

.PHONY: matrix
matrix: _require-study $(MARKER)
	$(PY) -m granstudies matrix $(STUDY) $(if $(THRESHOLD),--threshold $(THRESHOLD),)

.PHONY: compose
compose: _require-study $(MARKER)
	$(PY) -m granstudies compose $(STUDY) \
		$(if $(SEED),--seed $(SEED),) \
		$(if $(STEPS),--steps $(STEPS),) \
		$(if $(START),--start $(START),)

# Niente `render` fra i prerequisiti: `all-study` lo ha gia' fatto, e nel giro
# di `study` la seconda passata era solo rumore nel log (con `for_each:`, un
# giro in piu' su ogni combinazione). Se l'audio manca, cmd_sv lo dice
# variante per variante ("esegui prima 'render'").
.PHONY: sv
sv: _require-study $(MARKER)
	$(PY) -m granstudies sv $(STUDY) $(if $(LAYOUT),--layout $(LAYOUT),) $(if $(STREAM),--stream $(STREAM),)

# Pipeline completa: sweep + stack + versions + percorso + render. versions e
# percorso sono attivati per presenza (cmd_versions/cmd_percorso sono no-op
# se lo study.yml non ha il blocco corrispondente), quindi girano sempre
# prima di render senza costo per gli study che non li usano.
.PHONY: all-study
all-study: sweep stack versions percorso render #describe matrix compose render-final
