# Detailed Analysis Framework

Extended guidance for the A/B/C/D analysis layers, data preprocessing, and advanced metrics.

---

## Data Source Separation

Apple Health data comes from multiple sources. Use the `source` column in CSV to distinguish:

| Source Pattern | Device | Accuracy Level |
|---------------|--------|---------------|
| "Apple Watch" / "Watch" | Apple Watch (direct sensor) | Highest for HR, HRV, SpO2 |
| iPhone model names | iPhone (motion coprocessor) | Good for steps/distance, different algorithm |
| "AutoSleep" / "Sleep Cycle" etc. | Third-party apps | Variable, check app-specific validation |
| "Health" / manual entry | User self-report | Weight, height — accuracy depends on user |

**Rule**: Do not mix data from different sources for the same indicator without noting the source distribution. If >20% of an indicator's data comes from a different source than the majority, flag this in the Data Quality section.

## Sleep Session Merging Logic

Raw sleep records contain individual stage segments. To compute nightly metrics:

1. **Sort** all sleep records by startDate
2. **Assign night**: If a record's startDate is after 18:00, assign to that calendar date's night. If before 18:00, assign to the previous date's night.
3. **Aggregate** per night:
   - `bedtime` = earliest InBed or Asleep startDate
   - `waketime` = latest endDate across all records
   - `time_in_bed` = waketime - bedtime (hours)
   - `total_sleep` = sum of durations where stage ∈ {Core, Deep, REM, Unspecified} (hours)
   - `deep_hours` = sum of Deep stage durations
   - `rem_hours` = sum of REM stage durations
   - `core_hours` = sum of Core stage durations
   - `awake_hours` = sum of Awake stage durations
   - `sleep_efficiency` = total_sleep / time_in_bed
   - `sleep_latency` = first Asleep startDate - first InBed startDate (minutes)
   - `fragmentation_index` = awake_count / total_sleep_hours
4. **Filter**: Exclude nights where time_in_bed > 18h or < 1h (anomalous)

## ODI (Oxygen Desaturation Index) Calculation

ODI estimates the frequency of oxygen desaturation events per hour, relevant to OSA screening:

1. Sort SpO2 records by time within each night (22:00-08:00 window)
2. A **desaturation event** = SpO2 drops ≥3% from the preceding baseline within a 120-second window
3. Count events per night
4. ODI = events / hours of nighttime SpO2 monitoring
5. Classification:
   - ODI <5: Normal
   - ODI 5-15: Mild
   - ODI 15-30: Moderate
   - ODI >30: Severe

**Caveat**: Apple Watch SpO2 sampling is intermittent (not continuous), so ODI calculation is an approximation. State this limitation explicitly.

## Circadian Rhythm Metrics (IS/IV/RA)

Computed from hourly activity or heart rate data using `pyActigraphy` or manual calculation:

### Interdaily Stability (IS)
- Measures consistency of the 24-hour activity pattern across days
- Range: 0 (random) to 1 (perfectly stable)
- Low IS associated with depression, cognitive decline

### Intradaily Variability (IV)
- Measures fragmentation of the activity pattern within days
- Range: 0 (smooth sine wave) to 2+ (highly fragmented)
- High IV associated with sleep disorders, dementia

### Relative Amplitude (RA)
- Ratio of most active 10 hours (M10) to least active 5 hours (L5)
- RA = (M10 - L5) / (M10 + L5)
- Range: 0 to 1
- Low RA associated with depression, metabolic syndrome

### Calculation
```python
# From hourly activity data (e.g., steps or heart rate)
# Reshape to 24 columns (hours) x N rows (days)
# IS = (N * sum of squared deviations of hourly means from grand mean) /
#      (24 * sum of squared deviations of all values from grand mean)
# IV = (N * 24 * sum of squared successive differences) /
#      ((24*(N-1)) * sum of squared deviations from grand mean)
```

## Change Point Detection

Use the `ruptures` library to automatically detect significant shifts in health indicators:

```python
import ruptures as rpt
# Detect changes in daily step count
algo = rpt.Pelt(model="rbf").fit(daily_steps_array)
change_points = algo.predict(pen=10)
```

Useful for identifying:
- When a health behavior changed (started/stopped exercise program)
- When a health event occurred (illness, injury)
- Device changes that affect measurements (new Apple Watch model)

## Wearing Gap Detection

Detect periods when Apple Watch was not worn:

1. From heart_rate.csv, compute time gaps between consecutive readings
2. Gap > 2 hours during waking hours (08:00-22:00) = likely not wearing
3. Gap > 4 hours during any time = definite non-wearing period
4. Report:
   - Total wearing days vs calendar days
   - Average daily wearing hours
   - Longest non-wearing streak
   - Impact on data completeness per indicator

## GQI (Gait Quality Index) Calculation

Composite score from gait metrics (Tier 3 — trend reference only):

```
speed_score = min(100, (walking_speed_mean / 6.0) * 100)
length_score = min(100, (step_length_mean / 80.0) * 100)
support_score = min(100, max(0, (40 - double_support_pct) / 20 * 100))
asymmetry_score = min(100, max(0, (10 - asymmetry_pct) / 10 * 100))

GQI = speed_score * 0.30 + length_score * 0.25 + support_score * 0.25 + asymmetry_score * 0.20
```

**Important**: This is a custom composite for trend tracking, not a validated clinical score. Use only for monitoring longitudinal changes, not for clinical assessment.

## Social Jet Lag Calculation

```
sleep_midpoint = (bedtime_decimal + waketime_decimal) / 2
# bedtime_decimal: e.g., 01:30 = 25.5 (add 24 if past midnight)
# waketime_decimal: e.g., 09:00 = 9.0

workday_midpoint = mean of sleep_midpoints on Mon-Fri nights
weekend_midpoint = mean of sleep_midpoints on Fri-Sat nights

social_jet_lag = abs(weekend_midpoint - workday_midpoint)  # hours
# > 1 hour: significant social jet lag
# > 2 hours: severe social jet lag
```

## Sleep Regularity Index (SRI) — Simplified

```
# For each pair of consecutive days:
# Divide 24 hours into 288 five-minute epochs
# For each epoch, check if sleep/wake state matches between the two days
# SRI = (matching_epochs / total_epochs) * 100

# Simplified approximation using bedtime/waketime consistency:
SRI_approx = 100 - (bedtime_std_minutes + waketime_std_minutes) / 2
# Where std is computed over a rolling 30-day window
```

Higher SRI (>80) = regular sleep pattern. Lower SRI (<60) = irregular.

Per JAMA 2024: SRI is a stronger predictor of mortality than sleep duration.

## Report Template

```markdown
# Apple Health Evidence-Based Data Report

**Subject**: [Age] years, [Sex]
**Data Span**: [Start] to [End] ([N] days)
**Apple Watch Model**: [Model] (wearing rate: [X]%)
**Analysis Date**: [Date]

---

## 1. Data Overview
[Time span, record counts per indicator, wearing pattern, data sources]

## 2. Tier 1 Indicators

### 2.1 Daily Step Count
**A. Measurement Reliability**: [cite accuracy data]
**B. Statistical Summary**: [descriptive stats table]
**C. Trend Analysis**: [monthly trends, weekday/weekend, seasonality]
**D. Risk Positioning**: [map to Paluch/Banach/Sheng dose-response, report HR with CI]

### 2.2 Resting Heart Rate
[A/B/C/D layers]

### 2.3 VO2max
[A/B/C/D layers]

### 2.4 Sleep Duration
[A/B/C/D layers]

### 2.5 Body Weight / BMI
[A/B/C/D layers]

## 3. Tier 2 Indicators

### 3.1 HRV (SDNN)
[A/B/C + qualitative D — no 24h Holter threshold comparison]

### 3.2 Blood Oxygen (SpO2)
[A/B/C + qualitative D — not medical-grade caveat]

### 3.3 ECG
[Classification distribution only]

## 4. Tier 3 Trend Summary
[Brief trends for energy, respiratory rate, gait, workouts, noise — no risk positioning]

## 5. Cross-Indicator Associations
[Descriptive correlations: steps↔RHR, sleep↔next-day HRV, exercise↔VO2max trend]
[Explicitly note: these are statistical associations, not causal claims]

## 6. Data Quality Notes
[Missing rates, anomalies, source distribution, wearing gaps, algorithm version changes]
```
