.DEFAULT_GOAL := help
.PHONY: help frontend-install frontend-dev frontend-build frontend-test frontend-preview frontend-format \
	data-install data-generate data-verify data-truth

PYTHON ?= python3

help:
	@echo "make frontend-install  Install locked dependencies"
	@echo "make frontend-dev      Start Vite at http://localhost:5173"
	@echo "make frontend-build    Build the frontend into frontend/dist/"
	@echo "make frontend-test     Run contract tests"
	@echo "make frontend-preview  Preview the production build"
	@echo "make frontend-format   Format source files"
	@echo "make data-install      Install pinned case-generator dependencies (PYTHON=python3)"
	@echo "make data-generate     Regenerate the synthetic Kestrel case in cases/kestrel/"
	@echo "make data-verify       Rebuild the case in a temp dir and check every file hash"
	@echo "make data-truth        Write the answer key to .truth/kestrel/ (git-ignored; scoring only)"

frontend-install:
	cd frontend && bun install --frozen-lockfile

frontend-dev:
	cd frontend && bun run --bun dev --host 127.0.0.1 --port 5173 --strictPort

frontend-build:
	cd frontend && bun run --bun build

frontend-test:
	cd frontend && bun run --bun test

frontend-preview:
	cd frontend && bun run --bun preview --host 127.0.0.1

frontend-format:
	cd frontend && bun run --bun format

data-install:
	$(PYTHON) -m pip install -r generator/requirements.txt

data-generate:
	$(PYTHON) generator/generate.py

data-verify:
	$(PYTHON) generator/generate.py --verify

data-truth:
	$(PYTHON) generator/generate.py --truth-out .truth/kestrel
