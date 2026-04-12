import type { components } from '@/generated/api'
import type {
  Asset,
  AssetGroup,
  AssetGroupMember,
  AssetGroupSubgroup,
  AssetGroupTree,
  AssetType,
} from './domain'

export type AssetDto = components['schemas']['AssetRead']
export type AssetTypeDto = components['schemas']['AssetTypeRead']
export type AssetGroupDto = components['schemas']['AssetGroupRead']
export type AssetGroupMemberDto = components['schemas']['AssetGroupMemberRead']
export type AssetGroupSubgroupDto = components['schemas']['AssetGroupSubgroupRead']
export type AssetGroupTreeDto = components['schemas']['AssetGroupTreeResponse']

// --- Asset -----------------------------------------------------------------

// Placeholder for DTO fields intentionally not surfaced in the domain type.
// Add entries as `'field_name'` union members, each with a comment explaining why.
type DroppedAssetKeys = never

type MappedAssetKeys =
  | 'id'
  | 'name'
  | 'display_name'
  | 'type_name'
  | 'color'
  | 'tags'
  | 'variables'
  | 'heatmap_config'
  | 'created_at'
  | 'updated_at'

// Compile-time check: every non-dropped DTO key must be mapped. If TypeScript
// errors here with a string literal type, the generated DTO has a new field —
// add it to `MappedAssetKeys` and map it in `dtoToAsset`, or add it to
// `DroppedAssetKeys` with a comment explaining why the UI ignores it.
type _AssetCoverage = Exclude<keyof AssetDto, MappedAssetKeys | DroppedAssetKeys>
const _assetExhaustive: _AssetCoverage extends never ? true : _AssetCoverage = true
void _assetExhaustive

// --- AssetType -------------------------------------------------------------

type DroppedAssetTypeKeys = never

type MappedAssetTypeKeys = 'id' | 'name' | 'is_default' | 'asset_count'

type _AssetTypeCoverage = Exclude<keyof AssetTypeDto, MappedAssetTypeKeys | DroppedAssetTypeKeys>
const _assetTypeExhaustive: _AssetTypeCoverage extends never ? true : _AssetTypeCoverage = true
void _assetTypeExhaustive

// --- AssetGroup ------------------------------------------------------------

type DroppedAssetGroupKeys = never

type MappedAssetGroupKeys =
  | 'id'
  | 'name'
  | 'display_name'
  | 'description'
  | 'color'
  | 'members'
  | 'subgroups'
  | 'created_at'
  | 'updated_at'

type _AssetGroupCoverage = Exclude<
  keyof AssetGroupDto,
  MappedAssetGroupKeys | DroppedAssetGroupKeys
>
const _assetGroupExhaustive: _AssetGroupCoverage extends never ? true : _AssetGroupCoverage = true
void _assetGroupExhaustive

// --- AssetGroupMember ------------------------------------------------------

type DroppedAssetGroupMemberKeys = never

type MappedAssetGroupMemberKeys =
  | 'asset_id'
  | 'asset_name'
  | 'asset_display_name'
  | 'asset_type_name'
  | 'weight'

type _AssetGroupMemberCoverage = Exclude<
  keyof AssetGroupMemberDto,
  MappedAssetGroupMemberKeys | DroppedAssetGroupMemberKeys
>
const _assetGroupMemberExhaustive: _AssetGroupMemberCoverage extends never
  ? true
  : _AssetGroupMemberCoverage = true
void _assetGroupMemberExhaustive

// --- AssetGroupSubgroup ----------------------------------------------------

type DroppedAssetGroupSubgroupKeys = never

type MappedAssetGroupSubgroupKeys = 'group_id' | 'group_name' | 'weight'

type _AssetGroupSubgroupCoverage = Exclude<
  keyof AssetGroupSubgroupDto,
  MappedAssetGroupSubgroupKeys | DroppedAssetGroupSubgroupKeys
>
const _assetGroupSubgroupExhaustive: _AssetGroupSubgroupCoverage extends never
  ? true
  : _AssetGroupSubgroupCoverage = true
void _assetGroupSubgroupExhaustive

// --- AssetGroupTree --------------------------------------------------------

type DroppedAssetGroupTreeKeys = never

type MappedAssetGroupTreeKeys = 'top_level' | 'all_groups'

type _AssetGroupTreeCoverage = Exclude<
  keyof AssetGroupTreeDto,
  MappedAssetGroupTreeKeys | DroppedAssetGroupTreeKeys
>
const _assetGroupTreeExhaustive: _AssetGroupTreeCoverage extends never
  ? true
  : _AssetGroupTreeCoverage = true
void _assetGroupTreeExhaustive

// --- Mappers ---------------------------------------------------------------

export function dtoToAsset(dto: AssetDto): Asset {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    typeName: dto.type_name,
    color: dto.color ?? null,
    // Backend guarantees string values; OpenAPI widens to unknown in some generators.
    tags: dto.tags as Record<string, string>,
    variables: dto.variables as Record<string, string>,
    // heatmap_config stays opaque per §15.4 of the UI layering spec. Design
    // deferred — see memory note project_heatmap_config_investigation.md.
    heatmapConfig: (dto.heatmap_config ?? null) as Record<string, unknown> | null,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}

export function dtoToAssetType(dto: AssetTypeDto): AssetType {
  return {
    id: dto.id,
    name: dto.name,
    isDefault: dto.is_default,
    assetCount: dto.asset_count,
  }
}

function dtoToAssetGroupMember(dto: AssetGroupMemberDto): AssetGroupMember {
  return {
    assetId: dto.asset_id,
    assetName: dto.asset_name,
    assetDisplayName: dto.asset_display_name ?? null,
    assetTypeName: dto.asset_type_name,
    weight: dto.weight,
  }
}

function dtoToAssetGroupSubgroup(dto: AssetGroupSubgroupDto): AssetGroupSubgroup {
  return {
    groupId: dto.group_id,
    groupName: dto.group_name,
    weight: dto.weight,
  }
}

export function dtoToAssetGroup(dto: AssetGroupDto): AssetGroup {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    description: dto.description,
    color: dto.color ?? null,
    members: dto.members.map(dtoToAssetGroupMember),
    subgroups: dto.subgroups.map(dtoToAssetGroupSubgroup),
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}

export function dtoToAssetGroupTree(dto: AssetGroupTreeDto): AssetGroupTree {
  return {
    topLevel: dto.top_level.map(dtoToAssetGroup),
    allGroups: dto.all_groups.map(dtoToAssetGroup),
  }
}
