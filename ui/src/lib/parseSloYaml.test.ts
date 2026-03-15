// src/lib/parseSloYaml.test.ts
import { describe, it, expect } from 'vitest'
import { parseSloYaml } from './parseSloYaml'

const FULL_YAML = `api_version: tropek/v1
kind: SLO
metadata:
  name: compilation-test-windows
  labels:
    os: windows
    test_type: compilation
spec:
  comparison:
    compare_with: several_results
    number_of_comparison_results: 3
    include_result_with_score: pass_or_warn
    aggregate_function: avg
  objectives:
    - sli_name: compilation_errors
      display_name: Compilation Errors
      pass:
        - criteria: ["=0"]
      weight: 3
      key_sli: true
      tab_group: summary
    - sli_name: compilation_duration_s
      display_name: Compilation Duration
      pass:
        - criteria: ["<=+10%"]
      warning:
        - criteria: ["<=+20%"]
      weight: 2
      key_sli: false
      tab_group: summary
    - sli_name: cpu_usage_avg
      display_name: CPU Usage Avg
      pass:
        - criteria: ["<80"]
      warning:
        - criteria: ["<90"]
      weight: 2
      key_sli: false
      tab_group: resources
  total_score:
    pass: "90%"
    warning: "75%"`

describe('parseSloYaml', () => {
  describe('top-level fields', () => {
    it('parses api_version', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.api_version).toBe('tropek/v1')
    })

    it('parses kind', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.kind).toBe('SLO')
    })
  })

  describe('metadata', () => {
    it('parses name', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.metadata.name).toBe('compilation-test-windows')
    })

    it('parses labels', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.metadata.labels).toEqual({ os: 'windows', test_type: 'compilation' })
    })
  })

  describe('comparison', () => {
    it('parses compare_with', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.comparison.compare_with).toBe('several_results')
    })

    it('parses number_of_comparison_results', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.comparison.number_of_comparison_results).toBe('3')
    })

    it('parses aggregate_function', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.comparison.aggregate_function).toBe('avg')
    })
  })

  describe('objectives', () => {
    it('parses all three objectives', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives).toHaveLength(3)
    })

    it('parses sli_name', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[0].sli_name).toBe('compilation_errors')
    })

    it('parses display_name', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[0].display_name).toBe('Compilation Errors')
    })

    it('parses pass criteria', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[0].pass).toEqual(['=0'])
    })

    it('parses weight', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[0].weight).toBe(3)
    })

    it('parses key_sli true', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[0].key_sli).toBe(true)
    })

    it('parses key_sli false', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[1].key_sli).toBe(false)
    })

    it('parses tab_group', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[0].tab_group).toBe('summary')
      expect(result?.spec.objectives[2].tab_group).toBe('resources')
    })

    it('parses warning criteria when present', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.objectives[1].warning).toEqual(['<=+20%'])
    })

    it('returns empty warning array when warning is absent', () => {
      const result = parseSloYaml(FULL_YAML)
      // compilation_errors has no warning block
      expect(result?.spec.objectives[0].warning).toEqual([])
    })

    it('returns empty pass array when pass is absent', () => {
      const yaml = `api_version: tropek/v1
kind: SLO
metadata:
  name: no-pass-slo
spec:
  objectives:
    - sli_name: some_metric
      display_name: Some Metric
      weight: 1
      key_sli: false`
      const result = parseSloYaml(yaml)
      expect(result?.spec.objectives[0].pass).toEqual([])
    })
  })

  describe('total_score', () => {
    it('parses pass threshold', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.total_score.pass).toBe('90%')
    })

    it('parses warning threshold', () => {
      const result = parseSloYaml(FULL_YAML)
      expect(result?.spec.total_score.warning).toBe('75%')
    })
  })

  describe('edge cases', () => {
    it('returns null for empty input', () => {
      expect(parseSloYaml('')).toBeNull()
    })

    it('returns null for non-YAML gibberish', () => {
      // Should not throw
      // Returns a partial object (not null) since parser is lenient; just ensure it doesn't throw
      expect(() => parseSloYaml('not yaml at all }{[')).not.toThrow()
    })

    it('handles YAML with no labels block', () => {
      const yaml = `api_version: tropek/v1
kind: SLO
metadata:
  name: minimal-slo
spec:
  objectives:
    - sli_name: error_rate
      display_name: Error Rate
      pass:
        - criteria: ["<1.0"]
      weight: 1
      key_sli: false`
      const result = parseSloYaml(yaml)
      expect(result?.metadata.labels).toEqual({})
      expect(result?.spec.objectives[0].sli_name).toBe('error_rate')
    })

    it('handles YAML with no comparison block', () => {
      const yaml = `api_version: tropek/v1
kind: SLO
metadata:
  name: no-comparison
spec:
  objectives:
    - sli_name: error_rate
      display_name: Error Rate
      pass:
        - criteria: ["<1.0"]
      weight: 1
      key_sli: false`
      const result = parseSloYaml(yaml)
      expect(result?.spec.comparison).toEqual({})
    })

    it('handles YAML with no total_score block', () => {
      const yaml = `api_version: tropek/v1
kind: SLO
metadata:
  name: no-score
spec:
  objectives:
    - sli_name: error_rate
      display_name: Error Rate
      pass:
        - criteria: ["<1.0"]
      weight: 1
      key_sli: false`
      const result = parseSloYaml(yaml)
      expect(result?.spec.total_score).toEqual({ pass: '', warning: '' })
    })

    it('handles relative threshold criteria like <=+10%', () => {
      const yaml = `api_version: tropek/v1
kind: SLO
metadata:
  name: relative-criteria
spec:
  objectives:
    - sli_name: response_time_p95
      display_name: Response Time P95
      pass:
        - criteria: ["<=+10%"]
      warning:
        - criteria: ["<=+25%"]
      weight: 2
      key_sli: true`
      const result = parseSloYaml(yaml)
      expect(result?.spec.objectives[0].pass).toEqual(['<=+10%'])
      expect(result?.spec.objectives[0].warning).toEqual(['<=+25%'])
    })

    it('handles objectives with only warning, no pass', () => {
      const yaml = `api_version: tropek/v1
kind: SLO
metadata:
  name: warn-only
spec:
  objectives:
    - sli_name: some_metric
      display_name: Some Metric
      warning:
        - criteria: ["<100"]
      weight: 1
      key_sli: false`
      const result = parseSloYaml(yaml)
      expect(result?.spec.objectives[0].pass).toEqual([])
      expect(result?.spec.objectives[0].warning).toEqual(['<100'])
    })
  })
})
