import { describe, it, expect } from 'vitest'
import { parseCriteria, serializeCriteria, type CriteriaParts } from './criteriaUtils'

describe('parseCriteria', () => {
  it('parses fixed threshold: <600', () => {
    expect(parseCriteria('<600')).toEqual({
      operator: '<', sign: null, value: 600, percent: false,
    })
  })

  it('parses relative percent: <=+10%', () => {
    expect(parseCriteria('<=+10%')).toEqual({
      operator: '<=', sign: '+', value: 10, percent: true,
    })
  })

  it('parses relative negative percent: >=-5%', () => {
    expect(parseCriteria('>=-5%')).toEqual({
      operator: '>=', sign: '-', value: 5, percent: true,
    })
  })

  it('parses relative absolute: <=+50', () => {
    expect(parseCriteria('<=+50')).toEqual({
      operator: '<=', sign: '+', value: 50, percent: false,
    })
  })

  it('parses equality: =100', () => {
    expect(parseCriteria('=100')).toEqual({
      operator: '=', sign: null, value: 100, percent: false,
    })
  })

  it('parses decimal values: <99.5', () => {
    expect(parseCriteria('<99.5')).toEqual({
      operator: '<', sign: null, value: 99.5, percent: false,
    })
  })

  it('returns null for invalid input', () => {
    expect(parseCriteria('')).toBeNull()
    expect(parseCriteria('abc')).toBeNull()
    expect(parseCriteria('<=+%')).toBeNull()
  })
})

describe('serializeCriteria', () => {
  it('serializes fixed threshold', () => {
    expect(serializeCriteria({ operator: '<', sign: null, value: 600, percent: false }))
      .toBe('<600')
  })

  it('serializes relative percent', () => {
    expect(serializeCriteria({ operator: '<=', sign: '+', value: 10, percent: true }))
      .toBe('<=+10%')
  })

  it('serializes relative negative percent', () => {
    expect(serializeCriteria({ operator: '>=', sign: '-', value: 5, percent: true }))
      .toBe('>=-5%')
  })

  it('serializes relative absolute', () => {
    expect(serializeCriteria({ operator: '<=', sign: '+', value: 50, percent: false }))
      .toBe('<=+50')
  })
})
