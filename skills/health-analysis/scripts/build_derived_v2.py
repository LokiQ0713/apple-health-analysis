#!/usr/bin/env python3
"""
Apple Health 衍生指标计算 v2
从 ETL 产出的 CSV 文件计算聚合和衍生数据集。

用法:
    python3 build_derived_v2.py <csv_dir> <output_dir>

输出 11 个数据集:
    1. daily_summary.csv        — 每日健康总览
    2. nightly_sleep.csv        — 每晚睡眠会话
    3. weekly_summary.csv       — 周汇总
    4. monthly_summary.csv      — 月汇总
    5. hr_hourly.csv            — 心率按小时聚合
    6. hr_zones_daily.csv       — 每日心率区间分布
    7. workout_enriched.csv     — 运动记录增强版
    8. body_composition.csv     — 身体成分时间序列
    9. data_quality.csv         — 数据质量报告
   10. wearing_gaps.csv         — 佩戴间隙检测
   11. sleep_steps_correlation.csv — 睡眠-活动关联表
"""

import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SLEEP_STAGE_MAP = {
    "HKCategoryValueSleepAnalysisAsleepCore": "Core",
    "HKCategoryValueSleepAnalysisAsleepDeep": "Deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "REM",
    "HKCategoryValueSleepAnalysisInBed": "InBed",
    "HKCategoryValueSleepAnalysisAwake": "Awake",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "Unspecified",
}

ACTIVITY_TYPE_MAP = {
    "HKWorkoutActivityTypeWalking": "Walking",
    "HKWorkoutActivityTypeBadminton": "Badminton",
    "HKWorkoutActivityTypeCycling": "Cycling",
    "HKWorkoutActivityTypeMixedCardio": "MixedCardio",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "HighIntensityIntervalTraining",
    "HKWorkoutActivityTypeHiking": "Hiking",
    "HKWorkoutActivityTypeCoreTraining": "CoreTraining",
    "HKWorkoutActivityTypeSwimming": "Swimming",
    "HKWorkoutActivityTypeRunning": "Running",
    "HKWorkoutActivityTypeRowing": "Rowing",
    "HKWorkoutActivityTypeFencing": "Fencing",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "TraditionalStrengthTraining",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "FunctionalStrengthTraining",
    "HKWorkoutActivityTypeYoga": "Yoga",
    "HKWorkoutActivityTypeDance": "Dance",
    "HKWorkoutActivityTypeTableTennis": "TableTennis",
    "HKWorkoutActivityTypeElliptical": "Elliptical",
    "HKWorkoutActivityTypePilates": "Pilates",
}

ACTIVITY_CN_MAP = {
    "Walking": "步行",
    "Badminton": "羽毛球",
    "Cycling": "骑行",
    "MixedCardio": "混合有氧",
    "HighIntensityIntervalTraining": "HIIT",
    "Hiking": "远足",
    "CoreTraining": "核心训练",
    "Swimming": "游泳",
    "Running": "跑步",
    "Rowing": "划船",
    "Fencing": "击剑",
    "TraditionalStrengthTraining": "力量训练",
    "FunctionalStrengthTraining": "功能性力量",
    "Yoga": "瑜伽",
    "Dance": "舞蹈",
    "TableTennis": "乒乓球",
    "Elliptical": "椭圆机",
    "Pilates": "普拉提",
}

DEFAULT_MAX_HR = 185
LOCAL_TZ = "Asia/Shanghai"

# 活动阈值
SEDENTARY_STEP_THRESHOLD = 3000
ACTIVE_STEP_THRESHOLD = 8000

# 睡眠过滤阈值
MAX_SLEEP_HOURS = 18
MIN_SLEEP_HOURS = 1
MAX_LATENCY_MINUTES = 180

# RHR 缺失时的默认值
FALLBACK_RHR = 65

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def load_csv(csv_dir: Path, name: str) -> pd.DataFrame | None:
    """加载 CSV 文件，不存在或为空则返回 None。"""
    p = csv_dir / name
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        if df.empty:
            return None
        return df
    except (pd.errors.ParserError, pd.errors.EmptyDataError, FileNotFoundError) as exc:
        logging.warning("无法解析 %s: %s", p, exc)
        return None


def parse_datetime_col(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """将日期列解析为 datetime，提取 date_only。"""
    df = df.copy()
    df[col] = pd.to_datetime(df[col], utc=True)
    df["date_only"] = df[col].dt.tz_convert(LOCAL_TZ).dt.date
    return df


def safe_float(df: pd.DataFrame, col: str = "value") -> pd.DataFrame:
    """确保 value 列为 float。"""
    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def pct_to_100(series: pd.Series) -> pd.Series:
    """如果数据看起来是小数形式 (0~1) 则 *100 转为百分比。
    判断标准: 中位数 <= 1 (更稳健，避免极端值干扰)。"""
    s = series.dropna()
    if s.empty:
        return series
    if s.median() <= 1.0:
        return (series * 100.0).clip(upper=100)
    return series.clip(upper=100)


def load_me_json(csv_dir: Path) -> dict:
    """读取 me.json，返回 dict。"""
    p = csv_dir / "me.json"
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning("无法解析 %s: %s", p, exc)
        return {}


def calc_age(birthday_str: str, ref_date: date | None = None) -> int | None:
    """从生日字符串计算年龄。"""
    try:
        bday = datetime.strptime(birthday_str, "%Y-%m-%d").date()
    except Exception:
        return None
    ref = ref_date or date.today()
    age = ref.year - bday.year - ((ref.month, ref.day) < (bday.month, bday.day))
    return age


def calc_max_hr(me: dict) -> int:
    """计算最大心率: 220 - age，或默认值。"""
    bday = me.get("HKCharacteristicTypeIdentifierDateOfBirth", "")
    age = calc_age(bday)
    if age is not None and 10 < age < 120:
        return 220 - age
    return DEFAULT_MAX_HR


def round_df(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    """对所有 float 列保留指定小数位。"""
    df = df.copy()
    float_cols = df.select_dtypes(include=["float64", "float32"]).columns
    df[float_cols] = df[float_cols].round(decimals)
    return df


def save_csv(df: pd.DataFrame, out_dir: Path, name: str) -> None:
    """保存 CSV 并打印信息。"""
    p = out_dir / name
    df = round_df(df)
    df.to_csv(p, index=False)
    size_kb = p.stat().st_size / 1024
    logging.info("  %s: %d 行, %.1f KB", name, len(df), size_kb)


# ---------------------------------------------------------------------------
# 1. daily_summary.csv
# ---------------------------------------------------------------------------


def build_daily_summary(csv_dir: Path) -> pd.DataFrame | None:
    """构建每日健康总览。"""
    logging.info("[1/11] 构建 daily_summary.csv ...")

    # 收集所有日期的聚合结果
    daily_parts = []

    # --- 步数 (sum) ---
    df = load_csv(csv_dir, "steps.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("steps_total")
        daily_parts.append(agg)

    # --- 距离 (sum, km) ---
    df = load_csv(csv_dir, "distance.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("distance_km")
        daily_parts.append(agg)

    # --- 骑行距离 (sum, km) ---
    df = load_csv(csv_dir, "distance_cycling.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("distance_cycling_km")
        daily_parts.append(agg)

    # --- 爬楼 (sum) ---
    df = load_csv(csv_dir, "flights.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("flights_climbed")
        daily_parts.append(agg)

    # --- 运动时长 (sum, min) ---
    df = load_csv(csv_dir, "exercise_time.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("exercise_min")
        daily_parts.append(agg)

    # --- 站立时长 (sum, min) ---
    df = load_csv(csv_dir, "stand_time.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("stand_min")
        daily_parts.append(agg)

    # --- 心率 (mean/min/max/std) ---
    df = load_csv(csv_dir, "heart_rate.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        g = df.groupby("date_only")["value"]
        daily_parts.append(g.mean().rename("hr_mean"))
        daily_parts.append(g.min().rename("hr_min"))
        daily_parts.append(g.max().rename("hr_max"))
        daily_parts.append(g.std().rename("hr_std"))

    # --- 静息心率 (mean → 通常每天一条) ---
    df = load_csv(csv_dir, "resting_heart_rate.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("resting_hr")
        daily_parts.append(agg)

    # --- 步行心率 (mean) ---
    df = load_csv(csv_dir, "walking_heart_rate.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("walking_hr_avg")
        daily_parts.append(agg)

    # --- HRV (mean) ---
    df = load_csv(csv_dir, "hrv.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("hrv_mean")
        daily_parts.append(agg)

    # --- 血氧 (mean/min/below95_count) ---
    df = load_csv(csv_dir, "spo2.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        # 检查单位：如果中位数 <= 1 则是小数形式 (0.98 = 98%)
        if df["value"].dropna().median() <= 1.0:
            df["value"] = df["value"] * 100.0
        g = df.groupby("date_only")["value"]
        daily_parts.append(g.mean().rename("spo2_mean"))
        daily_parts.append(g.min().rename("spo2_min"))
        # below95: 每天低于95%的读数计数，没有低于95的天填0
        below95_raw = df[df["value"] < 95].groupby("date_only")["value"].count()
        all_dates = g.first().index  # 所有有spo2数据的日期
        below95 = below95_raw.reindex(all_dates, fill_value=0).rename("spo2_below95_count")
        daily_parts.append(below95)

    # --- 呼吸频率 (mean) ---
    df = load_csv(csv_dir, "respiratory_rate.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("resp_rate_mean")
        daily_parts.append(agg)

    # --- VO2max (last) ---
    df = load_csv(csv_dir, "vo2max.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        df = df.sort_values("date")
        agg = df.groupby("date_only")["value"].last().rename("vo2max")
        daily_parts.append(agg)

    # --- 体重 (last) ---
    df = load_csv(csv_dir, "body_mass.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        df = df.sort_values("date")
        agg = df.groupby("date_only")["value"].last().rename("body_mass_kg")
        daily_parts.append(agg)

    # --- BMI (last) ---
    df = load_csv(csv_dir, "bmi.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        df = df.sort_values("date")
        agg = df.groupby("date_only")["value"].last().rename("bmi")
        daily_parts.append(agg)

    # --- 体脂率 (last) ---
    df = load_csv(csv_dir, "body_fat.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        df = df.sort_values("date")
        agg = df.groupby("date_only")["value"].last().rename("body_fat_pct")
        daily_parts.append(agg)

    # --- 步行速度 (mean, km/hr) ---
    df = load_csv(csv_dir, "walking_speed.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("walking_speed_mean")
        daily_parts.append(agg)

    # --- 步幅 (mean, cm) ---
    df = load_csv(csv_dir, "step_length.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("step_length_mean")
        daily_parts.append(agg)

    # --- 双腿支撑时间 (mean, %) ---
    df = load_csv(csv_dir, "double_support.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        df["value"] = pct_to_100(df["value"])
        agg = df.groupby("date_only")["value"].mean().rename("double_support_pct")
        daily_parts.append(agg)

    # --- 步态不对称 (mean, %) ---
    df = load_csv(csv_dir, "asymmetry.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        df["value"] = pct_to_100(df["value"])
        agg = df.groupby("date_only")["value"].mean().rename("asymmetry_pct")
        daily_parts.append(agg)

    # --- 上楼速度 (mean, m/s) ---
    df = load_csv(csv_dir, "stair_ascent.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("stair_ascent_speed")
        daily_parts.append(agg)

    # --- 下楼速度 (mean, m/s) ---
    df = load_csv(csv_dir, "stair_descent.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("stair_descent_speed")
        daily_parts.append(agg)

    # --- 步行稳定性 ---
    df = load_csv(csv_dir, "walking_steadiness.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        if df["value"].dropna().median() <= 1.0:
            df["value"] = df["value"] * 100.0
        agg = df.groupby("date_only")["value"].mean().rename("walking_steadiness")
        daily_parts.append(agg)

    # --- 日照 (sum, min) ---
    df = load_csv(csv_dir, "daylight.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("daylight_min")
        daily_parts.append(agg)

    # --- 环境噪音 (mean) ---
    df = load_csv(csv_dir, "env_noise.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("env_noise_mean")
        daily_parts.append(agg)

    # --- 耳机噪音 (mean) ---
    df = load_csv(csv_dir, "headphone_noise.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("headphone_noise_mean")
        daily_parts.append(agg)

    # --- 体力消耗 (mean) ---
    df = load_csv(csv_dir, "physical_effort.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].mean().rename("physical_effort_mean")
        daily_parts.append(agg)

    # --- 活动能量 (sum) ---
    df = load_csv(csv_dir, "active_energy.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("active_energy_kcal")
        daily_parts.append(agg)

    # --- 基础能量 (sum) ---
    df = load_csv(csv_dir, "basal_energy.csv")
    if df is not None:
        df = parse_datetime_col(safe_float(df))
        agg = df.groupby("date_only")["value"].sum().rename("basal_energy_kcal")
        daily_parts.append(agg)

    if not daily_parts:
        logging.warning("没有可用的原始 CSV 数据")
        return None

    # 合并所有日聚合
    daily = pd.concat(daily_parts, axis=1)
    daily.index.name = "date"
    daily = daily.reset_index()
    daily["date"] = pd.to_datetime(daily["date"])

    # 添加 weekday, is_weekend
    daily["weekday"] = daily["date"].dt.weekday
    daily["is_weekend"] = (daily["weekday"] >= 5).astype(int)

    # --- 活动环 (从 activity_summary.csv) ---
    act = load_csv(csv_dir, "activity_summary.csv")
    if act is not None:
        act["date"] = pd.to_datetime(act["date"])
        # 过滤掉异常早期数据
        act = act[act["date"] >= "2000-01-01"].copy()
        ring_cols = {}
        if "active_energy" in act.columns:
            ring_cols["active_energy"] = "ring_active_energy"
        if "active_energy_goal" in act.columns:
            ring_cols["active_energy_goal"] = "ring_active_energy_goal"
        if "exercise_min" in act.columns:
            ring_cols["exercise_min"] = "ring_exercise_min"
        if "exercise_goal" in act.columns:
            ring_cols["exercise_goal"] = "ring_exercise_goal"
        if "stand_hours" in act.columns:
            ring_cols["stand_hours"] = "ring_stand_hours"
        if "stand_goal" in act.columns:
            ring_cols["stand_goal"] = "ring_stand_goal"

        act_renamed = act[["date"] + list(ring_cols.keys())].rename(columns=ring_cols)
        daily = daily.merge(act_renamed, on="date", how="left")

        # 计算环完成百分比
        if "ring_active_energy" in daily.columns and "ring_active_energy_goal" in daily.columns:
            daily["ring_move_pct"] = np.where(
                daily["ring_active_energy_goal"] > 0,
                daily["ring_active_energy"] / daily["ring_active_energy_goal"] * 100,
                np.nan,
            )
        if "ring_exercise_min" in daily.columns and "ring_exercise_goal" in daily.columns:
            daily["ring_exercise_pct"] = np.where(
                daily["ring_exercise_goal"] > 0,
                daily["ring_exercise_min"] / daily["ring_exercise_goal"] * 100,
                np.nan,
            )
        if "ring_stand_hours" in daily.columns and "ring_stand_goal" in daily.columns:
            daily["ring_stand_pct"] = np.where(
                daily["ring_stand_goal"] > 0,
                daily["ring_stand_hours"] / daily["ring_stand_goal"] * 100,
                np.nan,
            )

        # rings_closed: 0-3
        rings_closed = pd.Series(0, index=daily.index, dtype=int)
        if "ring_move_pct" in daily.columns:
            rings_closed += (daily["ring_move_pct"] >= 100).astype(int)
        if "ring_exercise_pct" in daily.columns:
            rings_closed += (daily["ring_exercise_pct"] >= 100).astype(int)
        if "ring_stand_pct" in daily.columns:
            rings_closed += (daily["ring_stand_pct"] >= 100).astype(int)
        daily["rings_closed"] = rings_closed

    # --- 运动 (从 workouts.csv) ---
    wo = load_csv(csv_dir, "workouts.csv")
    if wo is not None:
        wo["start_date"] = pd.to_datetime(wo["start_date"], utc=True)
        wo["wo_date"] = wo["start_date"].dt.tz_convert("Asia/Shanghai").dt.date
        wo["wo_date"] = pd.to_datetime(wo["wo_date"])
        wo["duration_min"] = pd.to_numeric(wo["duration_min"], errors="coerce")
        wo["energy_kcal"] = pd.to_numeric(wo["energy_kcal"], errors="coerce")

        wo_daily = wo.groupby("wo_date").agg(
            workout_count=("duration_min", "count"),
            workout_total_min=("duration_min", "sum"),
            workout_total_kcal=("energy_kcal", "sum"),
            workout_types=("activity_type", lambda x: ",".join(sorted(set(
                ACTIVITY_TYPE_MAP.get(v, v) for v in x.dropna()
            )))),
        ).reset_index().rename(columns={"wo_date": "date"})

        daily = daily.merge(wo_daily, on="date", how="left")
        daily["workout_count"] = daily["workout_count"].fillna(0).astype(int)

    # 排序
    daily = daily.sort_values("date").reset_index(drop=True)

    return daily


# ---------------------------------------------------------------------------
# 2. nightly_sleep.csv
# ---------------------------------------------------------------------------


def build_nightly_sleep(csv_dir: Path) -> pd.DataFrame | None:
    """构建每晚睡眠会话。"""
    logging.info("[2/11] 构建 nightly_sleep.csv ...")

    df = load_csv(csv_dir, "sleep.csv")
    if df is None:
        logging.info("跳过: sleep.csv 不存在")
        return None

    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["end_date"] = pd.to_datetime(df["end_date"], utc=True)

    # 转为本地时间
    df["start_local"] = df["date"].dt.tz_convert("Asia/Shanghai")
    df["end_local"] = df["end_date"].dt.tz_convert("Asia/Shanghai")

    # 映射 sleep stage
    if "sleep_stage" in df.columns:
        df["stage"] = df["sleep_stage"].map(SLEEP_STAGE_MAP).fillna(df["sleep_stage"])
    elif "value" in df.columns:
        df["stage"] = df["value"].map(SLEEP_STAGE_MAP).fillna(df["value"])
    else:
        logging.info("跳过: 无法识别 sleep stage 列")
        return None

    # 归并为"晚上": startDate 18:00 之后 → 当天晚上; 之前 → 前一天晚上
    df["start_hour"] = df["start_local"].dt.hour
    df["night_date"] = df["start_local"].dt.date
    df.loc[df["start_hour"] < 18, "night_date"] = (
        pd.to_datetime(df.loc[df["start_hour"] < 18, "night_date"]) - timedelta(days=1)
    ).dt.date

    # 持续时间 (小时)
    df["duration_hours"] = (df["end_local"] - df["start_local"]).dt.total_seconds() / 3600

    # 按 night_date 聚合
    results = []
    for night, group in df.groupby("night_date"):
        group = group.sort_values("start_local")

        # bedtime / waketime (整个 session 的最早开始、最晚结束)
        bedtime = group["start_local"].min()
        waketime = group["end_local"].max()
        time_in_bed_hours = (waketime - bedtime).total_seconds() / 3600

        # 过滤异常
        if time_in_bed_hours > 18 or time_in_bed_hours < 1:
            continue

        # 各阶段时长
        stage_hours = {}
        for stage in ["Deep", "Core", "REM", "Awake", "Unspecified", "InBed"]:
            mask = group["stage"] == stage
            stage_hours[stage] = group.loc[mask, "duration_hours"].sum()

        deep_h = stage_hours.get("Deep", 0)
        core_h = stage_hours.get("Core", 0)
        rem_h = stage_hours.get("REM", 0)
        awake_h = stage_hours.get("Awake", 0)
        unspecified_h = stage_hours.get("Unspecified", 0)

        total_sleep = deep_h + core_h + rem_h + unspecified_h
        if total_sleep <= 0:
            # 如果没有有效的 sleep 数据，跳过
            continue

        # 百分比 (基于 total_sleep)
        deep_pct = deep_h / total_sleep * 100 if total_sleep > 0 else np.nan
        core_pct = core_h / total_sleep * 100 if total_sleep > 0 else np.nan
        rem_pct = rem_h / total_sleep * 100 if total_sleep > 0 else np.nan

        # 睡眠效率
        raw_efficiency = total_sleep / time_in_bed_hours if time_in_bed_hours > 0 else np.nan
        # Cap at 1.0 — 多数据源重叠可能导致 total_sleep > time_in_bed
        sleep_efficiency = min(raw_efficiency, 1.0) if pd.notna(raw_efficiency) else np.nan

        # 入睡潜伏期
        inbed_records = group[group["stage"] == "InBed"]
        asleep_records = group[group["stage"].isin(["Core", "Deep", "REM", "Unspecified"])]
        sleep_latency_min = np.nan
        if not inbed_records.empty and not asleep_records.empty:
            first_inbed = inbed_records["start_local"].min()
            first_asleep = asleep_records["start_local"].min()
            latency = (first_asleep - first_inbed).total_seconds() / 60
            if 0 <= latency <= 180:  # 合理范围
                sleep_latency_min = latency

        # 醒来次数 & 碎片化指数
        awake_records = group[group["stage"] == "Awake"]
        awake_count = len(awake_records)
        fragmentation_index = awake_count / total_sleep if total_sleep > 0 else np.nan

        # 数据来源
        source = group["source"].mode().iloc[0] if "source" in group.columns and not group["source"].empty else ""

        results.append({
            "night_date": night,
            "bedtime": bedtime.strftime("%Y-%m-%d %H:%M"),
            "waketime": waketime.strftime("%Y-%m-%d %H:%M"),
            "time_in_bed_hours": time_in_bed_hours,
            "total_sleep_hours": total_sleep,
            "deep_hours": deep_h,
            "core_hours": core_h,
            "rem_hours": rem_h,
            "awake_hours": awake_h,
            "unspecified_hours": unspecified_h,
            "deep_pct": deep_pct,
            "core_pct": core_pct,
            "rem_pct": rem_pct,
            "sleep_efficiency": sleep_efficiency,
            "sleep_latency_min": sleep_latency_min,
            "awake_count": awake_count,
            "fragmentation_index": fragmentation_index,
            "source": source,
        })

    if not results:
        logging.warning("没有有效的睡眠会话")
        return None

    sleep_df = pd.DataFrame(results)
    sleep_df["night_date"] = pd.to_datetime(sleep_df["night_date"])
    sleep_df = sleep_df.sort_values("night_date").reset_index(drop=True)

    return sleep_df


# ---------------------------------------------------------------------------
# 3. weekly_summary.csv
# ---------------------------------------------------------------------------


def build_weekly_summary(daily: pd.DataFrame | None, sleep: pd.DataFrame | None) -> pd.DataFrame | None:
    """从 daily_summary 按 ISO 周聚合。"""
    logging.info("[3/11] 构建 weekly_summary.csv ...")

    if daily is None or daily.empty:
        logging.info("跳过: daily_summary 不可用")
        return None

    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    # ISO 周: 周一为一周的开始
    df["week_start"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")

    agg_dict = {}
    if "steps_total" in df.columns:
        agg_dict["steps_avg"] = ("steps_total", "mean")
        agg_dict["steps_total"] = ("steps_total", "sum")
    if "distance_km" in df.columns:
        agg_dict["distance_total_km"] = ("distance_km", "sum")
    if "exercise_min" in df.columns:
        agg_dict["exercise_min_total"] = ("exercise_min", "sum")
    if "workout_count" in df.columns:
        agg_dict["workout_count"] = ("workout_count", "sum")
    if "workout_total_min" in df.columns:
        agg_dict["workout_min_total"] = ("workout_total_min", "sum")
    if "resting_hr" in df.columns:
        agg_dict["hr_resting_avg"] = ("resting_hr", "mean")
    if "hrv_mean" in df.columns:
        agg_dict["hrv_avg"] = ("hrv_mean", "mean")
    if "spo2_mean" in df.columns:
        agg_dict["spo2_avg"] = ("spo2_mean", "mean")
    if "rings_closed" in df.columns:
        agg_dict["rings_closed_avg"] = ("rings_closed", "mean")

    if not agg_dict:
        print("  跳过: 没有可聚合的列")
        return None

    weekly = df.groupby("week_start").agg(**agg_dict).reset_index()

    # sedentary_days & active_days
    if "steps_total" in df.columns:
        sed = df.groupby("week_start")["steps_total"].apply(lambda x: (x < 3000).sum()).rename("sedentary_days")
        act = df.groupby("week_start")["steps_total"].apply(lambda x: (x >= 8000).sum()).rename("active_days")
        weekly = weekly.merge(sed, on="week_start", how="left")
        weekly = weekly.merge(act, on="week_start", how="left")

    # 从 nightly_sleep 合并周均睡眠
    if sleep is not None and not sleep.empty:
        sl = sleep.copy()
        sl["night_date"] = pd.to_datetime(sl["night_date"])
        sl["week_start"] = sl["night_date"] - pd.to_timedelta(sl["night_date"].dt.weekday, unit="D")
        sl_weekly = sl.groupby("week_start").agg(
            sleep_avg_hours=("total_sleep_hours", "mean"),
        ).reset_index()

        # 平均就寝时间 (用 bedtime 的 hour 部分)
        sl["bedtime_dt"] = pd.to_datetime(sl["bedtime"])
        sl["bedtime_hour_raw"] = sl["bedtime_dt"].dt.hour + sl["bedtime_dt"].dt.minute / 60
        # 把 18-23 点映射为 -6 到 -1，0-12 点映射为 0-12
        sl["bedtime_hour_adj"] = sl["bedtime_hour_raw"].apply(
            lambda x: x - 24 if x >= 18 else x
        )
        bedtime_avg = sl.groupby("week_start")["bedtime_hour_adj"].mean().rename("bedtime_avg_hour")
        # 转回正常小时表示
        bedtime_avg = bedtime_avg.apply(lambda x: x + 24 if x < 0 else x)

        sl_weekly = sl_weekly.merge(bedtime_avg, on="week_start", how="left")
        weekly = weekly.merge(sl_weekly, on="week_start", how="left")

    weekly = weekly.sort_values("week_start").reset_index(drop=True)
    return weekly


# ---------------------------------------------------------------------------
# 4. monthly_summary.csv
# ---------------------------------------------------------------------------


def build_monthly_summary(
    daily: pd.DataFrame | None, sleep: pd.DataFrame | None
) -> pd.DataFrame | None:
    """按自然月聚合。"""
    print("\n[4/11] 构建 monthly_summary.csv ...")

    if daily is None or daily.empty:
        print("  跳过: daily_summary 不可用")
        return None

    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")

    agg_dict = {}
    if "steps_total" in df.columns:
        agg_dict["steps_avg"] = ("steps_total", "mean")
        agg_dict["steps_total"] = ("steps_total", "sum")
    if "distance_km" in df.columns:
        agg_dict["distance_total_km"] = ("distance_km", "sum")
    if "exercise_min" in df.columns:
        agg_dict["exercise_min_total"] = ("exercise_min", "sum")
    if "workout_count" in df.columns:
        agg_dict["workout_count"] = ("workout_count", "sum")
    if "workout_total_min" in df.columns:
        agg_dict["workout_min_total"] = ("workout_total_min", "sum")
    if "resting_hr" in df.columns:
        agg_dict["hr_resting_avg"] = ("resting_hr", "mean")
    if "hrv_mean" in df.columns:
        agg_dict["hrv_avg"] = ("hrv_mean", "mean")
    if "spo2_mean" in df.columns:
        agg_dict["spo2_avg"] = ("spo2_mean", "mean")
    if "rings_closed" in df.columns:
        agg_dict["rings_closed_avg"] = ("rings_closed", "mean")

    if not agg_dict:
        print("  跳过: 没有可聚合的列")
        return None

    monthly = df.groupby("month").agg(**agg_dict).reset_index()

    # sedentary_days & active_days
    if "steps_total" in df.columns:
        sed = df.groupby("month")["steps_total"].apply(lambda x: (x < 3000).sum()).rename("sedentary_days")
        act = df.groupby("month")["steps_total"].apply(lambda x: (x >= 8000).sum()).rename("active_days")
        monthly = monthly.merge(sed, on="month", how="left")
        monthly = monthly.merge(act, on="month", how="left")

        # 变异系数
        cv = df.groupby("month")["steps_total"].apply(
            lambda x: x.std() / x.mean() * 100 if x.mean() > 0 else np.nan
        ).rename("steps_cv")
        monthly = monthly.merge(cv, on="month", how="left")

    # 睡眠相关
    if sleep is not None and not sleep.empty:
        sl = sleep.copy()
        sl["night_date"] = pd.to_datetime(sl["night_date"])
        sl["month"] = sl["night_date"].dt.to_period("M")

        sl_monthly = sl.groupby("month").agg(
            sleep_avg_hours=("total_sleep_hours", "mean"),
        ).reset_index()

        # bedtime_avg_hour
        sl["bedtime_dt"] = pd.to_datetime(sl["bedtime"])
        sl["bedtime_hour_raw"] = sl["bedtime_dt"].dt.hour + sl["bedtime_dt"].dt.minute / 60
        sl["bedtime_hour_adj"] = sl["bedtime_hour_raw"].apply(lambda x: x - 24 if x >= 18 else x)
        bedtime_avg = sl.groupby("month")["bedtime_hour_adj"].mean().rename("bedtime_avg_hour")
        bedtime_avg = bedtime_avg.apply(lambda x: x + 24 if x < 0 else x)
        sl_monthly = sl_monthly.merge(bedtime_avg, on="month", how="left")

        # 睡眠规律性: 100 - (bedtime_std_min + waketime_std_min) / 2
        sl["waketime_dt"] = pd.to_datetime(sl["waketime"])
        sl["waketime_hour_raw"] = sl["waketime_dt"].dt.hour + sl["waketime_dt"].dt.minute / 60
        # bedtime 标准差 (分钟)
        bedtime_std = sl.groupby("month")["bedtime_hour_adj"].std().rename("bedtime_std_hours")
        waketime_std = sl.groupby("month")["waketime_hour_raw"].std().rename("waketime_std_hours")
        regularity = pd.concat([bedtime_std, waketime_std], axis=1)
        regularity["sleep_regularity_approx"] = 100 - (
            regularity["bedtime_std_hours"] * 60 + regularity["waketime_std_hours"] * 60
        ) / 2
        sl_monthly = sl_monthly.merge(
            regularity[["sleep_regularity_approx"]], on="month", how="left"
        )

        monthly = monthly.merge(sl_monthly, on="month", how="left")

    # GQI (步态质量指数)
    gait_cols_needed = ["walking_speed_mean", "step_length_mean", "double_support_pct", "asymmetry_pct"]
    gait_available = [c for c in gait_cols_needed if c in df.columns]
    if gait_available:
        gait_means = df.groupby("month")[gait_available].mean()

        def calc_gqi(row):
            speed = row.get("walking_speed_mean", np.nan)
            length = row.get("step_length_mean", np.nan)
            ds = row.get("double_support_pct", np.nan)
            asym = row.get("asymmetry_pct", np.nan)

            scores = []
            weights = []

            if pd.notna(speed):
                speed_score = min(100, (speed / 6.0) * 100)
                scores.append(speed_score)
                weights.append(0.30)
            if pd.notna(length):
                length_score = min(100, (length / 80.0) * 100)
                scores.append(length_score)
                weights.append(0.25)
            if pd.notna(ds):
                support_score = min(100, max(0, (40 - ds) / 20 * 100))
                scores.append(support_score)
                weights.append(0.25)
            if pd.notna(asym):
                asym_score = min(100, max(0, (10 - asym) / 10 * 100))
                scores.append(asym_score)
                weights.append(0.20)

            if not scores:
                return np.nan
            # 加权平均 (归一化权重)
            total_w = sum(weights)
            return sum(s * w for s, w in zip(scores, weights)) / total_w

        gait_means["gqi_score"] = gait_means.apply(calc_gqi, axis=1)
        monthly = monthly.merge(
            gait_means[["gqi_score"]], on="month", how="left"
        )

    # 将 Period 转为字符串
    monthly["month"] = monthly["month"].astype(str)
    monthly = monthly.sort_values("month").reset_index(drop=True)

    return monthly


# ---------------------------------------------------------------------------
# 5. hr_hourly.csv
# ---------------------------------------------------------------------------


def build_hr_hourly(csv_dir: Path) -> pd.DataFrame | None:
    """心率按小时聚合。"""
    print("\n[5/11] 构建 hr_hourly.csv ...")

    df = load_csv(csv_dir, "heart_rate.csv")
    if df is None:
        print("  跳过: heart_rate.csv 不存在")
        return None

    df = safe_float(df)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["local_dt"] = df["date"].dt.tz_convert("Asia/Shanghai")
    df["date_only"] = df["local_dt"].dt.date
    df["hour"] = df["local_dt"].dt.hour

    hourly = df.groupby(["date_only", "hour"])["value"].agg(
        hr_mean="mean",
        hr_min="min",
        hr_max="max",
        hr_count="count",
    ).reset_index()
    hourly = hourly.rename(columns={"date_only": "date"})
    hourly = hourly.sort_values(["date", "hour"]).reset_index(drop=True)

    return hourly


# ---------------------------------------------------------------------------
# 6. hr_zones_daily.csv
# ---------------------------------------------------------------------------


def build_hr_zones_daily(csv_dir: Path, max_hr: int) -> pd.DataFrame | None:
    """每日心率区间分布。"""
    print("\n[6/11] 构建 hr_zones_daily.csv ...")

    df = load_csv(csv_dir, "heart_rate.csv")
    if df is None:
        print("  跳过: heart_rate.csv 不存在")
        return None

    df = safe_float(df)
    df = parse_datetime_col(df)

    # 计算心率区间边界
    z1_floor = max_hr * 0.50
    z2_floor = max_hr * 0.60
    z3_floor = max_hr * 0.70
    z4_floor = max_hr * 0.80
    z5_floor = max_hr * 0.90

    def assign_zone(hr):
        if pd.isna(hr):
            return np.nan
        if hr < z1_floor:
            return 0
        elif hr < z2_floor:
            return 1
        elif hr < z3_floor:
            return 2
        elif hr < z4_floor:
            return 3
        elif hr < z5_floor:
            return 4
        else:
            return 5

    df["zone"] = df["value"].apply(assign_zone)

    results = []
    for dt, group in df.groupby("date_only"):
        total = len(group)
        row = {"date": dt}
        for z in range(6):
            cnt = (group["zone"] == z).sum()
            row[f"zone{z}_count"] = cnt
            row[f"zone{z}_pct"] = cnt / total * 100 if total > 0 else 0
        results.append(row)

    zones = pd.DataFrame(results)
    zones = zones.sort_values("date").reset_index(drop=True)

    print(f"  最大心率: {max_hr}, 区间边界: Z1>{z1_floor:.0f}, Z2>{z2_floor:.0f}, "
          f"Z3>{z3_floor:.0f}, Z4>{z4_floor:.0f}, Z5>{z5_floor:.0f}")

    return zones


# ---------------------------------------------------------------------------
# 7. workout_enriched.csv
# ---------------------------------------------------------------------------


def build_workout_enriched(csv_dir: Path, max_hr: int) -> pd.DataFrame | None:
    """运动记录增强版。"""
    print("\n[7/11] 构建 workout_enriched.csv ...")

    df = load_csv(csv_dir, "workouts.csv")
    if df is None:
        print("  跳过: workouts.csv 不存在")
        return None

    df["start_date"] = pd.to_datetime(df["start_date"], utc=True)
    df["end_date"] = pd.to_datetime(df["end_date"], utc=True)
    df["start_local"] = df["start_date"].dt.tz_convert("Asia/Shanghai")
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")
    df["energy_kcal"] = pd.to_numeric(df["energy_kcal"], errors="coerce")
    df["hr_avg"] = pd.to_numeric(df.get("hr_avg", pd.Series(dtype=float)), errors="coerce")
    df["hr_min"] = pd.to_numeric(df.get("hr_min", pd.Series(dtype=float)), errors="coerce")
    df["hr_max"] = pd.to_numeric(df.get("hr_max", pd.Series(dtype=float)), errors="coerce")

    # 时间特征
    df["weekday"] = df["start_local"].dt.weekday
    df["hour"] = df["start_local"].dt.hour
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)

    # 活动类型映射
    df["activity_type_short"] = df["activity_type"].map(ACTIVITY_TYPE_MAP).fillna(
        df["activity_type"].str.replace("HKWorkoutActivityType", "", regex=False)
    )
    df["activity_type_cn"] = df["activity_type_short"].map(ACTIVITY_CN_MAP).fillna(df["activity_type_short"])

    # RHR 估计 (使用 resting HR 的中位数，如果不可用则用 65)
    rhr_csv = load_csv(csv_dir, "resting_heart_rate.csv")
    rhr_estimate = 65
    if rhr_csv is not None:
        rhr_csv = safe_float(rhr_csv)
        rhr_median = rhr_csv["value"].median()
        if pd.notna(rhr_median):
            rhr_estimate = rhr_median

    # TRIMP
    def calc_trimp(row):
        if pd.isna(row["hr_avg"]) or pd.isna(row["duration_min"]):
            return np.nan
        hr_fraction = (row["hr_avg"] - rhr_estimate) / (max_hr - rhr_estimate)
        if hr_fraction < 0:
            hr_fraction = 0
        return row["duration_min"] * hr_fraction

    df["trimp"] = df.apply(calc_trimp, axis=1)

    # kcal/min
    df["kcal_per_min"] = np.where(
        df["duration_min"] > 0,
        df["energy_kcal"] / df["duration_min"],
        np.nan,
    )

    # pace (min/km) — 仅步行/跑步/骑行
    pace_types = {"Walking", "Running", "Cycling", "Hiking"}
    df["pace_min_per_km"] = np.nan
    mask = df["activity_type_short"].isin(pace_types) & (df["distance_km"] > 0)
    df.loc[mask, "pace_min_per_km"] = df.loc[mask, "duration_min"] / df.loc[mask, "distance_km"]

    # 整理输出列
    out_cols = [
        "activity_type", "activity_type_short", "activity_type_cn",
        "start_date", "end_date", "duration_min", "distance_km",
        "energy_kcal", "hr_avg", "hr_min", "hr_max",
        "weekday", "hour", "is_weekend",
        "trimp", "kcal_per_min", "pace_min_per_km",
    ]
    # 只保留存在的列
    out_cols = [c for c in out_cols if c in df.columns]
    df = df[out_cols].sort_values("start_date").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# 8. body_composition.csv
# ---------------------------------------------------------------------------


def build_body_composition(csv_dir: Path) -> pd.DataFrame | None:
    """身体成分时间序列。"""
    print("\n[8/11] 构建 body_composition.csv ...")

    parts = []

    for fname, col_name in [
        ("body_mass.csv", "body_mass_kg"),
        ("bmi.csv", "bmi"),
        ("body_fat.csv", "body_fat_pct"),
    ]:
        df = load_csv(csv_dir, fname)
        if df is not None:
            df = parse_datetime_col(safe_float(df))
            df = df.sort_values("date")
            agg = df.groupby("date_only")["value"].last().rename(col_name)
            parts.append(agg)

    if not parts:
        print("  跳过: 没有找到 body_mass/bmi/body_fat CSV")
        return None

    body = pd.concat(parts, axis=1)
    body.index.name = "date"
    body = body.reset_index()

    # 计算瘦体重
    if "body_mass_kg" in body.columns and "body_fat_pct" in body.columns:
        fat_pct = body["body_fat_pct"]
        # 如果 body_fat_pct max < 1 则是小数
        if not fat_pct.dropna().empty and fat_pct.dropna().median() <= 1.0:
            fat_pct = fat_pct * 100
        body["lean_body_mass_kg"] = body["body_mass_kg"] * (1 - fat_pct / 100)

    body = body.sort_values("date").reset_index(drop=True)
    return body


# ---------------------------------------------------------------------------
# 9. data_quality.csv
# ---------------------------------------------------------------------------


def build_data_quality(csv_dir: Path) -> pd.DataFrame:
    """数据质量报告。"""
    print("\n[9/11] 构建 data_quality.csv ...")

    csv_files = sorted(Path(csv_dir).glob("*.csv"))
    results = []

    for csv_path in csv_files:
        name = csv_path.stem
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue

        if df.empty:
            continue

        total_records = len(df)

        # 日期范围
        date_col = "date" if "date" in df.columns else None
        if date_col is None:
            # activity_summary 等
            for candidate in ["start_date", "date"]:
                if candidate in df.columns:
                    date_col = candidate
                    break

        date_range_start = None
        date_range_end = None
        days_with_data = 0
        total_calendar_days = 0
        coverage_pct = 0

        if date_col and date_col in df.columns:
            try:
                dates = pd.to_datetime(df[date_col], utc=True, errors="coerce")
                dates_valid = dates.dropna()
                if not dates_valid.empty:
                    date_range_start = dates_valid.min().strftime("%Y-%m-%d")
                    date_range_end = dates_valid.max().strftime("%Y-%m-%d")
                    day_series = dates_valid.dt.date
                    days_with_data = day_series.nunique()
                    total_calendar_days = (dates_valid.max() - dates_valid.min()).days + 1
                    coverage_pct = days_with_data / total_calendar_days * 100 if total_calendar_days > 0 else 0
            except Exception:
                pass

        # null value
        value_col = "value" if "value" in df.columns else None
        null_value_count = 0
        null_value_pct = 0
        if value_col:
            null_value_count = df[value_col].isna().sum()
            null_value_pct = null_value_count / total_records * 100

        # source distribution
        source_dist = "{}"
        if "source" in df.columns:
            try:
                vc = df["source"].value_counts(normalize=True)
                dist = {str(k): round(v * 100, 1) for k, v in vc.items()}
                source_dist = json.dumps(dist, ensure_ascii=False)
            except Exception:
                pass

        # tier
        if coverage_pct >= 80:
            tier = "A"
        elif coverage_pct >= 50:
            tier = "B"
        elif coverage_pct >= 20:
            tier = "C"
        else:
            tier = "D"

        results.append({
            "indicator": name,
            "total_records": total_records,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "days_with_data": days_with_data,
            "total_calendar_days": total_calendar_days,
            "coverage_pct": coverage_pct,
            "null_value_count": null_value_count,
            "null_value_pct": null_value_pct,
            "source_distribution": source_dist,
            "tier": tier,
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# 10. wearing_gaps.csv
# ---------------------------------------------------------------------------


def build_wearing_gaps(csv_dir: Path) -> pd.DataFrame | None:
    """佩戴间隙检测。"""
    print("\n[10/11] 构建 wearing_gaps.csv ...")

    df = load_csv(csv_dir, "heart_rate.csv")
    if df is None:
        print("  跳过: heart_rate.csv 不存在")
        return None

    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").reset_index(drop=True)

    # 计算相邻记录之间的间隔
    df["next_date"] = df["date"].shift(-1)
    df["gap_seconds"] = (df["next_date"] - df["date"]).dt.total_seconds()

    results = []
    for _, row in df.iterrows():
        gap_sec = row["gap_seconds"]
        if pd.isna(gap_sec):
            continue

        gap_hours = gap_sec / 3600

        gap_start = row["date"]
        gap_end = row["next_date"]
        gap_start_local = gap_start.tz_convert("Asia/Shanghai")
        gap_end_local = gap_end.tz_convert("Asia/Shanghai")
        start_hour = gap_start_local.hour

        # 判断 gap 类型
        is_daytime = 8 <= start_hour <= 22

        if gap_hours >= 4:
            gap_type = "definite"
        elif gap_hours >= 2 and is_daytime:
            gap_type = "daytime"
        elif gap_hours >= 2 and not is_daytime:
            gap_type = "nighttime"
        else:
            continue  # 间隔 < 2h，不记录

        results.append({
            "gap_start": gap_start_local.strftime("%Y-%m-%d %H:%M"),
            "gap_end": gap_end_local.strftime("%Y-%m-%d %H:%M"),
            "gap_hours": gap_hours,
            "gap_type": gap_type,
        })

    if not results:
        print("  没有检测到佩戴间隙")
        return pd.DataFrame(columns=["gap_start", "gap_end", "gap_hours", "gap_type"])

    gaps = pd.DataFrame(results)
    gaps = gaps.sort_values("gap_start").reset_index(drop=True)

    return gaps


# ---------------------------------------------------------------------------
# 11. sleep_steps_correlation.csv
# ---------------------------------------------------------------------------


def build_sleep_steps_correlation(
    daily: pd.DataFrame | None, sleep: pd.DataFrame | None
) -> pd.DataFrame | None:
    """睡眠-活动关联表。"""
    print("\n[11/11] 构建 sleep_steps_correlation.csv ...")

    if daily is None or sleep is None:
        print("  跳过: daily_summary 或 nightly_sleep 不可用")
        return None

    if daily.empty or sleep.empty:
        print("  跳过: 数据为空")
        return None

    # 准备 daily 数据
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])

    # 准备 sleep 数据
    s = sleep[["night_date", "total_sleep_hours", "deep_pct", "sleep_efficiency"]].copy()
    s["night_date"] = pd.to_datetime(s["night_date"])

    # bedtime hour
    s_full = sleep.copy()
    s_full["night_date"] = pd.to_datetime(s_full["night_date"])
    if "bedtime" in s_full.columns:
        s_full["bedtime_dt"] = pd.to_datetime(s_full["bedtime"])
        s_full["bedtime_hour"] = s_full["bedtime_dt"].dt.hour + s_full["bedtime_dt"].dt.minute / 60
        s = s.merge(s_full[["night_date", "bedtime_hour"]], on="night_date", how="left")

    # prev_day = night_date (睡前一天的活动)
    # next_day = night_date + 1 (睡后一天)
    s["prev_day"] = s["night_date"]
    s["next_day"] = s["night_date"] + timedelta(days=1)

    # 合并前一天活动数据
    prev_cols = {}
    if "steps_total" in d.columns:
        prev_cols["steps_total"] = "prev_day_steps"
    if "exercise_min" in d.columns:
        prev_cols["exercise_min"] = "prev_day_exercise_min"
    if "workout_count" in d.columns:
        prev_cols["workout_count"] = "prev_day_workout_count"

    if prev_cols:
        d_prev = d[["date"] + list(prev_cols.keys())].rename(
            columns={**{"date": "prev_day"}, **prev_cols}
        )
        s = s.merge(d_prev, on="prev_day", how="left")

    # 合并后一天数据
    next_cols = {}
    if "steps_total" in d.columns:
        next_cols["steps_total"] = "next_day_steps"
    if "resting_hr" in d.columns:
        next_cols["resting_hr"] = "next_day_resting_hr"
    if "hrv_mean" in d.columns:
        next_cols["hrv_mean"] = "next_day_hrv"

    if next_cols:
        d_next = d[["date"] + list(next_cols.keys())].rename(
            columns={**{"date": "next_day"}, **next_cols}
        )
        s = s.merge(d_next, on="next_day", how="left")

    # 清理输出列
    out_cols = [
        "night_date", "total_sleep_hours", "deep_pct", "bedtime_hour", "sleep_efficiency",
        "prev_day_steps", "prev_day_exercise_min", "prev_day_workout_count",
        "next_day_steps", "next_day_resting_hr", "next_day_hrv",
    ]
    out_cols = [c for c in out_cols if c in s.columns]
    s = s[out_cols].sort_values("night_date").reset_index(drop=True)

    return s


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) != 3:
        print(f"用法: python3 {sys.argv[0]} <csv_dir> <output_dir>")
        sys.exit(1)

    csv_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])

    if not csv_dir.exists():
        print(f"错误: CSV 目录不存在: {csv_dir}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"输入目录: {csv_dir}")
    print(f"输出目录: {out_dir}")
    print(f"CSV 文件数: {len(list(csv_dir.glob('*.csv')))}")

    # 读取 me.json
    me = load_me_json(csv_dir)
    max_hr = calc_max_hr(me)
    bday = me.get("HKCharacteristicTypeIdentifierDateOfBirth", "未知")
    age = calc_age(bday) if bday != "未知" else None
    print(f"生日: {bday}, 年龄: {age}, 最大心率: {max_hr}")

    # ========== 构建各数据集 ==========

    # 1. daily_summary
    daily = build_daily_summary(csv_dir)
    if daily is not None:
        save_csv(daily, out_dir, "daily_summary.csv")

    # 2. nightly_sleep
    sleep = build_nightly_sleep(csv_dir)
    if sleep is not None:
        save_csv(sleep, out_dir, "nightly_sleep.csv")

    # 3. weekly_summary
    weekly = build_weekly_summary(daily, sleep)
    if weekly is not None:
        save_csv(weekly, out_dir, "weekly_summary.csv")

    # 4. monthly_summary
    monthly = build_monthly_summary(daily, sleep)
    if monthly is not None:
        save_csv(monthly, out_dir, "monthly_summary.csv")

    # 5. hr_hourly
    hr_hourly = build_hr_hourly(csv_dir)
    if hr_hourly is not None:
        save_csv(hr_hourly, out_dir, "hr_hourly.csv")

    # 6. hr_zones_daily
    hr_zones = build_hr_zones_daily(csv_dir, max_hr)
    if hr_zones is not None:
        save_csv(hr_zones, out_dir, "hr_zones_daily.csv")

    # 7. workout_enriched
    wo = build_workout_enriched(csv_dir, max_hr)
    if wo is not None:
        save_csv(wo, out_dir, "workout_enriched.csv")

    # 8. body_composition
    body = build_body_composition(csv_dir)
    if body is not None:
        save_csv(body, out_dir, "body_composition.csv")

    # 9. data_quality
    quality = build_data_quality(csv_dir)
    save_csv(quality, out_dir, "data_quality.csv")

    # 10. wearing_gaps
    gaps = build_wearing_gaps(csv_dir)
    if gaps is not None:
        save_csv(gaps, out_dir, "wearing_gaps.csv")

    # 11. sleep_steps_correlation
    corr = build_sleep_steps_correlation(daily, sleep)
    if corr is not None:
        save_csv(corr, out_dir, "sleep_steps_correlation.csv")

    # ========== 总结 ==========
    print("\n" + "=" * 50)
    print("全部完成! 输出文件:")
    total_size = 0
    for f in sorted(out_dir.glob("*.csv")):
        sz = f.stat().st_size
        total_size += sz
        # 已在 save_csv 中打印过
    print(f"总计大小: {total_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
