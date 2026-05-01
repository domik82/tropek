# Contributing to TROPEK

## Development Setup

```bash
# Install dependencies
just install

# Start infrastructure (TimescaleDB + Redis)
just infra

# Apply database migrations
just migrate

# Start full dev environment (API + UI + adapters)
just dev
```

## Running Tests

```bash
just test          # API unit tests (no infrastructure required)
just test-ui       # UI component tests
just test-int      # API integration tests (requires: just test-env)
just test-schema   # Schemathesis property-based tests (requires: just test-env)
just test-all      # unit + integration + UI
```

## Code Quality

```bash
just check         # lint + format check + typecheck (all)
just lint          # ruff linter (Python)
just lint-ui       # eslint (React hooks, compiler)
just typecheck     # mypy strict mode
just fmt           # ruff formatter (apply)
```

Pre-commit hooks run ruff, mypy, and eslint automatically on commit.

## Pull Requests

- Keep PRs focused on a single concern
- All CI checks must pass (lint, typecheck, tests, Docker security scan)
- PR titles should be concise (<70 chars) and descriptive

## Release Process

TROPEK uses a single version for all components (API, UI, adapter).
All components are tagged and released together.

### Cutting a release

1. Update `CHANGELOG.md` with the new version's notable changes
2. Commit the changelog update to `main`
3. Create and push a git tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. CI automatically:
   - Builds multi-platform Docker images (amd64 + arm64)
   - Pushes to `ghcr.io/domik82/tropek-{api,ui,adapter-prometheus}:v1.0.0`
   - Creates a GitHub Release with auto-generated notes from PR titles
   - Attaches `deploy/docker-compose.yml` and `deploy/.env.example`
5. Optionally edit the GitHub Release notes in the UI before publishing

### Updating `latest` tag

Run the "Latest Images" workflow manually from the GitHub Actions UI
when `main` is stable.

### Changelog conventions

- `CHANGELOG.md` is maintained manually for major releases
- For patch releases, GitHub's auto-generated release notes (from PR titles) are usually sufficient
- The changelog and GitHub release notes are independent — you can use either or both
