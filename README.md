# apple-health-analysis

A Claude Code plugin for evidence-based Apple Health data analysis. Transforms raw Apple Health `export.xml` into structured CSV data, then applies tier-based analysis with research-backed risk positioning.

## Features

- **Three-phase ETL pipeline**: XML → CSV → Derived metrics → Evidence-based analysis
- **Tier-based indicator system**: Indicators classified by measurement reliability and clinical evidence strength
- **Research-backed risk positioning**: Dose-response mapping with cited epidemiological studies
- **Parallel analysis agents**: 5 specialized subagents for concurrent analysis
- **Zero speculation**: All interpretations anchored to specific research citations

## Installation

### As a plugin (from marketplace)

```bash
/plugin marketplace add github:loki/apple-health-analysis
/plugin install apple-health-analysis@apple-health-plugins
```

### As a plugin (direct)

```bash
/plugin install --plugin-dir /path/to/apple-health-analysis
```

## Usage

1. Export your Apple Health data from the Health app on iPhone (Settings → Health → Export All Health Data)
2. Place `export.xml` in an accessible path
3. Use the `/apple-health-analysis` skill:

```
/apple-health-analysis
```

Or ask Claude directly:

```
Analyze my Apple Health export at /path/to/export.xml
```

## Pipeline

| Phase | Description | Output |
|-------|-------------|--------|
| 0: ETL | Single-pass XML → CSV extraction | ~35 CSV files |
| 1: Derived | Aggregated metrics computation | 11 derived datasets |
| 2: Analysis | Parallel tier-based analysis | Per-indicator reports |
| 3: Synthesis | Cross-indicator report | Final health report |

## Indicator Tiers

| Tier | Indicators | Analysis Depth |
|------|-----------|---------------|
| Tier 1 | Steps, Resting HR, VO2max, Sleep, Weight/BMI | Full A/B/C/D |
| Tier 2 | HRV, SpO2, ECG, Walking Steadiness | A/B/C + qualitative D |
| Tier 3 | Energy, Respiratory Rate, Gait, Workouts, Noise | B/C only |

## Plugin Structure

```
apple-health-analysis/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── health-analysis/
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── parse_health_v2.py
│       │   └── build_derived_v2.py
│       └── references/
│           ├── research-citations.md
│           ├── measurement-accuracy.md
│           └── analysis-framework.md
├── agents/
│   ├── tier-1-analysis.md
│   ├── tier-2-analysis.md
│   ├── tier-3-analysis.md
│   ├── data-quality.md
│   └── correlations.md
├── LICENSE
└── CHANGELOG.md
```

## Requirements

- Python 3.8+ (for ETL scripts)
- `numpy` and `pandas` (for derived metrics)
- Claude Code with plugin support

## License

MIT
