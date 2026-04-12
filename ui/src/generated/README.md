# Generated Types

This directory contains TypeScript types generated from the FastAPI OpenAPI
schema. The backend is the single source of truth for all API contracts.

## Rules

- **Do not edit `api.ts` by hand.** It is regenerated from `api/openapi.json`
  by `just codegen`.
- **Do not add new types in other `types.ts` files that duplicate shapes from
  here.** Alias instead.
- **When the backend schema changes**, run `just export-schema && just codegen`
  and commit both files.

## Migration pattern

Feature-local `types.ts` files should become thin aliases over the generated
schema components. See `ui/src/features/assets/types.ts` for the reference
pattern established in Phase 1 of the contract testing rollout:

```typescript
import type { components } from '@/generated/api'

type Schemas = components['schemas']

export type Asset = Schemas['AssetRead']
export type AssetGroup = Schemas['AssetGroupRead']
```

If a frontend-only type is truly needed (for example a UI-only derived
shape that has no backend equivalent), keep it in the feature `types.ts`
but clearly comment it as UI-only so the boundary is visible.

## Path naming

The generated `paths` type uses the raw FastAPI route table — no `/api`
prefix. The `/api` prefix is added by the Vite dev proxy and by the deployed
web server, not by the router itself. When referencing `paths['/foo']`,
use the route string as it appears in the FastAPI router.

## CI freshness check

`just check-schema-fresh` regenerates schema and types, then fails if
`git diff` is non-empty. Run this locally before pushing if you touched
any Pydantic response model, and it will also run automatically in the
`Contract Freshness` GitHub Actions workflow.
