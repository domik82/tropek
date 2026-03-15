/**
 * Deterministic mock data generator — 30 days × 30 metrics × multiple assets per lab.
 * Uses a seeded LCG so output is identical on every page reload.
 */

import type { EvaluationSummary, EvaluationDetail, IndicatorResult, TrendPoint, FailingIndicator } from '../features/evaluations/types'
import { computeChangePct } from '../utils/metrics'

// ---------------------------------------------------------------------------
// Seeded pseudo-random
// ---------------------------------------------------------------------------
function makePrng(seed: number) {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff
    return (s >>> 0) / 0xffffffff
  }
}

// ---------------------------------------------------------------------------
// Metric catalogue  (30 metrics, grouped into tabs)
// ---------------------------------------------------------------------------
export type MetricDef = {
  name: string
  display_name: string
  tab_group: string        // drives UI tab generation
  key_sli: boolean
  weight: number
  unit: string
  base: number             // realistic baseline value
  pass_criteria: string    // e.g. "=0", "<600", "<=+10%"
  warn_criteria: string | null
  higher_is_worse: boolean // true for latency/errors; false for throughput
}

export const METRICS: MetricDef[] = [
  // ---- Summary (key indicators) ----------------------------------------
  { name: 'compilation_errors',    display_name: 'Compilation Errors',    tab_group: 'summary',   key_sli: true,  weight: 3, unit: '',    base: 0,    pass_criteria: '=0',      warn_criteria: null,       higher_is_worse: true  },
  { name: 'compilation_duration_s',display_name: 'Compilation Duration',  tab_group: 'summary',   key_sli: false, weight: 2, unit: 's',   base: 42,   pass_criteria: '<=+10%',  warn_criteria: '<=+20%',   higher_is_worse: true  },
  { name: 'error_rate',            display_name: 'Error Rate',            tab_group: 'summary',   key_sli: true,  weight: 3, unit: '%',   base: 0.5,  pass_criteria: '<1.0',    warn_criteria: '<2.0',     higher_is_worse: true  },
  { name: 'throughput_rps',        display_name: 'Throughput',            tab_group: 'summary',   key_sli: false, weight: 2, unit: 'rps', base: 1520, pass_criteria: '>1200',   warn_criteria: '>1000',    higher_is_worse: false },
  // ---- Timing --------------------------------------------------------------
  { name: 'response_time_p50',     display_name: 'Response Time P50',     tab_group: 'timing',    key_sli: false, weight: 1, unit: 'ms',  base: 120,  pass_criteria: '<200',    warn_criteria: '<350',     higher_is_worse: true  },
  { name: 'response_time_p75',     display_name: 'Response Time P75',     tab_group: 'timing',    key_sli: false, weight: 1, unit: 'ms',  base: 200,  pass_criteria: '<300',    warn_criteria: '<450',     higher_is_worse: true  },
  { name: 'response_time_p90',     display_name: 'Response Time P90',     tab_group: 'timing',    key_sli: false, weight: 1, unit: 'ms',  base: 320,  pass_criteria: '<450',    warn_criteria: '<600',     higher_is_worse: true  },
  { name: 'response_time_p95',     display_name: 'Response Time P95',     tab_group: 'timing',    key_sli: false, weight: 1, unit: 'ms',  base: 420,  pass_criteria: '<550',    warn_criteria: '<700',     higher_is_worse: true  },
  { name: 'response_time_p99',     display_name: 'Response Time P99',     tab_group: 'timing',    key_sli: true,  weight: 2, unit: 'ms',  base: 580,  pass_criteria: '<=+10%',  warn_criteria: '<900',     higher_is_worse: true  },
  { name: 'compilation_phase1_s',  display_name: 'Compile Phase 1',       tab_group: 'timing',    key_sli: false, weight: 1, unit: 's',   base: 18,   pass_criteria: '<=+10%',  warn_criteria: '<=+20%',   higher_is_worse: true  },
  { name: 'compilation_phase2_s',  display_name: 'Compile Phase 2',       tab_group: 'timing',    key_sli: false, weight: 1, unit: 's',   base: 15,   pass_criteria: '<=+10%',  warn_criteria: '<=+20%',   higher_is_worse: true  },
  { name: 'link_duration_s',       display_name: 'Link Duration',         tab_group: 'timing',    key_sli: false, weight: 1, unit: 's',   base: 8,    pass_criteria: '<=+10%',  warn_criteria: '<=+20%',   higher_is_worse: true  },
  // ---- Resources -----------------------------------------------------------
  { name: 'cpu_usage_avg',         display_name: 'CPU Usage Avg',         tab_group: 'resources', key_sli: false, weight: 2, unit: '%',   base: 68,   pass_criteria: '<80',     warn_criteria: '<90',      higher_is_worse: true  },
  { name: 'cpu_usage_max',         display_name: 'CPU Usage Max',         tab_group: 'resources', key_sli: false, weight: 1, unit: '%',   base: 85,   pass_criteria: '<95',     warn_criteria: null,       higher_is_worse: true  },
  { name: 'memory_peak_mb',        display_name: 'Peak Memory',           tab_group: 'resources', key_sli: false, weight: 2, unit: 'MB',  base: 1024, pass_criteria: '<2048',   warn_criteria: null,       higher_is_worse: true  },
  { name: 'memory_avg_mb',         display_name: 'Avg Memory',            tab_group: 'resources', key_sli: false, weight: 1, unit: 'MB',  base: 820,  pass_criteria: '<1536',   warn_criteria: null,       higher_is_worse: true  },
  { name: 'disk_io_read_mbps',     display_name: 'Disk Read',             tab_group: 'resources', key_sli: false, weight: 1, unit: 'MB/s',base: 145,  pass_criteria: '<200',    warn_criteria: null,       higher_is_worse: true  },
  { name: 'disk_io_write_mbps',    display_name: 'Disk Write',            tab_group: 'resources', key_sli: false, weight: 1, unit: 'MB/s',base: 68,   pass_criteria: '<100',    warn_criteria: null,       higher_is_worse: true  },
  { name: 'swap_usage_mb',         display_name: 'Swap Usage',            tab_group: 'resources', key_sli: false, weight: 1, unit: 'MB',  base: 32,   pass_criteria: '<256',    warn_criteria: null,       higher_is_worse: true  },
  // ---- Network -------------------------------------------------------------
  { name: 'network_rx_mbps',       display_name: 'Network RX',            tab_group: 'network',   key_sli: false, weight: 1, unit: 'Mbps',base: 220,  pass_criteria: '>180',    warn_criteria: '>150',     higher_is_worse: false },
  { name: 'network_tx_mbps',       display_name: 'Network TX',            tab_group: 'network',   key_sli: false, weight: 1, unit: 'Mbps',base: 85,   pass_criteria: '>70',     warn_criteria: '>55',      higher_is_worse: false },
  { name: 'packet_loss_pct',       display_name: 'Packet Loss',           tab_group: 'network',   key_sli: true,  weight: 2, unit: '%',   base: 0.01, pass_criteria: '<0.1',    warn_criteria: '<0.5',     higher_is_worse: true  },
  { name: 'tcp_retransmit_rate',   display_name: 'TCP Retransmit Rate',   tab_group: 'network',   key_sli: false, weight: 1, unit: '%',   base: 0.3,  pass_criteria: '<1.0',    warn_criteria: null,       higher_is_worse: true  },
  { name: 'dns_lookup_ms',         display_name: 'DNS Lookup',            tab_group: 'network',   key_sli: false, weight: 1, unit: 'ms',  base: 8,    pass_criteria: '<50',     warn_criteria: null,       higher_is_worse: true  },
  { name: 'connection_errors',     display_name: 'Connection Errors',     tab_group: 'network',   key_sli: true,  weight: 2, unit: '',    base: 0,    pass_criteria: '=0',      warn_criteria: null,       higher_is_worse: true  },
  // ---- Errors --------------------------------------------------------------
  { name: 'link_errors',           display_name: 'Link Errors',           tab_group: 'errors',    key_sli: true,  weight: 3, unit: '',    base: 0,    pass_criteria: '=0',      warn_criteria: null,       higher_is_worse: true  },
  { name: 'test_failures',         display_name: 'Test Failures',         tab_group: 'errors',    key_sli: true,  weight: 3, unit: '',    base: 0,    pass_criteria: '=0',      warn_criteria: null,       higher_is_worse: true  },
  { name: 'warnings_count',        display_name: 'Compiler Warnings',     tab_group: 'errors',    key_sli: false, weight: 1, unit: '',    base: 3,    pass_criteria: '<10',     warn_criteria: '<20',      higher_is_worse: true  },
  { name: 'crash_count',           display_name: 'Crashes',               tab_group: 'errors',    key_sli: true,  weight: 3, unit: '',    base: 0,    pass_criteria: '=0',      warn_criteria: null,       higher_is_worse: true  },
  { name: 'assert_failures',       display_name: 'Assert Failures',       tab_group: 'errors',    key_sli: true,  weight: 2, unit: '',    base: 0,    pass_criteria: '=0',      warn_criteria: null,       higher_is_worse: true  },
]

// ---------------------------------------------------------------------------
// Test / asset catalogue
// ---------------------------------------------------------------------------
type RegressionSpec = { start: number; end: number; factor: number } | null

type Scenario = {
  test: string
  asset: string
  group: string
  os: string
  arch: string
  slo: string
  seed: number
  regression: RegressionSpec
  runs_per_day: number
}

const SCENARIOS: Scenario[] = [
  // --- monthly-lab -----------------------------------------------------------
  { test: 'compilation-test', asset: 'win-monthly-01',   group: 'monthly-lab', os: 'windows-11',   arch: 'x64',   slo: 'compilation-test-windows', seed: 1001, regression: { start: 18, end: 22, factor: 1.35 }, runs_per_day: 1 },
  { test: 'compilation-test', asset: 'linux-monthly-01', group: 'monthly-lab', os: 'ubuntu-22.04', arch: 'x64',   slo: 'compilation-test-linux',   seed: 1002, regression: null,                                  runs_per_day: 1 },
  { test: 'compilation-test', asset: 'mac-monthly-01',   group: 'monthly-lab', os: 'macos-14',     arch: 'arm64', slo: 'compilation-test-macos',   seed: 1003, regression: { start: 24, end: 26, factor: 1.2 },   runs_per_day: 1 },

  // --- toolset-lab (mild regressions) ----------------------------------------
  { test: 'compilation-test', asset: 'win-toolset-01',   group: 'toolset-lab', os: 'windows-11',   arch: 'x64',   slo: 'compilation-test-windows', seed: 2001, regression: { start: 15, end: 17, factor: 1.15 }, runs_per_day: 1 },
  { test: 'compilation-test', asset: 'linux-toolset-01', group: 'toolset-lab', os: 'ubuntu-22.04', arch: 'x64',   slo: 'compilation-test-linux',   seed: 2002, regression: { start: 22, end: 23, factor: 1.12 }, runs_per_day: 1 },
  { test: 'compilation-test', asset: 'mac-toolset-01',   group: 'toolset-lab', os: 'macos-14',     arch: 'arm64', slo: 'compilation-test-macos',   seed: 2003, regression: null,                                  runs_per_day: 1 },

  // --- ad-hoc-lab-1 (more failures) ------------------------------------------
  { test: 'compilation-test', asset: 'win-adhoc-01',   group: 'ad-hoc-lab-1', os: 'windows-10',   arch: 'x64', slo: 'compilation-test-windows', seed: 3001, regression: { start: 10, end: 15, factor: 1.8 }, runs_per_day: 1 },
  { test: 'compilation-test', asset: 'linux-adhoc-01', group: 'ad-hoc-lab-1', os: 'ubuntu-22.04', arch: 'x64', slo: 'compilation-test-linux',   seed: 3002, regression: { start: 5,  end: 8,  factor: 1.6 }, runs_per_day: 1 },
  { test: 'compilation-test', asset: 'win-adhoc-02',   group: 'ad-hoc-lab-1', os: 'windows-7',    arch: 'x86', slo: 'compilation-test-windows', seed: 3003, regression: { start: 20, end: 26, factor: 1.75}, runs_per_day: 1 },

  // --- performance-lab-1 linux (2 runs/day) -----------------------------------
  { test: 'load-test', asset: 'centos79-pl1-01',  group: 'performance-lab-1', os: 'centos-7.9',   arch: 'x64', slo: 'load-test-linux', seed: 4001, regression: { start: 20, end: 23, factor: 1.3 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'rocky8-pl1-01',    group: 'performance-lab-1', os: 'rocky-8',      arch: 'x64', slo: 'load-test-linux', seed: 4002, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'rocky9-pl1-01',    group: 'performance-lab-1', os: 'rocky-9',      arch: 'x64', slo: 'load-test-linux', seed: 4003, regression: { start: 14, end: 16, factor: 1.2 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'rocky10-pl1-01',   group: 'performance-lab-1', os: 'rocky-10',     arch: 'x64', slo: 'load-test-linux', seed: 4004, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'ubuntu22-pl1-01',  group: 'performance-lab-1', os: 'ubuntu-22.04', arch: 'x64', slo: 'load-test-linux', seed: 4005, regression: { start: 25, end: 27, factor: 1.25}, runs_per_day: 2 },
  { test: 'load-test', asset: 'ubuntu24-pl1-01',  group: 'performance-lab-1', os: 'ubuntu-24.04', arch: 'x64', slo: 'load-test-linux', seed: 4006, regression: null,                                runs_per_day: 2 },

  // --- performance-lab-1 windows (2 runs/day) ----------------------------------
  { test: 'load-test', asset: 'win7-pl1-01',      group: 'performance-lab-1', os: 'windows-7',          arch: 'x86', slo: 'load-test-windows', seed: 4101, regression: { start: 18, end: 22, factor: 1.4 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'win10-32-pl1-01',  group: 'performance-lab-1', os: 'windows-10',         arch: 'x86', slo: 'load-test-windows', seed: 4102, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'win10-64-pl1-01',  group: 'performance-lab-1', os: 'windows-10',         arch: 'x64', slo: 'load-test-windows', seed: 4103, regression: { start: 12, end: 14, factor: 1.2 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'win11-pl1-01',     group: 'performance-lab-1', os: 'windows-11',         arch: 'x64', slo: 'load-test-windows', seed: 4104, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'winsrv22-pl1-01',  group: 'performance-lab-1', os: 'windows-server-2022',arch: 'x64', slo: 'load-test-windows', seed: 4105, regression: { start: 8,  end: 10, factor: 1.35}, runs_per_day: 2 },

  // --- performance-lab-2 linux (2 runs/day) -----------------------------------
  { test: 'load-test', asset: 'centos79-pl2-01',  group: 'performance-lab-2', os: 'centos-7.9',   arch: 'x64', slo: 'load-test-linux', seed: 5001, regression: { start: 22, end: 25, factor: 1.3 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'rocky8-pl2-01',    group: 'performance-lab-2', os: 'rocky-8',      arch: 'x64', slo: 'load-test-linux', seed: 5002, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'rocky9-pl2-01',    group: 'performance-lab-2', os: 'rocky-9',      arch: 'x64', slo: 'load-test-linux', seed: 5003, regression: { start: 16, end: 18, factor: 1.2 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'rocky10-pl2-01',   group: 'performance-lab-2', os: 'rocky-10',     arch: 'x64', slo: 'load-test-linux', seed: 5004, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'ubuntu22-pl2-01',  group: 'performance-lab-2', os: 'ubuntu-22.04', arch: 'x64', slo: 'load-test-linux', seed: 5005, regression: { start: 27, end: 29, factor: 1.25}, runs_per_day: 2 },
  { test: 'load-test', asset: 'ubuntu24-pl2-01',  group: 'performance-lab-2', os: 'ubuntu-24.04', arch: 'x64', slo: 'load-test-linux', seed: 5006, regression: null,                                runs_per_day: 2 },

  // --- performance-lab-2 windows (2 runs/day) ----------------------------------
  { test: 'load-test', asset: 'win7-pl2-01',      group: 'performance-lab-2', os: 'windows-7',          arch: 'x86', slo: 'load-test-windows', seed: 5101, regression: { start: 20, end: 24, factor: 1.4 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'win10-32-pl2-01',  group: 'performance-lab-2', os: 'windows-10',         arch: 'x86', slo: 'load-test-windows', seed: 5102, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'win10-64-pl2-01',  group: 'performance-lab-2', os: 'windows-10',         arch: 'x64', slo: 'load-test-windows', seed: 5103, regression: { start: 14, end: 16, factor: 1.2 }, runs_per_day: 2 },
  { test: 'load-test', asset: 'win11-pl2-01',     group: 'performance-lab-2', os: 'windows-11',         arch: 'x64', slo: 'load-test-windows', seed: 5104, regression: null,                                runs_per_day: 2 },
  { test: 'load-test', asset: 'winsrv22-pl2-01',  group: 'performance-lab-2', os: 'windows-server-2022',arch: 'x64', slo: 'load-test-windows', seed: 5105, regression: { start: 10, end: 12, factor: 1.35}, runs_per_day: 2 },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
// Run 0 = 06:00, run 1 = 14:00, run 2 = 22:00
const RUN_HOURS = [6, 14, 22]

function isoDate(daysAgo: number, runIndex: number = 0): string {
  const d = new Date('2026-03-14T10:46:00Z')
  d.setDate(d.getDate() - (29 - daysAgo))
  const hour = RUN_HOURS[runIndex] ?? 6
  d.setUTCHours(hour, 0, 0, 0)
  return d.toISOString().slice(0, 19) + 'Z'
}

function checkFixed(value: number, criteria: string): boolean {
  const m = criteria.match(/^([<>]=?|=)([\d.]+)$/)
  if (!m) return true
  const [, op, raw] = m
  const threshold = parseFloat(raw)
  if (op === '=')  return Math.abs(value - threshold) < 0.001
  if (op === '<')  return value < threshold
  if (op === '<=') return value <= threshold
  if (op === '>')  return value > threshold
  if (op === '>=') return value >= threshold
  return true
}

function checkRelative(value: number, baseline: number, criteria: string): boolean {
  const m = criteria.match(/^<=\+(\d+)%$/)
  if (!m) return true
  const pctAllowed = parseFloat(m[1])
  return value <= baseline * (1 + pctAllowed / 100)
}

function scoreIndicator(
  metric: MetricDef,
  value: number,
  baseline: number | null
): { status: 'pass' | 'warning' | 'fail'; score: number } {
  const isRelative = metric.pass_criteria.startsWith('<=+') || metric.pass_criteria.startsWith('>=-')
  const passCrit = metric.pass_criteria
  const warnCrit = metric.warn_criteria

  let passOk: boolean
  if (isRelative && baseline != null) {
    passOk = checkRelative(value, baseline, passCrit)
  } else if (!isRelative) {
    passOk = checkFixed(value, passCrit)
  } else {
    passOk = true  // no baseline yet
  }

  if (passOk) return { status: 'pass', score: metric.weight }

  const warnOk = warnCrit ? checkFixed(value, warnCrit) : false
  if (warnOk) return { status: 'warning', score: metric.weight * 0.5 }

  return { status: 'fail', score: 0 }
}

// ---------------------------------------------------------------------------
// Core generator
// ---------------------------------------------------------------------------
export function generateAllEvaluations(): EvaluationSummary[] {
  const all: EvaluationSummary[] = []

  for (const scenario of SCENARIOS) {
    const rand = makePrng(scenario.seed)
    const history: number[] = []  // running baseline for first relative metric

    for (let day = 0; day < 30; day++) {
      const regFactor =
        scenario.regression &&
        day >= scenario.regression.start &&
        day <= scenario.regression.end
          ? scenario.regression.factor
          : 1.0

      // noise factor 0.9–1.1 normally, but push higher during regression
      const noise = 0.97 + rand() * 0.06

      // Score proxy: use compilation_duration as a proxy for overall health
      const durBase = METRICS.find(m => m.name === 'compilation_duration_s')!.base
      const dur = +(durBase * regFactor * noise).toFixed(2)
      const baselineDur = history.length >= 3 ? history.slice(-3).reduce((a, b) => a + b, 0) / 3 : null
      history.push(dur)

      let result: 'pass' | 'warning' | 'fail' = 'pass'
      let score = 90 + rand() * 8

      if (regFactor > 1.3) {
        result = 'fail'
        score = 40 + rand() * 25
      } else if (regFactor > 1.1 || (baselineDur != null && dur > baselineDur * 1.15)) {
        result = 'warning'
        score = 70 + rand() * 10
      }

      // day 5 of the regression also has 1 error
      const hasError = scenario.regression && day === scenario.regression.start + 2

      // top_failures: when warning or fail, include actual values and thresholds
      let top_failures: FailingIndicator[] | undefined
      if (result === 'fail' || result === 'warning') {
        const keySlis = METRICS.filter(m => m.key_sli)
        const failRand = makePrng(scenario.seed + day * 31 + 7)
        const count = result === 'fail' ? Math.min(3, 1 + Math.floor(failRand() * 3)) : 1
        const noiseF = 0.96 + failRand() * 0.08
        top_failures = keySlis
          .sort(() => failRand() - 0.5)
          .slice(0, count)
          .map(m => {
            let value: number
            if (m.base === 0) {
              value = regFactor > 1.3 ? Math.max(1, Math.floor(failRand() * 5)) : 1
            } else if (m.higher_is_worse) {
              value = +(m.base * regFactor * noiseF).toFixed(m.unit === 'ms' ? 0 : 2)
            } else {
              value = +(m.base / (regFactor * noiseF)).toFixed(2)
            }
            const thresholdStr = m.pass_criteria.startsWith('<=+')
              ? `baseline ${m.pass_criteria}`
              : `${m.pass_criteria}${m.unit ? ' ' + m.unit : ''}`
            return {
              metric: m.name,
              display_name: m.display_name,
              value,
              unit: m.unit,
              threshold: thresholdStr,
            }
          })
      }

      const runsPerDay = scenario.runs_per_day ?? 1

      for (let run = 0; run < runsPerDay; run++) {
        const runNoise = runsPerDay > 1 ? 0.98 + rand() * 0.04 : 1.0
        const runScore = +(result === 'fail' || hasError
          ? (hasError ? 20 + rand() * 10 : score) * runNoise
          : score * runNoise
        ).toFixed(2)

        const start = isoDate(day, run)
        const end = new Date(new Date(start).getTime() + 45 * 60 * 1000).toISOString().slice(0, 19) + 'Z'
        const created = new Date(new Date(end).getTime() + 60 * 1000).toISOString().slice(0, 19) + 'Z'

        const evalId = runsPerDay > 1
          ? `${scenario.asset}-${scenario.test}-day${day}-run${run}`
          : `${scenario.asset}-${scenario.test}-day${day}`

        const triggeredBy = scenario.seed % 3 === 0 ? 'jenkins' : scenario.seed % 3 === 1 ? 'github-actions' : 'manual'

        const evalResult = hasError ? 'fail' : result
        const jiraLink = { href: 'https://jira.example.com/browse/PERF-481', label: 'PERF-481' }

        // Specific story-driven annotations
        const mockAnnotation = (() => {
          // win-monthly-01 (seed 1001)
          if (scenario.seed === 1001 && day === 12)
            // invalidated record
            return { id: `ann-${evalId}-1`, meta: {}, updated_at: created, content: 'Invalidated — agent crashed mid-run during scheduled maintenance window. Results not representative.', author: 'ops-team', category: 'invalidated', created_at: created }
          if (scenario.seed === 1001 && day === 18)
            // first failure: two notes — investigation + JIRA creation
            return { id: `ann-${evalId}-1`, meta: {}, updated_at: created, content: 'ABC investigation\nCreated JIRA', author: 'j.kowalski', category: 'investigation', created_at: created, link: jiraLink }
          if (scenario.seed === 1001 && day >= 19 && day <= 22 && (evalResult === 'fail' || evalResult === 'warning'))
            // following failures: just the JIRA link
            return { id: `ann-${evalId}-1`, meta: {}, updated_at: created, content: '', author: null, category: null, created_at: created, link: jiraLink }

          // mac-monthly-01 (seed 1003)
          if (scenario.seed === 1003 && day >= 24 && day <= 26 && (evalResult === 'fail' || evalResult === 'warning'))
            return { id: `ann-${evalId}-1`, meta: {}, updated_at: created, content: 'Disk failure on primary storage volume — I/O errors causing compilation timeouts.', author: 'infra', category: 'hardware', created_at: created }
          if (scenario.seed === 1003 && day === 27 && evalResult === 'pass')
            return { id: `ann-${evalId}-1`, meta: {}, updated_at: created, content: 'Disk replaced — new NVMe installed and benchmarked. Monitoring next 2 runs.', author: 'infra', category: 'resolved', created_at: created }

          return null
        })()

        all.push({
          id: evalId,
          name: scenario.test,
          status: 'completed',
          result: evalResult,
          score: Math.min(100, Math.max(0, runScore)),
          start,
          end,
          slo_name: scenario.slo,
          slo_version: 1,
          ingestion_mode: 'pull',
          adapter_used: 'prometheus',
          invalidated: day === 12 && scenario.seed === 1001,
          asset_snapshot: { name: scenario.asset, tags: { os: scenario.os, arch: scenario.arch, lab: scenario.group } },
          metadata: { branch: 'main', build: `ci-${7800 + day}`, triggered_by: triggeredBy },
          latest_annotation: mockAnnotation ?? undefined,
          annotation_count: mockAnnotation ? (scenario.seed === 1001 && day === 18 ? 2 : 1) : 0,
          created_at: created,
          top_failures: hasError ? [
            { metric: 'compilation_errors', display_name: 'Compilation Errors', value: 3, unit: '', threshold: '= 0' },
            { metric: 'link_errors', display_name: 'Link Errors', value: 2, unit: '', threshold: '= 0' },
          ] : top_failures,
        })
      }
    }
  }

  return all
}

export function generateEvaluationDetail(
  id: string,
  evaluations: EvaluationSummary[]
): EvaluationDetail {
  const ev = evaluations.find(e => e.id === id) ?? evaluations[evaluations.length - 1]

  // Parse scenario from id
  const scenario = SCENARIOS.find(s => id.startsWith(s.asset + '-' + s.test)) ?? SCENARIOS[0]
  const dayMatch = id.match(/day(\d+)/)
  const day = dayMatch ? parseInt(dayMatch[1]) : 29

  const rand = makePrng(scenario.seed + day * 17)
  const regFactor =
    scenario.regression &&
    day >= scenario.regression.start &&
    day <= scenario.regression.end
      ? scenario.regression.factor
      : 1.0

  // Build baseline from earlier days
  const getBaselineValue = (m: MetricDef) => {
    const br = makePrng(scenario.seed + (day - 3) * 17 + m.name.length)
    return +(m.base * (0.97 + br() * 0.06)).toFixed(3)
  }

  const indicators: IndicatorResult[] = METRICS.map(m => {
    const noise = 0.96 + rand() * 0.08
    let value: number

    if (m.base === 0) {
      // count metrics: 0 normally, spike on regression
      value = regFactor > 1.3 ? Math.floor(rand() * 5) : 0
    } else if (m.higher_is_worse) {
      value = +(m.base * regFactor * noise).toFixed(3)
    } else {
      // throughput: lower on regression
      value = +(m.base / (regFactor * noise)).toFixed(3)
    }

    const baseline = day >= 3 ? getBaselineValue(m) : null
    const { status, score } = scoreIndicator(m, value, baseline)

    const isRelativePass = m.pass_criteria.startsWith('<=+')
    const isRelativeWarn = m.warn_criteria?.startsWith('<=+') ?? false
    const passRelPct = isRelativePass ? parseFloat(m.pass_criteria.slice(3, -1)) : null
    const warnRelPct = isRelativeWarn && m.warn_criteria ? parseFloat(m.warn_criteria.slice(3, -1)) : null
    const passTarget = isRelativePass && baseline != null && passRelPct != null
      ? [{ criteria: m.pass_criteria, target_value: +(baseline * (1 + passRelPct / 100)).toFixed(2), violated: status !== 'pass' }]
      : m.pass_criteria !== null
      ? [{ criteria: m.pass_criteria, target_value: parseFloat(m.pass_criteria.replace(/[^0-9.]/g, '')), violated: status !== 'pass' }]
      : null

    return {
      metric: m.name,
      display_name: m.display_name,
      tab_group: m.tab_group,
      value: +value.toFixed(3),
      compared_value: baseline,
      change_absolute: baseline != null ? +(value - baseline).toFixed(3) : null,
      change_relative_pct: computeChangePct(value, baseline),
      aggregation: m.base === 0 ? 'raw' : 'avg',
      status,
      score,
      weight: m.weight,
      key_sli: m.key_sli,
      pass_targets: passTarget,
      warning_targets: m.warn_criteria
        ? [{ criteria: m.warn_criteria, target_value: isRelativeWarn && baseline != null && warnRelPct != null
            ? +(baseline * (1 + warnRelPct / 100)).toFixed(2)
            : parseFloat(m.warn_criteria.replace(/[^0-9.]/g, '')), violated: false }]
        : null,
    }
  })

  const maxScore = METRICS.reduce((s, m) => s + m.weight, 0)
  const achieved = indicators.reduce((s, ind) => s + ind.score, 0)
  const score = +(achieved / maxScore * 100).toFixed(2)

  const keySliFailed = indicators.some(ind => ind.key_sli && ind.status === 'fail')
  const result: 'pass' | 'warning' | 'fail' =
    keySliFailed ? 'fail' :
    score >= 90 ? 'pass' :
    score >= 75 ? 'warning' : 'fail'

  return {
    ...ev,
    result,
    score,
    invalidation_note: ev.invalidated ? 'VM had disk I/O spike during antivirus scan.' : null,
    asset_snapshot: {
      name: scenario.asset,
      tags: { os: scenario.os, arch: scenario.arch },
      primary_version: '7.6',
      build_ref: `ci-${7800 + day}`,
    },
    metadata: { branch: '7.6', build: `ci-${7800 + day}`, triggered_by: 'github-actions' },
    compared_evaluation_ids: day >= 3 ? [
      `${scenario.asset}-${scenario.test}-day${day - 1}`,
      `${scenario.asset}-${scenario.test}-day${day - 2}`,
    ] : [],
    annotations: (() => {
      const jiraLink = { href: 'https://jira.example.com/browse/PERF-481', label: 'PERF-481' }
      const t = ev.created_at

      // win-monthly-01 invalidated
      if (scenario.seed === 1001 && day === 12)
        return [{ id: `ann-${scenario.seed}-${day}-1`, content: 'Invalidated — agent crashed mid-run during scheduled maintenance window. Results not representative.', author: 'ops-team', category: 'invalidated', meta: {}, created_at: t, updated_at: t }]

      // win-monthly-01 first failure — two annotations
      if (scenario.seed === 1001 && day === 18)
        return [
          { id: `ann-${scenario.seed}-${day}-1`, content: 'ABC investigation — compilation times show ~35% regression across all stages. Correlates with toolchain upgrade on day 17.', author: 'j.kowalski', category: 'investigation', meta: {}, created_at: t, updated_at: t },
          { id: `ann-${scenario.seed}-${day}-2`, content: 'Created JIRA', author: 'j.kowalski', category: 'investigation', meta: { ticket: 'PERF-481' }, link: jiraLink, created_at: t, updated_at: t },
        ]

      // win-monthly-01 following failures — JIRA link only
      if (scenario.seed === 1001 && day >= 19 && day <= 22)
        return [{ id: `ann-${scenario.seed}-${day}-1`, content: '', author: null, category: null, meta: { ticket: 'PERF-481' }, link: jiraLink, created_at: t, updated_at: t }]

      // mac-monthly-01 disk failure days
      if (scenario.seed === 1003 && day >= 24 && day <= 26)
        return [{ id: `ann-${scenario.seed}-${day}-1`, content: 'Disk failure on primary storage volume — I/O errors causing compilation timeouts.', author: 'infra', category: 'hardware', meta: {}, created_at: t, updated_at: t }]

      // mac-monthly-01 first green after disk replacement
      if (scenario.seed === 1003 && day === 27)
        return [{ id: `ann-${scenario.seed}-${day}-1`, content: 'Disk replaced — new NVMe installed and benchmarked. Monitoring next 2 runs.', author: 'infra', category: 'resolved', meta: {}, created_at: t, updated_at: t }]

      return []
    })(),
    indicator_results: indicators,
  }
}

export function generateTrendData(
  testName: string,
  metricName: string,
  assetName: string,
  evaluations: EvaluationSummary[]
): TrendPoint[] {
  const scenario = SCENARIOS.find(s => s.test === testName && s.asset === assetName)
  if (!scenario) return []

  const metric = METRICS.find(m => m.name === metricName)
  if (!metric) return []

  const sorted = evaluations
    .filter(e => e.name === testName && e.asset_snapshot.name === assetName)
    .sort((a, b) => a.start.localeCompare(b.start))

  const valueHistory: number[] = []

  return sorted.map((ev, i) => {
    const dayMatch = ev.id.match(/day(\d+)/)
    const day = dayMatch ? parseInt(dayMatch[1]) : i
    const rand = makePrng(scenario.seed + day * 17 + metricName.length)
    const regFactor =
      scenario.regression &&
      day >= scenario.regression.start &&
      day <= scenario.regression.end
        ? scenario.regression.factor
        : 1.0
    const noise = 0.96 + rand() * 0.08

    let value: number
    if (metric.base === 0) {
      value = regFactor > 1.3 ? Math.floor(rand() * 5) : 0
    } else if (metric.higher_is_worse) {
      value = +(metric.base * regFactor * noise).toFixed(3)
    } else {
      value = +(metric.base / (regFactor * noise)).toFixed(3)
    }

    const baseline = valueHistory.length >= 3
      ? valueHistory.slice(-3).reduce((a, b) => a + b, 0) / 3
      : valueHistory.length > 0
      ? valueHistory.reduce((a, b) => a + b, 0) / valueHistory.length
      : null
    valueHistory.push(value)

    const { status } = scoreIndicator(metric, value, baseline)
    return { timestamp: ev.start, value, eval_id: ev.id, result: status, baseline }
  })
}

// ---------------------------------------------------------------------------
// MSW-compatible wrappers
// Simple signatures for use in MSW handlers. Cache the full list once per
// module load (deterministic generator produces the same output every time).
// ---------------------------------------------------------------------------

let _cached: EvaluationSummary[] | null = null

function allEvals(): EvaluationSummary[] {
  if (!_cached) _cached = generateAllEvaluations()
  return _cached
}

export interface EvaluationListFilters {
  lab?: string
  date?: string
  slot?: string
}

export function getEvaluations(filters: EvaluationListFilters = {}): EvaluationSummary[] {
  let evals = allEvals()
  if (filters.lab) evals = evals.filter(e => e.asset_snapshot.tags?.['lab'] === filters.lab)
  if (filters.date) evals = evals.filter(e => e.start.startsWith(filters.date!))
  if (filters.slot) evals = evals.filter(e => e.start === filters.slot)
  return evals
}

export function getEvaluationDetail(id: string): EvaluationDetail {
  return generateEvaluationDetail(id, allEvals())
}

export function getTrend(evalId: string, metric: string): TrendPoint[] {
  const ev = allEvals().find(e => e.id === evalId)
  if (!ev) return []
  return generateTrendData(ev.name, metric, ev.asset_snapshot.name, allEvals())
}

// Assets — sourced from static fixtures in mocks/data/
import assetsFixture from './data/assets.json'
import sloFixture from './data/slo-definitions.json'

export function getAssets() {
  return (assetsFixture as { items: unknown[] }).items
}

export function getAssetGroupTree() {
  const assets = (assetsFixture as { items: Array<{ id: string; name: string; labels: Record<string, string> }> }).items
  const labMap = new Map<string, typeof assets>()
  for (const a of assets) {
    const lab = a.labels['lab'] ?? 'unknown'
    if (!labMap.has(lab)) labMap.set(lab, [])
    labMap.get(lab)!.push(a)
  }

  const LAB_DESCRIPTIONS: Record<string, string> = {
    'monthly-lab':       'Monthly compilation regression tests across Windows, Linux, and macOS',
    'toolset-lab':       'Toolset update validation across Windows, Linux, and macOS',
    'ad-hoc-lab-1':      'Ad-hoc performance tests with multiple regression scenarios',
    'performance-lab-1': 'Continuous performance load tests (2 runs/day) on Linux and Windows',
    'performance-lab-2': 'Performance load test mirror environment (2 runs/day)',
  }

  const allGroups = Array.from(labMap.entries()).map(([lab, members], i) => ({
    id: `group-${i}`,
    name: lab,
    display_name: lab.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    description: LAB_DESCRIPTIONS[lab],
    members: members.map(a => ({ asset_id: a.id, asset_name: a.name, weight: 1 })),
    subgroups: [],
  }))

  return { top_level: allGroups, all_groups: allGroups }
}

export function getSloDefinitions() {
  return (sloFixture as { items: unknown[] }).items
}

// SLI definitions — sourced from static fixture in mocks/data/
import sliData from './data/sli-definitions.json'

export function getSliDefinitions() {
  return sliData
}
