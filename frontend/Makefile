.DEFAULT_GOAL := help
.PHONY: help install dev build test preview format

help:
	@echo "make install  Install locked dependencies"
	@echo "make dev      Start Vite at http://localhost:5173"
	@echo "make build    Build the frontend into dist/"
	@echo "make test     Run contract tests"
	@echo "make preview  Preview the production build"
	@echo "make format   Format source files"

install:
	bun install --frozen-lockfile

dev:
	bun run --bun dev --host 127.0.0.1 --port 5173 --strictPort

build:
	bun run --bun build

test:
	bun run --bun test

preview:
	bun run --bun preview --host 127.0.0.1

format:
	bun run --bun format
