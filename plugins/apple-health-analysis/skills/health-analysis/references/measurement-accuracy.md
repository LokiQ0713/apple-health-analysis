# Apple Watch Measurement Accuracy Reference

Layer A (Measurement Reliability) data for each indicator. Cite this when assessing whether an indicator's precision supports risk assessment.

---

## Tier 1 Indicators

### Step Count
- **Source**: Choe & Kang, Physiol Meas 2025 (56-study meta-analysis)
- **Bias**: -1.83 steps/minute
- **LoA**: -9.08 to +5.41 steps/minute
- **MAPE**: Some subgroups exceed 10%
- **Key limitation**: Accuracy drops significantly at low walking speeds (<3 km/h)
- **Assessment**: Precision adequate for risk positioning at daily aggregation level

### Resting Heart Rate
- **Source**: Lambe et al., npj Digital Medicine 2026 (82-study living review, 430,052 participants)
- **Bias**: -0.27 bpm
- **LoA**: -7.19 to +6.64 bpm
- **Source**: Choe & Kang 2025 meta-analysis: all subgroups MAPE <10%
- **Key limitation**: PPG accuracy decreases with darker skin tones, tattoos, high exercise intensity
- **RHR extraction**: If RestingHeartRate type exists, use directly (Apple's algorithm pre-filters). If only HeartRate data, extract lowest 5th percentile of 2-5 AM readings (excluding awake periods)
- **Assessment**: Precision adequate for risk positioning (10 bpm gradient resolution)

### VO2max (Cardio Fitness)
- **Source**: Shanahan et al., PLOS ONE 2025 (30 participants, Series 9/Ultra 2 vs indirect calorimetry)
- **Bias**: Tends to underestimate; MAPE ~15.8% (Series 7: ~13.31%)
- **Source**: JMIR 2024: ICC = 0.47 (poor reliability); lab mean 45.88 vs Apple Watch 41.37
- **Directional bias**: Overestimates low-fitness, underestimates high-fitness individuals; sex bias (more underestimation in women)
- **Key limitation**: Requires outdoor walking/running/cycling + GPS + sufficient heart rate intensity; indoor exercise produces no estimate; data points are sparse
- **Assessment**: Absolute values unreliable (ICC 0.47); trends over multiple readings may be informative; map to FRIEND percentile with ±6 ml/kg/min uncertainty band

### Sleep Duration (Total Sleep Time)
- **Binary classification** (sleep vs wake): Sensitivity ≥95% across all major devices — reliable
- **Sleep stage classification** (Apple Watch Series 8+):
  - Overall Cohen's kappa vs PSG: 0.53 (moderate)
  - Deep sleep sensitivity: **50.5-50.7%** — poor
  - REM sleep sensitivity: **~78-81%** — fair
  - Core (light) sleep: tends to be overestimated
  - Apple Watch underestimates wake time by 11-39 minutes → overestimates total sleep
- **Key limitation**: 38% of deep sleep epochs misclassified as core sleep
- **Assessment**: Total sleep duration usable for risk positioning. Sleep stage proportions (deep/REM/core) are trend-reference ONLY — do not make clinical interpretations based on stage percentages

### Body Weight / BMI
- **Source**: User-entered or smart scale sync
- **Accuracy**: Depends entirely on measurement device (scale accuracy ±0.1-0.5 kg typical)
- **Key limitation**: Irregular measurement intervals; self-report bias possible
- **Assessment**: Weight trends are reliable; single measurements depend on scale quality

---

## Tier 2 Indicators

### HRV (SDNN)
- **What Apple Watch measures**: Short-term SDNN from ~60-second PPG windows, typically during sleep/rest
- **Source**: 2025 validation (78 healthy adults, vs Biopac 3-lead ECG): Apple Watch 6 HRV has data gaps (avg 5 intervals, ~6.5s gaps); frequency-domain metrics affected; time-domain (SDNN, RMSSD) relatively unaffected
- **Critical limitation**: Apple Watch short-term SDNN ≠ 24-hour Holter SDNN. Clinical thresholds (ESC/NASPE 1996: 24h SDNN <50ms = severely depressed) do NOT apply
- **Assessment**: Trend analysis only. Report absolute values for personal baseline tracking. Do NOT map to 24h Holter clinical thresholds

### SpO2 (Blood Oxygen)
- **FDA status**: NOT cleared as medical device for SpO2 measurement
- **Clinical pulse oximeter standard**: ±2% accuracy; Apple Watch error typically larger
- **Key limitations**: Affected by skin tone, band tightness, motion state, tattoos, cold extremities
- **Sleep apnea detection** (Series 9/10, Sept 2024): Uses accelerometer (NOT SpO2 sensor); sensitivity for severe OSA: 89%, specificity 98.5%; sensitivity for moderate OSA: only 43%
- **Assessment**: Not suitable for clinical decision-making. Report distribution and patterns. Explicitly caveat that anomalies require medical-grade device confirmation

### ECG (Electrocardiogram)
- **FDA status**: FDA 510(k) cleared for atrial fibrillation detection
- **What it records**: Single-lead ECG (Lead I equivalent), 30 seconds
- **Classification categories**: Sinus rhythm / Atrial fibrillation / Inconclusive / Other
- **Assessment**: Report classification distribution. Do not interpret beyond Apple's classification — AFib clinical significance requires cardiologist evaluation with full clinical history

### Walking Steadiness
- **What it measures**: Apple's composite fall risk score (Low / OK / High risk)
- **Source**: Apple internal validation
- **Assessment**: Useful as categorical indicator; limited validation data available for detailed interpretation

---

## Tier 3 Indicators (Trend Reference Only)

### Active/Basal Energy Burned
- **Source**: Choe & Kang 2025: All subgroup MAPE >10% (exceeds validity threshold)
- **Assessment**: Absolute calorie values are NOT reliable. Report ONLY relative monthly trends (direction and magnitude of change). Never interpret absolute kcal values

### Respiratory Rate
- **Limited validation data available**
- **Normal range**: 12-20 breaths/minute (resting adult)
- **Assessment**: Basic statistics and trend only

### Gait Metrics (Walking Speed, Step Length, Double Support, Asymmetry)
- **Walking speed**: Measured during daily activities, differs methodologically from clinical standardized tests (e.g., 4-meter walk test)
- **Step length**: Limited validation; should be normalized by height (normalized stride = stride/height)
- **Double support %**: Apple Health App vs APDM Mobility Lab: "poor to moderate" agreement
- **Asymmetry %**: Limited validation
- **Assessment**: Trend analysis only. Do not make clinical diagnoses based on these values. Walking speed has strongest evidence base among gait metrics

### Workout Records
- **Duration/distance**: Generally reliable (GPS + accelerometer)
- **Heart rate during workout**: PPG accuracy decreases during high-intensity exercise
- **Energy burned**: Same MAPE >10% limitation as general energy data
- **Assessment**: Frequency, duration trends are reliable. Compare to WHO guidelines (150-300 min/week moderate intensity). Energy values are directional only
