import type { components } from '@/generated/api'
import type { Datasource } from './domain'

export type DatasourceDto = components['schemas']['DataSourceRead']

// Placeholder for DTO fields intentionally not surfaced in the domain type.
// Add entries as `'field_name'` union members, each with a comment explaining why.
type DroppedDatasourceKeys = never

type MappedDatasourceKeys =
  | 'id'
  | 'name'
  | 'display_name'
  | 'adapter_type'
  | 'adapter_url'
  | 'tags'
  | 'has_token'
  | 'created_at'
  | 'updated_at'

// Compile-time check: every non-dropped DTO key must be mapped. If TypeScript
// errors here with a string literal type (e.g. `"new_field"`), the generated
// DTO has a new field — add it to `MappedDatasourceKeys` and map it in
// `dtoToDatasource`, or add it to `DroppedDatasourceKeys` with a comment
// explaining why the UI intentionally ignores it.
type _DatasourceCoverage = Exclude<
  keyof DatasourceDto,
  MappedDatasourceKeys | DroppedDatasourceKeys
>
const _datasourceExhaustive: _DatasourceCoverage extends never
  ? true
  : _DatasourceCoverage = true
void _datasourceExhaustive

export function dtoToDatasource(dto: DatasourceDto): Datasource {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    adapterType: dto.adapter_type,
    adapterUrl: dto.adapter_url,
    // Backend guarantees string values; the OpenAPI schema widens to unknown.
    tags: dto.tags as Record<string, string>,
    hasToken: dto.has_token,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}
