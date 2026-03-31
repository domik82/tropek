export const ENTITY_NAME_PATTERN = /^[a-z0-9-]+$/
export function isValidEntityName(name: string): boolean {
  return name.length > 0 && ENTITY_NAME_PATTERN.test(name)
}
export const ENTITY_NAME_HINT = 'lowercase letters, numbers, hyphens only'
