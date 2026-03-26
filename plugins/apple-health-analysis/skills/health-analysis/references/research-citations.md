# Research Citations for Risk Positioning

All dose-response data used in risk positioning (Layer D) must come from this file. Do not fabricate or extrapolate beyond these citations.

---

## 1. Daily Step Count

### Source 1 — Paluch et al., Lancet Public Health 2022
- **Design**: Meta-analysis, 15 prospective cohorts, 47,471 adults, 3,013 deaths
- **Key findings**:
  - Age ≥60: risk plateau at 6,000-8,000 steps/day
  - Age <60: risk plateau at 8,000-10,000 steps/day
  - Highest vs lowest quartile: all-cause mortality reduced 40%-53%

### Source 2 — Banach et al., Eur J Prev Cardiol 2023
- **Design**: Meta-analysis, 17 cohorts, 226,889 participants, median follow-up 7.1 years
- **Key findings**:
  - Per 1,000 steps/day increase: all-cause mortality HR 0.85 (95% CI 0.81-0.91)
  - Per 500 steps/day increase: CVD mortality HR 0.93 (95% CI 0.91-0.95)
  - All-cause mortality protective threshold: ~3,867 steps/day
  - CVD mortality protective threshold: ~2,337 steps/day
  - No upper limit — benefits continue up to 20,000 steps/day

### Source 3 — Sheng et al., JACC 2023
- **Design**: Meta-analysis, 12 studies, 111,309 participants
- **Key findings**:
  - All-cause mortality minimum risk: 2,517 steps/day (aHR 0.92 vs 2,000 reference)
  - All-cause mortality optimal dose: 8,763 steps/day (aHR 0.40, 95% CI 0.38-0.43)
  - CVD optimal dose: 7,126 steps/day (aHR 0.49, 95% CI 0.45-0.55)

### Source 4 — Inoue et al., JAMA Network Open 2023
- Even reaching 8,000 steps on only 1-2 days/week significantly reduces 10-year all-cause mortality vs never reaching it

### Analysis Application
- Compute daily and weekly mean steps
- Identify proportion of days reaching 8,000 steps
- Analyze weekday vs weekend pattern
- Map daily mean to the dose-response curves above, report corresponding HR interval
- Observe monthly trend direction

---

## 2. Resting Heart Rate

### Source 1 — Zhang et al., CMAJ 2016
- **Design**: Meta-analysis, 46 studies, 1,246,203 participants, 78,349 all-cause deaths
- **Key findings**:
  - Per 10 bpm increase: all-cause mortality RR 1.09 (95% CI 1.07-1.12), CVD mortality RR 1.08 (95% CI 1.06-1.10)
  - 60-80 bpm vs lowest category: all-cause mortality RR 1.12 (95% CI 1.07-1.17)
  - ≥80 bpm vs lowest: all-cause mortality RR 1.45 (95% CI 1.34-1.57)
  - Dose-response is linear, risk increases continuously from 45 bpm upward

### Source 2 — Aune et al., 2017
- **Design**: Meta-analysis, 87 studies
- **Key findings**:
  - Per 10 bpm increase: CHD RR 1.07, Heart failure RR 1.18, All-cause mortality RR 1.17

### Source 3 — Tjugen et al., Clin Res Cardiol 2021
- **Design**: Lifetime follow-up cohort
- **Key findings**:
  - RHR vs CVD mortality follows **U-shaped** relationship, with 60 bpm as reference
  - 60-70 bpm zone corresponds to lowest CVD mortality
  - ≥90 bpm vs 60-70 bpm: non-CVD mortality HR 2.19 (95% CI 1.47-2.38)

### Analysis Application
- Compute daily RHR (or use RestingHeartRate type directly)
- Report recent 3-month median and trend
- Map to the per-10-bpm risk gradient above
- Analyze longitudinal trend: is RHR rising or falling? This matters more than absolute value

---

## 3. VO2max / Cardiorespiratory Fitness (CRF)

### Population Reference — FRIEND Registry (Mayo Clin Proc 2015; updated 2021)
Male 50th percentile VO2max (ml/kg/min, treadmill):
- 20-29: 48.0-49.5
- 30-39: 44.0-45.0
- 40-49: 40.0-41.0
- 50-59: 35.0-36.0
- 60-69: 30.0-31.0
- 70-79: 24.4-30.8

Female 50th percentile VO2max:
- 20-29: 37.6-40.6
- 30-39: 34.0-35.0
- 40-49: 31.0-32.0
- 50-59: 27.0-28.0
- 60-69: 23.0-24.0

### Source 1 — Kokkinos et al., JACC 2022
- **Design**: 750,302 participants
- **Key findings**:
  - CRF-mortality relationship: inverse, independent, graded, across all age/sex/race groups
  - Least fit (≤20th percentile) vs extremely fit: mortality HR 4.09 (95% CI 3.90-4.20)
  - CRF difference is more hazardous than any single traditional cardiac risk factor
  - No excess risk at extremely high fitness levels

### Source 2 — Laukkanen et al.
- **Design**: 500+ males, 11-year follow-up
- **Key finding**: Per 1 ml/kg/min VO2max increase, mortality risk decreases 9%

### Source 3 — Mandsager et al., JAMA Network Open 2018
- **Design**: 122,007 participants
- **Key findings**:
  - Lowest fitness (<25th percentile) vs elite: ~5x mortality difference
  - Per ~3.5 ml/kg/min (≈1 MET) increase: all-cause mortality reduced ~13%

### Apple Watch Accuracy Note
- Shanahan et al., PLOS ONE 2025: Apple Watch tends to **underestimate** VO2max; MAPE ~15.8%
- Apple internal validation (221 people): error ~1.2 ml/kg/min, reliability 0.86-0.89
- **Important**: Apple Watch underestimates high-fitness individuals, overestimates low-fitness individuals
- VO2max estimation requires outdoor walking/running/cycling + GPS + sufficient HR intensity; indoor exercise produces no estimate

### Analysis Application
- Extract all VO2max readings, plot chronologically (do NOT aggregate by day)
- Note: VO2max data points are sparse (only from qualifying outdoor workouts)
- Report recent N readings' median and trend
- Map to FRIEND percentile table (requires user age and sex)
- Compute longitudinal change rate: VO2max naturally declines ~10%/decade; is user's decline faster or slower?

---

## 4. Sleep Duration

### Source 1 — Yin et al., JAHA 2017
- **Design**: Systematic review + dose-response meta-analysis
- **Key findings**:
  - U-shaped relationship with all-cause mortality and CVD events
  - Minimum risk point: ~7 hours/day
  - <7 hours: per 1-hour decrease, all-cause mortality RR 1.06 (95% CI 1.04-1.07)
  - >7 hours: per 1-hour increase, all-cause mortality RR 1.13 (95% CI 1.11-1.15)
  - Long sleep risk increment > short sleep

### Source 2 — Shen et al., Scientific Reports 2016
- **Design**: 35 articles, 1,526,609 participants
- **Key findings** (all-cause mortality RR, 7h as reference):
  - 4h: 1.07 (1.03-1.13)
  - 5h: 1.04 (1.01-1.07)
  - 6h: 1.01 (1.00-1.02) ← virtually no excess risk
  - 8h: 1.07 (1.06-1.09)
  - 9h: 1.21 (1.18-1.24)
  - 10h: 1.37 (1.32-1.42)
  - 11h: 1.55 (1.47-1.63)

### Source 3 — Kwok et al., JAHA 2018
- **Design**: 60 studies, >3 million participants
- **Key findings**:
  - Deviation from recommended 7-8h correlates with moderately increased all-cause mortality
  - J-shaped relationship: long sleep (>8h) risk increment > short sleep

### Source 4 — ACC/AHA Recommendation
- Optimal adult sleep: 7-9 hours/night

### Apple Watch Accuracy Note
- Sleep/wake binary classification: sensitivity ≥95% (reliable)
- Sleep stage classification: Cohen's kappa = 0.53 (moderate agreement with PSG)
  - Deep sleep sensitivity: 50.5-50.7% (poor — use for trends only)
  - REM sensitivity: ~78-81% (fair)
  - Apple Watch tends to underestimate wake time by 11-39 minutes, overestimating total sleep
- **Conclusion**: Total sleep duration is usable; sleep stage proportions are trend-reference only

### Analysis Application
- Extract nightly total sleep duration (= Core + Deep + REM + Unspecified, excluding InBed and Awake)
- Compute daily mean, median, distribution
- Analyze weekday vs weekend difference (Social Jet Lag)
- Identify sleep regularity: bedtime and wake-time standard deviation
- Map mean duration to U-shaped curve, report corresponding RR interval
- If sleep stage data exists, report Deep/REM proportions with accuracy caveat

---

## 5. HRV (Heart Rate Variability, SDNN)

### Measurement Critical Note
- Apple Watch records **short-term SDNN** (based on ~60s PPG sampling), NOT 24-hour Holter SDNN
- These are clinically different measurements with different reference ranges
- **Do NOT compare Apple Watch SDNN directly to ESC/NASPE 1996 24h thresholds** (those require 24h Holter: SDNN <50ms = severely depressed, <100ms = moderately decreased)

### General Research Findings
- HRV declines with age: SDNN and SDANN decrease linearly; after age 60, pNN50 may slightly increase
- Low HRV is associated with: all-cause mortality, cardiac arrhythmia death, PTSD, inflammation
- Regular aerobic exercise and Mediterranean diet correlate with higher HRV
- Smoking correlates with lower SDNN and RMSSD

### MESA Study Reference (10-second ECG, also not equivalent to Apple Watch 60s PPG)
- Borderline abnormal: <5th percentile of SDNN/rMSSD
- Abnormal: <2nd percentile
- Both associated with CVD events and all-cause mortality

### Analysis Application
- Compute daily HRV (use nighttime or morning readings, take median)
- Analyze 7-day moving average trend
- Compute HRV's own day-to-day CV (coefficient of variation) — high CV suggests unstable autonomic regulation
- **Do NOT** map to 24h Holter clinical thresholds
- Report absolute values and personal baseline
- Focus on longitudinal trend: is HRV persistently declining?
- If sufficient data exists, report user's own percentile distribution

---

## 6. Blood Oxygen (SpO2)

### Measurement Critical Note
- Apple Watch SpO2 has **NOT** received FDA medical device clearance
- Accuracy affected by: skin tone, band tightness, motion, tattoos
- Clinical pulse oximeter standard: ±2% error; Apple Watch error is typically larger

### Reference Values
- Healthy adult normal: 95%-100%
- <95%: clinically defined as hypoxemia
- <90%: severe hypoxemia, typically requires medical intervention
- Healthy individuals may briefly dip to 84.2% during sleep (within 2SD range)

### Analysis Application
- Report distribution: median, 5th percentile minimum
- Identify whether repeated <95% readings exist (pattern vs isolated)
- If nighttime continuous SpO2 data exists, observe desaturation patterns during sleep (associated with sleep apnea, but Apple Watch precision insufficient for diagnosis)
- **Explicitly state**: Apple Watch SpO2 is not medical-grade; anomalous values require medical-grade device confirmation

---

## 7. Body Weight and BMI

### WHO BMI Classification
- Underweight: <18.5
- Normal: 18.5-24.9
- Overweight: 25.0-29.9
- Obese Class I: 30.0-34.9
- Obese Class II: 35.0-39.9
- Obese Class III: ≥40.0

### Analysis Application
- Plot weight and BMI time series
- Calculate rate of change (kg/month)
- Note: self-reported weight data may have irregular intervals; do not interpolate
- Report current BMI category and trend direction
