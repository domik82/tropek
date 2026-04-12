import type { components } from '@/generated/api'
import type { SloGroup } from './domain'

export type SloGroupDto = components['schemas']['SLOGroupRead']

// Placeholder for DTO fields intentionally not surfaced in the domain type.
// Add entries as `'field_name'` union members, each with a comment explaining why.
type DroppedSloGroupKeys =
  // Internal FK to the template SLO row; the UI navigates by `templateSloName`
  // + `templateSloVersion`, so the raw UUID is not useful in domain code.
  | 'template_slo_definition_id'

type MappedSloGroupKeys =
  | 'id'
  | 'name'
  | 'display_name'
  | 'template_slo_name'
  | 'template_slo_version'
  | 'gen_variables'
  | 'tags'
  | 'author'
  | 'version'
  | 'active'
  | 'created_at'
  | 'updated_at'
  | 'generated_slo_count'

// Compile-time check: every non-dropped DTO key must be mapped. If TypeScript
// errors here with a string literal type (e.g. `"new_field"`), the generated
// DTO has a new field — add it to `MappedSloGroupKeys` and map it in
// `dtoToSloGroup`, or add it to `DroppedSloGroupKeys` with a comment
// explaining why the UI intentionally ignores it.
type _SloGroupCoverage = Exclude<
  keyof SloGroupDto,
  MappedSloGroupKeys | DroppedSloGroupKeys
>
const _sloGroupExhaustive: _SloGroupCoverage extends never
  ? true
  : _SloGroupCoverage = true
void _sloGroupExhaustive

export function dtoToSloGroup(dto: SloGroupDto): SloGroup {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    templateSloName: dto.template_slo_name,
    templateSloVersion: dto.template_slo_version,
    genVariables: dto.gen_variables,
    // Backend guarantees string values; the OpenAPI schema widens to unknown.
    tags: dto.tags as Record<string, string>,
    author: dto.author,
    version: dto.version,
    active: dto.active,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
    generatedSloCount: dto.generated_slo_count,
  }
}
