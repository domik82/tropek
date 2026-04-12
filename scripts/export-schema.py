#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to api/openapi.json.

Imports the app object directly — no uvicorn, no network, no database.
Run via `just export-schema` or `uv run python scripts/export-schema.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

from tropek.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / 'api' / 'openapi.json'


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + '\n')
    print(f'wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()
