import type { components } from '@/generated/api'
import type { Sli } from './domain'

export type SliDto = components['schemas']['SLIDefinitionRead']

// Placeholder for DTO fields intentionally not surfaced in the domain type.
// Add entries as `'field_name'` union members, each with a comment explaining why.
type DroppedSliKeys = never

type MappedSliKeys =
  | 'id'
  | 'name'
  | 'display_name'
  | 'adapter_type'
  | 'version'
  | 'comparable_from_version'
  | 'indicators'
  | 'mode'
  | 'query_template'
  | 'interval'
  | 'methods'
  | 'notes'
  | 'author'
  | 'tags'
  | 'active'
  | 'created_at'

// Compile-time check: every non-dropped DTO key must be mapped. If TypeScript
// errors here with a string literal type (e.g. `"new_field"`), the generated
// DTO has a new field — add it to `MappedSliKeys` and map it in `dtoToSli`,
// or add it to `DroppedSliKeys` with a comment explaining why the UI ignores it.
type _SliCoverage = Exclude<keyof SliDto, MappedSliKeys | DroppedSliKeys>
const _sliExhaustive: _SliCoverage extends never ? true : _SliCoverage = true
void _sliExhaustive

export function dtoToSli(dto: SliDto): Sli {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    adapterType: dto.adapter_type,
    version: dto.version,
    comparableFromVersion: dto.comparable_from_version,
    indicators: dto.indicators,
    // Backend constrains mode to 'raw' | 'aggregated'; OpenAPI widens to string.
    mode: dto.mode as Sli['mode'],
    queryTemplate: dto.query_template,
    interval: dto.interval,
    methods: dto.methods,
    notes: dto.notes,
    author: dto.author,
    // Backend guarantees string values; the OpenAPI schema widens to unknown.
    tags: dto.tags as Record<string, string>,
    active: dto.active,
    createdAt: new Date(dto.created_at),
  }
}
