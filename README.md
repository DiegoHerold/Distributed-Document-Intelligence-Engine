# Eixo - Distributed Document Intelligence Engine

Eixo is a modular document intelligence engine foundation. This repository currently contains Bloco 0 documentation and the Bloco 1 technical foundation for reusable contracts, use cases, capabilities and providers.

## Current Scope

Implemented:

- Python monorepo structure.
- Shared domain types and processing contracts.
- Transport-independent application use cases.
- Capability and provider contracts.
- In-memory Capability Registry.
- Initial FastAPI REST API and CLI foundations.
- Tests and architecture checks.

Not implemented yet:

- PDF parsing.
- Excel parsing.
- OCR.
- Rendering.
- Distributed execution.
- Persistence adapters.

## Development Commands

Preferred commands once `uv` is available:

```bash
uv sync
uv run lint
uv run format --check
uv run typecheck
uv run test
```

This environment does not currently expose `uv` on PATH, so the equivalent local commands are:

```bash
python -m tools.eixo_dev lint
python -m tools.eixo_dev format --check
python -m tools.eixo_dev typecheck
python -m tools.eixo_dev test
```

## Documentation

Start with [docs/README.md](docs/README.md).

API guide: [docs/guides/using-the-api.md](docs/guides/using-the-api.md).
CLI guide: [docs/guides/cli.md](docs/guides/cli.md).

## Public Python Package

Current public distribution: `eixo-document-sdk-python`.

Public import:

```python
from eixo import DocumentEngine, ProcessingRequest
```

The package includes `py.typed` and currently exposes local mode only. Real PDF, Excel and OCR capabilities are not implemented yet.
