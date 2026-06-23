# granulation-studies — interfaccia di alto livello.
# Ogni target wrappa la CLI `python -m granstudies` dentro il venv.
#
# Uso tipico:
#   make setup
#   make sweep   STUDY=study01_grain_density
#   make render  STUDY=study01_grain_density
#   make describe STUDY=study01_grain_density
#   make matrix  STUDY=study01_grain_density
#   make compose STUDY=study01_grain_density
#   make render-final STUDY=study01_grain_density

PYTHON ?= python3
VENV   := .venv
VENV_BIN := $(VENV)/bin
PY     := $(VENV_BIN)/python
PIP    := $(VENV_BIN)/pip
MARKER := $(VENV)/.installed

STUDY ?=

.DEFAULT_GOAL := help

include make/venv.mk
include make/studies.mk
include make/render.mk
include make/clean.mk

.PHONY: help
help:
	@echo "granulation-studies — target disponibili:"
	@echo "  make setup                 venv + submodule engine + dipendenze"
	@echo "  make tests                 esegue pytest (gate pre-commit)"
	@echo "  make sweep STUDY=...        genera le varianti YAML"
	@echo "  make render STUDY=...       renderizza audio + partitura PDF"
	@echo "  make describe STUDY=...     descrittori audio -> results.yml"
	@echo "  make matrix STUDY=...       matrice di parentela -> kinship.json"
	@echo "  make compose STUDY=...      genera final.yml dal percorso/grafo"
	@echo "  make render-final STUDY=... renderizza il brano finale"
	@echo "  make clean / clean-all      pulizia output / output+venv"

.PHONY: _require-study
_require-study:
	@if [ -z "$(STUDY)" ]; then \
		echo "Errore: specifica STUDY=<nome cartella in studies/>"; exit 1; \
	fi
