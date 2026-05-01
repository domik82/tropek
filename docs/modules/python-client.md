# Python Client SDK

Typed Python client for the TROPEK API. Provides programmatic access to all TROPEK
resources (assets, SLOs, SLIs, datasources, evaluations, annotations, trends) and a
declarative YAML manifest system for infrastructure-as-code workflows.

## Installation

```bash
cd clients/python
uv pip install -e .
```

Requires Python 3.13+. Dependencies: httpx, pydantic, pyyaml, click.

## Key Concepts

**Programmatic API** — `TropekClient` exposes namespaced methods for every resource
type. Create a client, call methods, get typed Pydantic models back.

```python
from tropek_client import TropekClient

with TropekClient('http://localhost:8080') as client:
    assets = client.assets.list()
    client.evaluations.evaluate('web-api', 'release-42', start, end)
```

**Manifest system** — Define resources as YAML documents with `api_version`, `kind`,
`metadata`, and `spec` fields. The manifest loader parses, validates, topologically
sorts by dependency, and applies via desired-state reconciliation (create/update/skip).

**CLI** — Three commands: `tropek validate` (offline YAML check), `tropek apply`
(reconcile with `--dry-run` support), `tropek export` (dump current state as YAML).

## Details

See [`clients/python/README.md`](../../clients/python/README.md) for the full API
reference, manifest format, CLI usage, and error handling guide.

See [`clients/python/docs/architecture.md`](../../clients/python/docs/architecture.md)
for contributor-level design details.
