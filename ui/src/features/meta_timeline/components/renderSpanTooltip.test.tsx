import { describe, expect, it } from 'vitest'
import { decodeGroupLabel, escapeHtml, renderSpanTooltip } from './renderSpanTooltip'

function makeItem(
  overrides: Partial<{
    group: string
    content: string
    start: string
    end: string
    className: string
    source: string
  }> = {},
) {
  return {
    group: '["app"]',
    content: '1.0',
    start: '2026-04-01T00:00:00Z',
    end: '2026-04-30T00:00:00Z',
    className: 'meta-span',
    source: 'cicd',
    ...overrides,
  }
}

describe('renderSpanTooltip', () => {
  it('renders plain meta-span tooltip without annotations', () => {
    const result = renderSpanTooltip(makeItem())
    expect(result).toContain('From:')
    expect(result).toContain('To:')
    expect(result).not.toContain('(started before window)')
    expect(result).not.toContain('(still open)')
    expect(result).not.toContain('(continues after window)')
    expect(result).not.toContain('(explicit closure)')
  })

  it('renders clipped-left annotation on From line', () => {
    const result = renderSpanTooltip(makeItem({ className: 'meta-span meta-span-clipped-left' }))
    expect(result).toContain('From:')
    expect(result).toContain('(started before window)')
  })

  it('renders still open annotation on To line', () => {
    const result = renderSpanTooltip(makeItem({ className: 'meta-span meta-span-open' }))
    expect(result).toContain('To:')
    expect(result).toContain('(still open)')
  })

  it('renders continues after window annotation on To line', () => {
    const result = renderSpanTooltip(makeItem({ className: 'meta-span meta-span-clipped-right' }))
    expect(result).toContain('To:')
    expect(result).toContain('(continues after window)')
  })

  it('renders explicit closure annotation on To line', () => {
    const result = renderSpanTooltip(makeItem({ className: 'meta-span meta-span-closed' }))
    expect(result).toContain('To:')
    expect(result).toContain('(explicit closure)')
  })
})

describe('escapeHtml', () => {
  it('escapes script tags', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;')
  })

  it('escapes ampersands', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b')
  })
})

describe('decodeGroupLabel', () => {
  it('decodes JSON path array to human-readable label', () => {
    expect(decodeGroupLabel('["app-A","plugin-alpha"]')).toBe('app-A > plugin-alpha')
  })

  it('falls back to raw string for malformed JSON', () => {
    expect(decodeGroupLabel('not-json')).toBe('not-json')
  })
})
