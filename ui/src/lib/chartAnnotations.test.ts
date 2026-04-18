import { describe, it, expect } from 'vitest'
import { buildNoteAnnotations } from './chartAnnotations'
import type { Annotation, TrendPoint } from '@/features/evaluations/domain'
import type { NoteCategory } from '@/features/note-categories'

const infoCat: NoteCategory = {
  id: 'info-id',
  name: 'info',
  label: 'Info',
  color: 'sky',
  showOnGraph: true,
  isSystem: false,
  createdAt: new Date(),
  updatedAt: null,
}
const failureCat: NoteCategory = {
  ...infoCat,
  id: 'fail-id',
  name: 'failure',
  label: 'Failure',
  color: 'red',
}
const hiddenCat: NoteCategory = {
  ...infoCat,
  id: 'hid-id',
  name: 'hidden',
  label: 'Hid',
  color: 'gray',
  showOnGraph: false,
}

function mkPoint(evalId: string, i: number): TrendPoint {
  return {
    timestamp: new Date(2026, 0, i + 1),
    value: 100 + i,
    score: 90,
    evalId,
    outcome: 'pass',
    baseline: null,
    evaluationName: null,
    targets: null,
    overridden: false,
  }
}

function mkAnnotation(id: string, runId: string, cat: NoteCategory): Annotation {
  return {
    id,
    sloEvaluationId: null,
    evaluationRunId: runId,
    content: 'note',
    author: null,
    categoryId: cat.id,
    category: cat,
    tags: {},
    noteGroupId: null,
    noteGroupName: null,
    hiddenAt: null,
    hiddenBy: null,
    hiddenReason: null,
    createdAt: new Date(),
    updatedAt: null,
  }
}

describe('buildNoteAnnotations', () => {
  it('emits nothing when no annotations', () => {
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map(),
      categoriesById: new Map(),
      chartWidth: 500,
    })
    expect(result.markLine.data).toEqual([])
    expect(result.markPoint.data).toEqual([])
    expect(result.labelBandPx).toBe(0)
  })

  it('filters categories with showOnGraph=false', () => {
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [mkAnnotation('n1', 'a', hiddenCat)]]]),
      categoriesById: new Map([[hiddenCat.id, hiddenCat]]),
      chartWidth: 500,
    })
    expect(result.markPoint.data).toEqual([])
    expect(result.labelBandPx).toBe(0)
  })

  it('emits one markPoint per noted eval with dominant category (alphabetical)', () => {
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([
        ['a', [mkAnnotation('n1', 'a', infoCat), mkAnnotation('n2', 'a', failureCat)]],
      ]),
      categoriesById: new Map([
        [infoCat.id, infoCat],
        [failureCat.id, failureCat],
      ]),
      chartWidth: 500,
    })
    expect(result.markPoint.data).toHaveLength(1)
    expect(result.markLine.data).toHaveLength(1)
    expect(result.labelBandPx).toBeGreaterThan(0)
    expect(result.markPoint.data[0].relativeTo).toBe('container')
  })

  it('shows annotation content as the label', () => {
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [mkAnnotation('n1', 'a', infoCat)]]]),
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 500,
    })
    expect(result.markPoint.data[0].label.formatter).toBe('note')
  })

  it('shows (+N) suffix when multiple notes on same eval', () => {
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([
        ['a', [mkAnnotation('n1', 'a', infoCat), mkAnnotation('n2', 'a', infoCat)]],
      ]),
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 500,
    })
    expect(result.markPoint.data[0].label.formatter).toBe('note (+1)')
  })

  it('clips overly long labels with ellipsis and keeps full text in tooltip', () => {
    const longContent =
      'this is a very long annotation that should be clipped in the label pill'
    const ann = { ...mkAnnotation('n1', 'a', infoCat), content: longContent }
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [ann]]]),
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 500,
    })
    const formatter = result.markPoint.data[0].label.formatter
    expect(formatter.endsWith('…')).toBe(true)
    expect(formatter.length).toBeLessThan(longContent.length)
    expect(result.markPoint.data[0].tooltip?.formatter).toContain(longContent)
  })

  it('omits fixed width so echarts auto-sizes the pill to the text', () => {
    const result = buildNoteAnnotations({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [mkAnnotation('n1', 'a', infoCat)]]]),
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 500,
    })
    const label = result.markPoint.data[0].label as unknown as Record<string, unknown>
    expect(label.width).toBeUndefined()
    expect(label.overflow).toBeUndefined()
  })

  it('staggers crowded labels across multiple rows', () => {
    const points = Array.from({ length: 10 }, (_, i) => mkPoint(`e${i}`, i))
    const anns = new Map(
      points.map(p => [p.evalId, [mkAnnotation(`n${p.evalId}`, p.evalId, infoCat)]]),
    )
    const result = buildNoteAnnotations({
      trendPoints: points,
      annotationsByEvalId: anns,
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 250,
    })
    const ys = new Set(result.markPoint.data.map(d => d.y))
    expect(ys.size).toBeGreaterThanOrEqual(2)
  })

  it('keeps well-spaced labels all on one row', () => {
    const points = Array.from({ length: 4 }, (_, i) => mkPoint(`e${i}`, i))
    const anns = new Map([
      [points[0].evalId, [mkAnnotation('n0', points[0].evalId, infoCat)]],
      [points[3].evalId, [mkAnnotation('n3', points[3].evalId, infoCat)]],
    ])
    const result = buildNoteAnnotations({
      trendPoints: points,
      annotationsByEvalId: anns,
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 1200,
    })
    const ys = new Set(result.markPoint.data.map(d => d.y))
    expect(ys.size).toBe(1)
  })

  it('places pixelX within the grid bounds', () => {
    const points = Array.from({ length: 5 }, (_, i) => mkPoint(`e${i}`, i))
    const anns = new Map([
      [points[0].evalId, [mkAnnotation('n0', points[0].evalId, infoCat)]],
      [points[4].evalId, [mkAnnotation('n4', points[4].evalId, infoCat)]],
    ])
    const result = buildNoteAnnotations({
      trendPoints: points,
      annotationsByEvalId: anns,
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 600,
    })
    const xs = result.markPoint.data.map(d => d.x)
    // label text 'note' (4 chars): estimated width ≈ 30px, halfLabel = 15.
    // Raw xs are 56 and 584; only the right one exceeds the clamp max of 583.
    expect(xs[0]).toBe(56)
    expect(xs[1]).toBe(583)
  })
})
