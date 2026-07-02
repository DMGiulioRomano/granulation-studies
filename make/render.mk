# Stadi della pipeline che producono audio/partiture (usano l'engine).

.PHONY: render
render: _require-study $(MARKER)
	$(PY) -m granstudies render $(STUDY) --no-score $(if $(FORCE),--force,) $(if $(JOBS),--jobs $(JOBS),)

.PHONY: render-final
render-final: _require-study $(MARKER)
	$(PY) -m granstudies render-final $(STUDY)
