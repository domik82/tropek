// src/features/assets/types.ts
// Thin aliases over the generated OpenAPI types.
// DO NOT add fields here. If a field is missing, add it to the backend
// schema and regenerate: `just export-schema && just codegen`.
import type { components } from '@/generated/api'

type Schemas = components['schemas']

export type Asset = Schemas['AssetRead']
export type AssetType = Schemas['AssetTypeRead']
export type AssetGroup = Schemas['AssetGroupRead']
export type AssetGroupMember = Schemas['AssetGroupMemberRead']
export type AssetGroupSubgroup = Schemas['AssetGroupSubgroupRead']
export type AssetGroupTree = Schemas['AssetGroupTreeResponse']
export type TagKeyCount = Schemas['TagKeyCount']
export type TagValueCount = Schemas['TagValueCount']
