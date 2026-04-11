# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TROPEK** = Trend Reporting and Objective Evaluation toolKit — a standalone quality gate and performance test evaluation platform. It is a Python rewrite/extraction of Keptn's `lighthouse-service`, deployable without Kubernetes via Docker Compose.

Stack: Python 3.13, FastAPI, PostgreSQL + TimescaleDB, Redis (arq job queue), uv (package manager).

## Common Commands

```bash
just              # list all available recipes
just install      # install all dependencies (uv sync + pnpm)
just test         # API unit tests
just test-int     # API integration tests (requires just test-env first)
just test-ui      # UI component tests
just test-all     # all tests
just test-one engine/test_evaluator.py  # run a specific test file
just lint         # ruff linter (Python)
just lint-ui      # eslint (UI — React hooks, compiler)
just typecheck    # mypy
just check        # lint + format check + typecheck
just dev          # start full dev environment (Ctrl+C to stop)
just migrate      # apply DB migrations (dev)
just up           # docker compose up --build
```

Raw commands (equivalent, for when `just` is unavailable):

```bash
uv sync                                               # install workspace deps
uv run --directory api pytest tests/ -m "not integration" -q  # unit tests
uv run --directory api pytest tests/ -m integration -v        # integration tests
uv run ruff check api/ adapters/                              # lint
uv run mypy api/tropek adapters/prometheus/tropek_prometheus   # typecheck
```

## Integration Tests — REQUIRED STEPS

Integration tests require a **dedicated test database** on port 5433 — completely separate from the
dev database (port 5432). **Never run integration tests against the dev database.**

`.env.test` is committed with local defaults — no setup needed.

### Running integration tests

```bash
# Step 1: Start test infrastructure (idempotent — safe to re-run)
just test-env

# Step 2: Run integration tests (.env.test is loaded automatically by pytest-dotenv)
just test-int

# Step 3: Tear down when done (removes container + volume)
just test-env-down
```

`api/tests/db/conftest.py` loads `.env.test` via `python-dotenv` when the DB fixtures are imported —
scoped to integration tests only, so unit tests are not affected. **Never** pass
`TEST_DATABASE_URL` or `QG_*` vars as shell prefixes or inline exports.

### Re-running migrations only (container already running)

```bash
just migrate-test
```
Never use `set -a && source .env.test && set +a` or any bash chaining for this purpose.

## Architecture

### Service Topology (Docker Compose)

| Service | Port | Role |
|---|---|---|
| `api` | 8080 | FastAPI REST API |
| `worker` | — | arq job workers (×4) for async evaluation |
| `adapter-prometheus` | 8081 | Prometheus query adapter |
| `timescaledb` | 5432 | PostgreSQL + TimescaleDB (metrics, evaluations, SLOs) |
| `redis` | 6379 | Job queue + response cache |
| `ui` | 5173 | React SPA (Vite dev server) |

### Evaluation Flow

1. Client POSTs to `/evaluations`
2. API validates SLO, enqueues job to Redis
3. Worker dequeues, queries adapter (e.g., Prometheus) for SLI values
4. Core engine evaluates SLI values against SLO criteria — pure function, no I/O
5. Results written to TimescaleDB, cached in Redis
6. Client fetches result via GET

### Core Evaluation Engine (`api/tropek/modules/quality_gate/evaluation_engine/`)

Zero-I/O pure Python logic ported from Keptn's Go lighthouse-service. All unit-testable without database or network:

- `evaluator.py` — Top-level `evaluate()` entry point
- `slo_parser.py` — Parse and validate SLO YAML
- `criteria.py` — Parse criteria strings, evaluate pass/warning/fail conditions
- `scoring.py` — Per-objective scoring and total score calculation
- `variables.py` — Template variable substitution in SLI queries

### Workspace Layout

```
tropek/
├── api/                          # FastAPI app, worker, DB models, repositories
│   ├── tropek/
│   │   ├── modules/
│   │   │   ├── assets/           # Asset (project/service) group CRUD
│   │   │   ├── datasource/       # Datasource (adapter) registry
│   │   │   ├── quality_gate/     # Evaluation router + layered architecture
│   │   │   │   ├── evaluation_engine/  # Pure scoring logic (zero I/O)
│   │   │   │   ├── repositories/       # Data access layer
│   │   │   │   ├── workflows/          # Orchestration (trigger, execution, re-eval, presentation)
│   │   │   │   ├── schemas/            # API contracts
│   │   │   │   └── shared/             # Cross-cutting (exceptions, params, DI)
│   │   │   ├── sli_registry/     # SLI definition CRUD
│   │   │   └── slo_registry/     # Versioned SLO CRUD
│   │   └── ...
│   ├── tests/
│   │   ├── engine/               # Pure unit tests
│   │   ├── db/                   # Integration tests (mark: integration)
│   │   └── data/slo/             # YAML fixtures for engine tests
│   └── pyproject.toml
├── adapters/
│   ├── prometheus/               # Standalone Prometheus query adapter
│   └── mock/                     # Mock adapter with data generator (for testing)
├── config.yaml                   # Non-secret runtime config template
├── .env.example                  # Secrets template (DB, Redis, API key)
└── pyproject.toml                # UV workspace root + ruff/mypy/pytest config
```

### SLO File Format

TROPEK's SLO format is a superset of Keptn 1.0: **SLI queries are embedded** in the SLO YAML under an `indicators` block (no separate SLI file). Criteria support fixed thresholds (`<600`), relative percent (`<=+10%`), and relative absolute (`<=+50`) comparisons against a configurable baseline.

### Repository/Database Layer

SQLAlchemy async ORM (asyncpg driver) with Alembic migrations. Repositories in `api/tropek/modules/*/repositories.py` wrap DB access. Integration tests hit a real database — no mocks for DB layer.

## Working Practices

Research the codebase before editing. Never change code you haven't read.

## Code Conventions

- Python 3.13, strict MyPy, ruff with rules: E, W, F, I, N, UP, B, SIM, D, S, DTZ, RUF, PT, C90, PERF, TRY
- Line length: 100 chars
- Pytest: `asyncio_mode = auto`, mark infra-requiring tests with `@pytest.mark.integration`
- Error messages: lowercase, no trailing period, prefer `"could not ..."` phrasing
- Pre-commit runs ruff (lint + format), mypy, and eslint (UI) automatically
- **Variable names must be human-readable.** No cryptic abbreviations like `stmt`, `val`, `subq`,
  `col`, `res`, `tmp`, `cb`. Name variables after what they represent: `key_counts` not `stmt`,
  `tag_value` not `val`, `keys_subquery` not `subq`. Single-letter names are only acceptable for
  trivial loop counters (`i`, `x`) or well-known conventions (`db`, `id`).

### File naming: schemas vs models

- `schemas.py` = Pydantic classes (API serialization layer). Request/response shapes.
- `models.py` = SQLAlchemy ORM classes (DB persistence layer). Lives in `api/tropek/db/models.py`.
- `params.py` = Pydantic parameter objects passed between service layers (not exposed in API).

Never name a file containing Pydantic classes `models.py` — that collides with the ORM layer.
All request body models must inherit `StrictInput` (from `tropek.modules.common.schemas`)
to reject unknown fields. Response and internal models stay on `BaseModel`.

### Python imports

All imports must be at the top of the file. Never place imports inside functions,
methods, or test bodies. This applies to production code and test files equally.

## UI (React SPA)

### Stack & commands

React 19, TypeScript 5.9, Vite 8, Tailwind CSS v4, React Query, shadcn/ui, lucide-react icons.

```bash
just test-ui                                            # Run all UI tests
just test-ui src/features/.../Foo.test.tsx              # Run specific file(s)
```

Raw commands (from `ui/` directory):

```bash
cd ui && pnpm install                     # Install dependencies
pnpm exec vite --host                     # Dev server on :5173
pnpm exec tsc --noEmit -p tsconfig.app.json  # Type check (must use app config)
pnpm exec vitest run                      # Run component tests (Vitest + React Testing Library)
pnpm exec vitest run --watch              # Watch mode
```

Vitest requires `vite.config.ts` for happy-dom environment. Running `pnpm exec vitest` from the repo root
(outside `ui/`) will fail with `document is not defined`. Always use `just test-ui` or `cd ui` first.

### UI testing

Component tests use **Vitest + React Testing Library + happy-dom**. Config lives in `vite.config.ts` (`test` block), setup in `src/test-setup.ts`.

- Place test files next to the component: `ComponentName.test.tsx`
- Wrap components that use React Query in `QueryClientProvider` (see `NoteEntry.test.tsx` for pattern)
- Use `@testing-library/jest-dom/vitest` matchers (loaded via setup file)
- **Happy-dom + React Query cleanup** — happy-dom aborts all in-flight fetches on teardown, causing
  `DOMException: AbortError` noise. Every test file that renders a component using React Query hooks
  (`useQuery`, `useQueries`, `useMutation`) **must** create a fresh `QueryClient` in `beforeEach` and
  cancel queries in `afterEach`:
  ```tsx
  let queryClient: QueryClient
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })
  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })
  ```

### Theme system

Three themes via `data-theme` attribute on `<html>`: `dark` (Radix-based, green primary), `current` (neutral/Dynatrace — "Alt"), `light` (stub — Radix light reversal, TODO).
The `dark` theme uses Radix UI color scales (slate, green, red, yellow, sky, amber) with semantic aliasing.
The TROPEK logo color is a fixed brand constant (`--tropek-logo`) that never changes with theme.
Colors are CSS custom properties defined in `ui/src/index.css`. Always use semantic tokens:

| Token | Use for |
|---|---|
| `--primary` | Interactive elements: buttons, selected states, links |
| `--popover` / `--border` | Card/menu backgrounds and borders |
| `--muted-foreground` | Secondary text, placeholders |
| `--status-pass/warning/fail` | Evaluation outcomes only — never for action identity |

### Color conventions

- **Status colors** (`text-pass`, `text-warning`, `text-fail`, `text-invalidated`) = evaluation outcomes.
  Used in: heatmaps, result badges, score text, SLI breakdown table.
- **Action accent colors** (gray `#8B949E`, red `#F85149`, blue `#58A6FF`, purple `#A371F7`) = action identity.
  Used in: action forms, context menus. Intentionally hardcoded — must NOT overlap with status palette.
- **Interactive elements** use `--primary` (theme-aware). Never hardcode button colors.

### Design patterns

- **Color identity via accents, not backgrounds.** Cards/forms use neutral `bg-popover`.
  Color comes from a 3px top accent strip + title text + confirm button. No tinted backgrounds.
- **Compact, right-aligned forms.** Inline action forms use `max-w-md` + `flex justify-end`.
  Single-line inputs, not textareas. Only show fields the API actually uses.
- **Two-line menu items.** Dropdown items show label + description with colored left accent bar.
- **Sans-serif for UI chrome.** Body is monospace (good for data). Sidebars, menus, dialogs
  need inline `fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"`.

### Key UI directories

```
ui/src/
├── components/
│   ├── AssetTree/             # Sidebar tree component
│   ├── charts/                # Shared chart components
│   ├── labels/                # Label/badge components
│   └── shared/                # Shared UI primitives
├── features/
│   ├── assets/                # Asset group hooks and types
│   ├── datasources/           # Datasource management
│   ├── evaluations/           # Eval detail, actions, SLI table, trend charts
│   ├── navigator/             # Navigator page, asset panel, heatmaps
│   ├── registry/              # 3-mode SLO registry (tree, detail panel, sidebar)
│   ├── slis/                  # SLI definition management
│   └── slos/                  # SLO CRUD, SLO link dialogs
├── lib/                       # Theme context, result colors, utilities
└── pages/                     # Route-level page components
```

## Configuration

- Non-secret config: `config.yaml` (server, DB pool, cache TTLs, queue settings, adapter URLs, logging)
- Secrets: environment variables prefixed `QG_` (e.g., `QG_DB_PASSWORD`, `QG_REDIS_PASSWORD`, `QG_SECRET_KEY`)

## Shell command discipline

**Avoid compound commands.** Pipes (`|`), chains (`&&`, `||`, `;`), subshells (`$(...)`),
and redirects (`>`) require manual user approval because they cannot be trusted as a unit.
Simple, single commands are auto-approved and run without interruption.

Prefer dedicated tools over shell compounds:

✗ cat file.py | grep -n "def "          ← requires approval
✓ grep -n "def " file.py               ← use the Grep tool directly

✗ ls src/ | head -n 20                  ← requires approval
✓ ls src/                               ← use the Glob tool instead

✗ cd api && uv run pytest tests/ -q     ← requires approval
✓ uv run --directory api pytest tests/ -q   ← flags over cd

**When a compound is genuinely unavoidable**, wrap it in a versioned shell script under
`scripts/` and call the script. The script has a known, reviewable effect and becomes an
auto-approved command. Example: if you need `npx tool | head -n 10` repeatedly, create
`scripts/run-tool-preview.sh` — then `./scripts/run-tool-preview.sh` is a single approved call.

### Agent test commands

`just` recipes are for humans (full output). Agents should use the wrapper scripts
with `--tail` to get summary-only output as a single auto-approvable command:

```bash
# API unit tests — summary only
./scripts/api-test.sh --tail 5

# API integration tests — summary only
./scripts/api-test.sh --tail 5 -m integration -v

# UI component tests — summary only
./scripts/ui-test.sh --tail 10

# Specific API test file
./scripts/api-test.sh --tail 20 tests/db/test_baseline_query.py -v

# Specific UI test file
./scripts/ui-test.sh --tail 10 src/features/.../Foo.test.tsx

# UI lint (ESLint — React hooks, compiler) — summary only
./scripts/ui-lint.sh --tail 10

# Specific UI file lint
./scripts/ui-lint.sh --tail 10 src/features/.../Foo.tsx
```

Never use `cmd 2>&1 | tail -N` directly — that's a compound command requiring approval.

## Git commands

When working with git in worktrees, always issue git add and git commit as
separate bash calls, never chained with &&.

Never use `cd <path> && git <command>` patterns. Always use `git -C <path> <command>` instead.

✗ cd /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/theme-system && git add ui/src/index.css
✓ git -C /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/theme-system add ui/src/index.css

✗ cd .worktrees/theme-system && git add . && git commit -m "..."
✓ git -C .worktrees/theme-system add .
✓ git -C .worktrees/theme-system commit -m "..."

## Python execution

Never use `python` or `python3` directly. Always use `uv run` to execute 
Python code and scripts — this ensures the project virtualenv is used, 
not the system Python.

✗ python script.py
✗ python3 -m pytest
✓ uv run python script.py
✓ uv run pytest
✓ uv run -m pytest