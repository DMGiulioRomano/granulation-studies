# granulation-studies — interfaccia di alto livello.
# Ogni target wrappa la CLI `python -m granstudies` dentro il venv.
#
# Uso tipico:
#   make setup
#   make sweep   STUDY=grain_1-10ms
#   make render  STUDY=grain_1-10ms
#   make describe STUDY=grain_1-10ms
#   make matrix  STUDY=grain_1-10ms
#   make compose STUDY=grain_1-10ms
#   make render-final STUDY=grain_1-10ms

# Interprete di sistema per creare il venv: preferisci 3.11 (versione del
# progetto), poi python3/python. Override esplicito: make setup PYTHON=...
PYTHON := $(shell command -v python3.11 || command -v python3 || command -v python)
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
	@echo "  make sweep STUDY=...        genera le varianti YAML  (STUDY = nome cartella in studies/, es. grain_1-10ms)"
	@echo "  make stack STUDY=...        genera il documento multi-stream (stack, puro)"
	@echo "  make versions STUDY=...     genera il documento delle versioni (prodotto cartesiano)"
	@echo "  make percorso STUDY=...     genera il documento del percorso (orchestrazione temporale)"
	@echo "  make render STUDY=...       renderizza audio (incrementale, parallelo; FORCE=1 rifa' tutto, JOBS=n worker)"
	@echo "  make describe STUDY=...     descrittori audio -> results.yml"
	@echo "  make matrix STUDY=...       matrice di parentela -> kinship.json"
	@echo "  make compose STUDY=...      genera final.yml dal percorso/grafo"
	@echo "  make render-final STUDY=... renderizza il brano finale"
	@echo "  make sv STUDY=...            CSV envelope per Sonic Visualiser"
	@echo "  make all-study STUDY=...    pipeline completa (sweep→stack→render)"
	@echo "  make clean / clean-all      pulizia output / output+venv"

.PHONY: _require-study
_require-study:
	@if [ -z "$(STUDY)" ]; then \
		echo "Errore: specifica STUDY=<nome cartella in studies/>"; exit 1; \
	fi
