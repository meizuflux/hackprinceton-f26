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
	npm ci

dev:
	npm run dev -- --host 127.0.0.1 --port 5173 --strictPort

build:
	npm run build

test:
	npm test

preview:
	npm run preview -- --host 127.0.0.1

format:
	npm run format
