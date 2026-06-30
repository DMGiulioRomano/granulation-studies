# Stadi della pipeline che producono dati testuali (no audio).

.PHONY: sweep
sweep: _require-study $(MARKER)
	$(PY) -m granstudies sweep $(STUDY) $(if $(STREAM),--stream $(STREAM),)

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

.PHONY: sv
sv: _require-study render
	$(PY) -m granstudies sv $(STUDY) $(if $(LAYOUT),--layout $(LAYOUT),) $(if $(STREAM),--stream $(STREAM),)

.PHONY: all-study
all-study: sweep render #describe matrix compose render-final
