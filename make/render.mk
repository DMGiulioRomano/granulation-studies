# Stadi della pipeline che producono audio/partiture (usano l'engine).

.PHONY: render
render: _require-study $(MARKER)
	$(PY) -m granstudies render $(STUDY) --no-score

.PHONY: render-final
render-final: _require-study $(MARKER)
	$(PY) -m granstudies render-final $(STUDY)
