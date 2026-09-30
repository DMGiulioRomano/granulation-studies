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

# YAML e audio dello sweep che lo study.yml non genera piu': succede quando si
# CAMBIA il valore di un asse invece di aggiungerne uno, e finche' il vecchio
# YAML resta il render lo tratta come una variante viva. Di default elenca
# soltanto; APPLY=1 cancella. STEMS=1 aggiunge al bersaglio gli stem
# (<mix>__<stream>.aif), che altrimenti seguono il mix da cui nascono.
# Si accendono solo su 1/true/yes: e' un comando che cancella, e con un
# $(if ...) nudo APPLY=0 avrebbe cancellato.
PRUNE_ON := 1 true yes
.PHONY: prune
prune: _require-study $(MARKER)
	$(PY) -m granstudies prune $(STUDY) \
		$(if $(filter $(PRUNE_ON),$(APPLY)),--apply,) \
		$(if $(filter $(PRUNE_ON),$(STEMS)),--stems,)

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
