import { describe, it, expect } from 'vitest'
import { buildNoteMarkPoint } from './chartAnnotations'
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

describe('buildNoteMarkPoint', () => {
  it('emits nothing when no annotations', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map(),
      categoriesById: new Map(),
      chartWidth: 500,
    })
    expect(mp.data).toEqual([])
  })

  it('filters categories with showOnGraph=false', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([['a', [mkAnnotation('n1', 'a', hiddenCat)]]]),
      categoriesById: new Map([[hiddenCat.id, hiddenCat]]),
      chartWidth: 500,
    })
    expect(mp.data).toEqual([])
  })

  it('emits one markPoint per noted eval with dominant category (alphabetical)', () => {
    const mp = buildNoteMarkPoint({
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
    expect(mp.data).toHaveLength(1)
    expect(mp.data[0].itemStyle.color).toContain('red')
  })

  it('hides labels when density is too high', () => {
    const points = Array.from({ length: 20 }, (_, i) => mkPoint(`e${i}`, i))
    const anns = new Map(
      points.map(p => [p.evalId, [mkAnnotation(`n${p.evalId}`, p.evalId, infoCat)]]),
    )
    const mp = buildNoteMarkPoint({
      trendPoints: points,
      annotationsByEvalId: anns,
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 600,
    })
    expect(mp.data[0].label.show).toBe(false)
  })

  it('shows labels with (n) suffix when multiple notes on same eval', () => {
    const mp = buildNoteMarkPoint({
      trendPoints: [mkPoint('a', 0)],
      annotationsByEvalId: new Map([
        ['a', [mkAnnotation('n1', 'a', infoCat), mkAnnotation('n2', 'a', infoCat)]],
      ]),
      categoriesById: new Map([[infoCat.id, infoCat]]),
      chartWidth: 500,
    })
    expect(mp.data[0].label.formatter).toBe('Info (2)')
  })
})
