# Compstat

Compstat is a prototype for an inspectable investigative evidence board. It presents a fictional case through cited evidence, relationships, ranked gaps, suggested evidence, source inspection, and an audit trail.

This repository currently contains a mocked frontend only. Case data is fictional and disposable; ZIP selection runs a simulated ingestion flow and does not read ZIP contents. There is no backend or real analysis yet.

## Run locally

Requires Bun 1.4.4. From the repository root:

```sh
cd frontend
make install
make dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend documentation has the full demo path and additional commands in [frontend/README.md](frontend/README.md).

Run tests and build the production bundle from the repository root:

```sh
make -C frontend test
make -C frontend build
```

## Run with Docker Compose

Requires Docker Compose and a running Docker daemon. The service binds to `127.0.0.1:5173`, so stop any other service using that port first.

```sh
docker compose up --build -d
```

Open [http://localhost:5173](http://localhost:5173). Stop the service with:

```sh
docker compose down
```

## Project docs

- [Frontend guide](frontend/README.md)
- [Project specification](SPEC.md)
- [Agent and implementation notes](AGENTS.md)

Before changing `SPEC.md`, propose the changes to the user and team members and wait for their explicit approval. Keep `SPEC.md` as the single product specification.
