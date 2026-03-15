// lib/parseSloYaml.ts
// Simple line-by-line parser for the TROPEK v1 SLO YAML format.
// Not a general-purpose YAML parser — handles only the known structure.

export interface ParsedObjective {
  sli_name: string
  display_name: string
  pass: string[]     // flattened criteria strings
  warning: string[]  // flattened criteria strings
  weight: number
  key_sli: boolean
  tab_group: string
}

export interface ParsedSloYaml {
  api_version: string
  kind: string
  metadata: {
    name: string
    labels: Record<string, string>
  }
  spec: {
    comparison: Record<string, string>
    objectives: ParsedObjective[]
    total_score: { pass: string; warning: string }
  }
}

function stripQuotes(s: string): string {
  return s.replace(/^["']|["']$/g, '').trim()
}

function extractValue(line: string): string {
  const idx = line.indexOf(':')
  if (idx === -1) return ''
  return stripQuotes(line.slice(idx + 1).trim())
}

export function parseSloYaml(yamlText: string): ParsedSloYaml | null {
  if (!yamlText.trim()) return null
  try {
    const lines = yamlText.split('\n')

    let api_version = ''
    let kind = ''
    const metadata: ParsedSloYaml['metadata'] = { name: '', labels: {} }
    const comparison: Record<string, string> = {}
    const objectives: ParsedObjective[] = []
    const total_score = { pass: '', warning: '' }

    type Section =
      | 'top'
      | 'metadata'
      | 'metadata.labels'
      | 'spec'
      | 'spec.comparison'
      | 'spec.objectives'
      | 'spec.total_score'

    let section: Section = 'top'
    let currentObj: ParsedObjective | null = null
    let objCriteriaSection: 'pass' | 'warning' | '' = ''

    function pushObj() {
      if (currentObj) {
        objectives.push(currentObj)
        currentObj = null
      }
    }

    for (const raw of lines) {
      const line = raw.trimEnd()
      if (!line.trim() || line.trim().startsWith('#')) continue

      // Top-level keys (no indent)
      if (/^api_version:/.test(line)) { api_version = extractValue(line); continue }
      if (/^kind:/.test(line)) { kind = extractValue(line); continue }
      if (/^metadata:/.test(line)) { section = 'metadata'; continue }
      if (/^spec:/.test(line)) { section = 'spec'; continue }

      // --- metadata ---
      if (section === 'metadata' || section === 'metadata.labels') {
        if (/^  name:/.test(line)) { metadata.name = extractValue(line); continue }
        if (/^  labels:/.test(line)) { section = 'metadata.labels'; continue }
        if (section === 'metadata.labels' && /^    \S/.test(line)) {
          const idx = line.indexOf(':')
          if (idx !== -1) {
            const k = line.slice(0, idx).trim()
            const v = stripQuotes(line.slice(idx + 1).trim())
            metadata.labels[k] = v
          }
          continue
        }
      }

      // --- spec ---
      if (section === 'spec') {
        if (/^  comparison:/.test(line)) { section = 'spec.comparison'; continue }
        if (/^  objectives:/.test(line)) { section = 'spec.objectives'; continue }
        if (/^  total_score:/.test(line)) { pushObj(); section = 'spec.total_score'; continue }
      }

      // --- spec.comparison ---
      if (section === 'spec.comparison') {
        if (/^    \S/.test(line)) {
          const idx = line.indexOf(':')
          if (idx !== -1) {
            const k = line.slice(0, idx).trim()
            const v = stripQuotes(line.slice(idx + 1).trim())
            comparison[k] = v
          }
          continue
        }
        // Leaving comparison section
        if (/^  \S/.test(line)) {
          if (/^  objectives:/.test(line)) { section = 'spec.objectives'; continue }
          if (/^  total_score:/.test(line)) { pushObj(); section = 'spec.total_score'; continue }
          section = 'spec'
        }
      }

      // --- spec.objectives ---
      if (section === 'spec.objectives') {
        // Leaving objectives
        if (/^  total_score:/.test(line)) { pushObj(); section = 'spec.total_score'; continue }
        if (/^  \S/.test(line) && !/^    /.test(line)) { pushObj(); section = 'spec'; continue }

        // New objective
        if (/^    - sli_name:/.test(line)) {
          pushObj()
          currentObj = {
            sli_name: extractValue(line),
            display_name: '',
            pass: [],
            warning: [],
            weight: 1,
            key_sli: false,
            tab_group: '',
          }
          objCriteriaSection = ''
          continue
        }

        if (currentObj) {
          if (/^      display_name:/.test(line)) {
            currentObj.display_name = extractValue(line)
            objCriteriaSection = ''
          } else if (/^      pass:/.test(line)) {
            objCriteriaSection = 'pass'
          } else if (/^      warning:/.test(line)) {
            objCriteriaSection = 'warning'
          } else if (/^      weight:/.test(line)) {
            currentObj.weight = parseFloat(extractValue(line)) || 1
            objCriteriaSection = ''
          } else if (/^      key_sli:/.test(line)) {
            currentObj.key_sli = extractValue(line) === 'true'
            objCriteriaSection = ''
          } else if (/^      tab_group:/.test(line)) {
            currentObj.tab_group = extractValue(line)
            objCriteriaSection = ''
          } else if (/^        - criteria:/.test(line) && objCriteriaSection) {
            // criteria: ["<=+10%"] or criteria: [<=+10%]
            const m = line.match(/criteria:\s*\[["']?([^"'\]]+)["']?\]/)
            if (m && objCriteriaSection === 'pass') currentObj.pass.push(m[1].trim())
            if (m && objCriteriaSection === 'warning') currentObj.warning.push(m[1].trim())
          }
        }
        continue
      }

      // --- spec.total_score ---
      if (section === 'spec.total_score') {
        if (/^    pass:/.test(line)) total_score.pass = extractValue(line)
        if (/^    warning:/.test(line)) total_score.warning = extractValue(line)
      }
    }

    pushObj()

    return { api_version, kind, metadata, spec: { comparison, objectives, total_score } }
  } catch {
    return null
  }
}
