---
name: apple-health-analysis
description: This skill should be used when the user asks to "analyze health data", "analyze Apple Health export", "parse export.xml", "health report", "generate health report", "sleep analysis", "VO2max analysis", "step count analysis", "heart rate analysis", "分析健康数据", "分析 Apple Health 导出", "健康报告", "睡眠分析", "运动分析", or mentions Apple Health export.xml, HealthKit data analysis, Apple Watch health metrics, understanding Apple Watch data, or evidence-based health data interpretation. Provides evidence-based methodology for Apple Health data analysis with three-phase ETL pipeline, tier-based indicator classification, A/B/C/D per-indicator analysis framework, and dose-response research citations.
---

# Apple Health Evidence-Based Data Analysis

An evidence-based health data analysis engine that maps Apple Health indicators to epidemiological dose-response relationships, producing a structured personal health data report.

## Core Principles

1. **Zero Speculation** — Anchor all interpretations to specific research provided in `references/research-citations.md`. If no research supports a claim, state "insufficient evidence for this indicator."
2. **Accuracy Before Conclusions** — Quantify Apple Watch measurement error (from `references/measurement-accuracy.md`) before risk mapping. If measurement error exceeds risk stratification resolution, state "measurement precision insufficient for risk assessment, trend reference only."
3. **Trends Over Absolutes** — Individual longitudinal change (3-month/6-month/1-year trends) carries more signal than single-point comparisons to population thresholds. Analyze both, but weight trends higher.
4. **No Action Recommendations** — Output is data interpretation and risk positioning, not medical advice. Never say "you should exercise more" or "see a doctor." Leave decisions to the user.
5. **No Emotional Language** — Report population distribution position and relative risk (HR) objectively. Replace "good/bad/normal/abnormal" with percentile positions and HR values with 95% CI.

## Pipeline: Three-Phase Architecture

### Phase 0: ETL (Extract-Transform-Load)

Run `scripts/parse_health_v2.py` to perform a **single-pass** XML extraction into CSV files.

```bash
python3 scripts/parse_health_v2.py /path/to/export.xml /path/to/output/csv/
```

This produces ~35 CSV files covering all clinically relevant Record types, Workout elements, ActivitySummary elements, and Me metadata. Run once, analyze many times.

### Phase 1: Derived Metrics

Run `scripts/build_derived_v2.py` to compute aggregated and derived datasets from raw CSVs.

```bash
python3 scripts/build_derived_v2.py /path/to/csv/ /path/to/output/derived/
```

Produces: `daily_summary.csv`, `nightly_sleep.csv`, `weekly_summary.csv`, `monthly_summary.csv`, `hr_hourly.csv`, `hr_zones_daily.csv`, `workout_enriched.csv`, `body_composition.csv`, `data_quality.csv`, `wearing_gaps.csv`.

### Phase 2: Evidence-Based Analysis

Launch parallel agents (one per Tier group), each reading from derived CSVs. No agent touches the original XML. See "Task Orchestration" below.

## Indicator Tier System

Classify every indicator by measurement reliability and clinical evidence strength:

| Tier | Definition | Indicators | Analysis Depth |
|------|-----------|-----------|---------------|
| **Tier 1** | High accuracy + strong evidence | Steps, Resting HR, VO2max, Sleep duration, Body weight/BMI | Full A/B/C/D framework |
| **Tier 2** | Medium accuracy + clinical reference | HRV (SDNN), SpO2, ECG, Walking steadiness | A/B/C + qualitative D |
| **Tier 3** | Trend reference only | Energy burned, Respiratory rate, Gait metrics, Workouts, Noise | B/C only, no risk positioning |

## Per-Indicator Analysis Framework (A/B/C/D)

For each indicator, output these layers in order:

### A. Measurement Reliability
Cite validation research from `references/measurement-accuracy.md`: bias, LoA (Limits of Agreement), MAPE. State whether precision supports risk assessment.

### B. User Data Statistical Summary
Descriptive statistics (mean, median, SD, IQR, extremes), natural-cycle aggregation (daily/weekly/monthly), distribution shape, missing rate, anomaly count.

### C. Trend Analysis
Longitudinal trends (moving averages), periodicity (weekday vs weekend, seasonal), variability trends (not just mean shifts, also volatility changes like HRV day-to-day CV).

### D. Risk Positioning (Tier 1 and Tier 2 only)
Map user values to dose-response curves from `references/research-citations.md`. Report:
- User's approximate position in population distribution
- Corresponding relative risk (HR) with 95% CI
- Explicitly note: these HRs reflect population-level statistical associations, not individual causal predictions

## Task Orchestration

### Dependency Graph

```
Phase 0 (ETL): 1 agent, serial          → CSV layer ready
Phase 1 (Derived): 1 agent, serial      → Derived layer ready
Phase 2 (Analysis): 3-5 agents, PARALLEL → Each reads different CSVs
Phase 3 (Synthesis): Main agent          → Cross-indicator report
```

### Phase 2 Parallel Agent Design

| Agent | Scope | Input CSVs | Framework |
|-------|-------|-----------|-----------|
| Tier 1 | Steps, RHR, VO2max, Sleep, Weight | daily_summary, vo2max, body_composition, nightly_sleep | A/B/C/D |
| Tier 2 | HRV, SpO2, ECG, Steadiness | hrv, spo2, ecg/*, walking_steadiness | A/B/C + D qualitative |
| Tier 3 | Energy, Respiratory, Gait, Workouts | daily_summary, workout_enriched | B/C only |
| Data Quality | Missing rates, sources, wearing gaps | data_quality, wearing_gaps, all CSVs | Standalone |
| Correlations | Cross-indicator associations | daily_summary, nightly_sleep, sleep_steps_correlation | Descriptive only |

**Critical rule**: Phase 2 agents MUST NOT depend on each other. Each reads only from Phase 1 outputs.

### Reference Loading Strategy

- Tier 1/2 analysis agents: Load `references/research-citations.md` and `references/measurement-accuracy.md` at start
- All agents: Load `references/analysis-framework.md` only when computing specialized metrics (ODI, circadian rhythm, GQI)
- Data Quality agent: No reference files needed — works from CSV metadata only

### Budget Estimation

Before launching, estimate and report to user:

| Phase | Agents | Est. Tokens | Wall Time |
|-------|--------|------------|-----------|
| 0: ETL | 1 | ~18K | 2 min |
| 1: Derived | 1 | ~25K | 3 min |
| 2: Analysis | 3-5 | ~85K | 5 min |
| 3: Synthesis | main | ~10K | 2 min |
| **Total** | **6-8** | **~138K** | **~12 min** |

Estimates based on typical 2-3 year Apple Health export; actual usage varies with data volume and model.

Report estimated window percentage for the user's subscription tier before proceeding.

## Report Structure

```
1. Data Overview
   - Time span, record counts, Apple Watch model, wearing pattern
2. Tier 1 Indicators (A/B/C/D per indicator)
3. Tier 2 Indicators (A/B/C + qualitative D)
4. Tier 3 Trend Summary
5. Cross-Indicator Associations (descriptive, not causal)
6. Data Quality Notes (missing rates, anomalies, wearing gaps)
```

## Prohibitions

1. **NEVER** make health status judgments without research support
2. **NEVER** use "healthy/unhealthy", "good/bad", "normal/abnormal" — use percentile and HR values
3. **NEVER** compare Apple Watch short-term SDNN to 24-hour Holter clinical thresholds
4. **NEVER** give action, medical, or lifestyle recommendations
5. **NEVER** fabricate research data not provided in `references/research-citations.md`
6. **NEVER** interpret energy expenditure absolute values as meaningful
7. **NEVER** treat Apple Watch SpO2 as medical-grade pulse oximetry

## Additional Resources

### Reference Files

Consult these for detailed data during analysis:
- **`references/research-citations.md`** — Dose-response relationships for all Tier 1 and Tier 2 indicators, with study citations, sample sizes, HR values, and 95% CIs
- **`references/measurement-accuracy.md`** — Apple Watch validation studies per indicator: bias, LoA, MAPE, sensitivity/specificity
- **`references/analysis-framework.md`** — Detailed A/B/C/D examples, data source separation guide, sleep session merging logic, ODI calculation, circadian rhythm metrics (IS/IV/RA)

### Scripts

ETL pipeline scripts (run in order):
- **`scripts/parse_health_v2.py`** — Single-pass XML → CSV extraction for all indicator types
- **`scripts/build_derived_v2.py`** — Derived metrics computation from raw CSVs

### Data Source Separation

Apple Health data comes from multiple sources with different accuracy levels. For detailed source separation rules and accuracy by device type, consult `references/analysis-framework.md`.
