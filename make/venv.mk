# Gestione virtualenv, submodule e test.

$(VENV):
	$(PYTHON) -m venv $(VENV)

# Marker di installazione: ricreato se pyproject cambia.
$(MARKER): pyproject.toml | $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@touch $(MARKER)

.PHONY: setup
setup: submodule $(MARKER)
	@echo "Setup completato. Engine: $$(git -C engine rev-parse --short HEAD 2>/dev/null || echo 'non inizializzato')"

.PHONY: submodule
submodule:
	@git submodule update --init --recursive

.PHONY: tests
tests: $(MARKER)
	$(PY) -m pytest

.PHONY: venv
venv: $(MARKER)
