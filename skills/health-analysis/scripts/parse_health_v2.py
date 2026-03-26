#!/usr/bin/env python3
"""Apple Health ETL v2 — 单次遍历 export.xml，输出多个 CSV 文件。

用法:
    python3 parse_health_v2.py <input_xml> <output_dir>

特性:
    - iterparse 流式解析，内存友好
    - 覆盖 35+ 种 Record 类型 + Workout + ActivitySummary + Me
    - 保留数据源 (source) 和设备 (device) 信息
    - 幂等：可重复运行，输出覆盖已有文件
"""

import csv
import json
import logging
import os
import re
import sys
import time
from io import TextIOWrapper
from xml.etree.ElementTree import iterparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Record type -> CSV filename 映射
# ---------------------------------------------------------------------------
RECORD_TYPE_MAP: dict[str, str] = {
    # Tier 1
    "HKQuantityTypeIdentifierStepCount": "steps.csv",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate.csv",
    "HKQuantityTypeIdentifierVO2Max": "vo2max.csv",
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep.csv",
    "HKQuantityTypeIdentifierBodyMass": "body_mass.csv",
    "HKQuantityTypeIdentifierBodyMassIndex": "bmi.csv",
    "HKQuantityTypeIdentifierHeight": "height.csv",
    # Tier 2
    "HKQuantityTypeIdentifierHeartRate": "heart_rate.csv",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv.csv",
    "HKQuantityTypeIdentifierOxygenSaturation": "spo2.csv",
    "HKQuantityTypeIdentifierAppleWalkingSteadiness": "walking_steadiness.csv",
    "HKQuantityTypeIdentifierSixMinuteWalkTestDistance": "six_min_walk.csv",
    "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute": "hrr1.csv",
    "HKCategoryTypeIdentifierHighHeartRateEvent": "high_hr_event.csv",
    # Tier 3
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_energy.csv",
    "HKQuantityTypeIdentifierBasalEnergyBurned": "basal_energy.csv",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance.csv",
    "HKQuantityTypeIdentifierDistanceCycling": "distance_cycling.csv",
    "HKQuantityTypeIdentifierFlightsClimbed": "flights.csv",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_time.csv",
    "HKQuantityTypeIdentifierAppleStandTime": "stand_time.csv",
    "HKQuantityTypeIdentifierWalkingSpeed": "walking_speed.csv",
    "HKQuantityTypeIdentifierWalkingStepLength": "step_length.csv",
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": "double_support.csv",
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": "asymmetry.csv",
    "HKQuantityTypeIdentifierStairAscentSpeed": "stair_ascent.csv",
    "HKQuantityTypeIdentifierStairDescentSpeed": "stair_descent.csv",
    "HKQuantityTypeIdentifierPhysicalEffort": "physical_effort.csv",
    "HKQuantityTypeIdentifierTimeInDaylight": "daylight.csv",
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure": "env_noise.csv",
    "HKQuantityTypeIdentifierHeadphoneAudioExposure": "headphone_noise.csv",
    "HKQuantityTypeIdentifierRespiratoryRate": "respiratory_rate.csv",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "walking_heart_rate.csv",
    "HKQuantityTypeIdentifierBodyFatPercentage": "body_fat.csv",
    "HKQuantityTypeIdentifierLeanBodyMass": "lean_body_mass.csv",
    "HKCategoryTypeIdentifierAppleStandHour": "stand_hour.csv",
    "HKCategoryTypeIdentifierHandwashingEvent": "handwashing.csv",
    "HKQuantityTypeIdentifierEnvironmentalSoundReduction": "sound_reduction.csv",
}

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
_DEVICE_NAME_RE = re.compile(r"name:([^,>]+)")


def extract_device_name(device_str: str | None) -> str:
    """从 HKDevice 字符串中提取设备名称。

    输入示例: '<<HKDevice: ...>, name:Apple Watch, manufacturer:Apple ..>'
    输出: 'Apple Watch'
    """
    if not device_str:
        return ""
    m = _DEVICE_NAME_RE.search(device_str)
    return m.group(1).strip() if m else device_str.strip()


def safe_float(val: str | None, default: str = "") -> str:
    """尝试转为 float 字符串，失败则返回默认值。"""
    if val is None:
        return default
    try:
        return str(float(val))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# 主解析逻辑
# ---------------------------------------------------------------------------
def parse(input_xml: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()

    # --- 打开所有 CSV writer ---
    csv_files: dict[str, tuple[TextIOWrapper, csv.writer]] = {}
    record_counts: dict[str, int] = {}  # filename -> row count

    def get_writer(filename: str, header: list[str]) -> csv.writer:
        if filename not in csv_files:
            fpath = os.path.join(output_dir, filename)
            fh = open(fpath, "w", newline="", encoding="utf-8")
            w = csv.writer(fh)
            w.writerow(header)
            csv_files[filename] = (fh, w)
            record_counts[filename] = 0
        return csv_files[filename][1]

    # 预创建所有 Record CSV 的 header
    standard_header = ["date", "end_date", "value", "unit", "source", "device"]
    workout_header = [
        "activity_type", "start_date", "end_date", "duration_min",
        "distance_km", "energy_kcal", "source", "device",
        "hr_avg", "hr_min", "hr_max",
    ]
    activity_header = [
        "date", "active_energy", "active_energy_goal",
        "exercise_min", "exercise_goal", "stand_hours", "stand_goal",
    ]

    # --- 状态追踪 ---
    unmapped_types: dict[str, int] = {}
    total_records = 0
    workout_count = 0
    activity_count = 0
    me_data: dict | None = None

    # 当前 Workout 暂存心率数据
    pending_hr: dict[str, str] = {}  # avg/min/max
    in_workout = False  # 是否正在处理 Workout 子元素

    # --- iterparse：监听 start 和 end 事件 ---
    context = iterparse(input_xml, events=("start", "end"))

    # 捕获根元素用于定期释放内存
    root = None

    try:
        for event, elem in context:
            if event == "start":
                tag = elem.tag

                # 捕获根元素引用
                if root is None:
                    root = elem

                if tag == "Workout":
                    in_workout = True
                    pending_hr = {"avg": "", "min": "", "max": ""}
                continue

            # event == "end"
            tag = elem.tag

            if tag == "Record":
                total_records += 1
                if total_records % 500_000 == 0:
                    elapsed = time.time() - t0
                    logging.info("已处理 %s 条记录 (%.1fs)", f"{total_records:,}", elapsed)

                rtype = elem.get("type", "")
                filename = RECORD_TYPE_MAP.get(rtype)

                if filename is None:
                    unmapped_types[rtype] = unmapped_types.get(rtype, 0) + 1
                else:
                    date = elem.get("startDate", "")
                    end_date = elem.get("endDate", "")
                    value = elem.get("value", "")
                    unit = elem.get("unit", "")
                    source = elem.get("sourceName", "")
                    device = extract_device_name(elem.get("device"))

                    w = get_writer(filename, standard_header)
                    w.writerow([date, end_date, value, unit, source, device])

                    record_counts[filename] += 1

                elem.clear()
                if root is not None:
                    root.clear()

            elif tag == "WorkoutStatistics":
                # 只在 Workout 内部处理
                if in_workout:
                    ws_type = elem.get("type", "")
                    if "HeartRate" in ws_type and "Variability" not in ws_type and "Recovery" not in ws_type:
                        pending_hr["avg"] = elem.get("average", "")
                        pending_hr["min"] = elem.get("minimum", "")
                        pending_hr["max"] = elem.get("maximum", "")
                elem.clear()

            elif tag == "Workout":
                workout_count += 1
                w = get_writer("workouts.csv", workout_header)

                # activity_type: 去掉 HKWorkoutActivityType 前缀
                activity_type = elem.get("workoutActivityType", "")
                activity_type = activity_type.replace("HKWorkoutActivityType", "")

                start_date = elem.get("startDate", "")
                end_date = elem.get("endDate", "")
                duration = safe_float(elem.get("duration", ""))
                distance = safe_float(elem.get("totalDistance", ""))
                energy = safe_float(elem.get("totalEnergyBurned", ""))
                source = elem.get("sourceName", "")
                device = extract_device_name(elem.get("device"))

                w.writerow([
                    activity_type, start_date, end_date,
                    duration, distance, energy,
                    source, device,
                    pending_hr.get("avg", ""),
                    pending_hr.get("min", ""),
                    pending_hr.get("max", ""),
                ])
                record_counts["workouts.csv"] += 1

                # 重置
                in_workout = False
                pending_hr = {}
                elem.clear()
                if root is not None:
                    root.clear()

            elif tag == "ActivitySummary":
                activity_count += 1
                w = get_writer("activity_summary.csv", activity_header)
                w.writerow([
                    elem.get("dateComponents", ""),
                    safe_float(elem.get("activeEnergyBurned", "")),
                    safe_float(elem.get("activeEnergyBurnedGoal", "")),
                    safe_float(elem.get("appleExerciseTime", "")),
                    safe_float(elem.get("appleExerciseTimeGoal", "")),
                    safe_float(elem.get("appleStandHours", "")),
                    safe_float(elem.get("appleStandHoursGoal", "")),
                ])
                record_counts["activity_summary.csv"] += 1
                elem.clear()
                if root is not None:
                    root.clear()

            elif tag == "Me":
                me_data = dict(elem.attrib)
                elem.clear()

            else:
                # 对于不关心的元素也及时清理
                # 但只清理顶层或已处理的元素
                # 注意：不要清理 HealthData 等父容器，否则会破坏 iterparse
                pass

    finally:
        # --- 关闭所有 CSV ---
        for fh, _ in csv_files.values():
            fh.close()

    # --- 写出 me.json ---
    me_json_path = os.path.join(output_dir, "me.json")
    if me_data:
        with open(me_json_path, "w", encoding="utf-8") as f:
            json.dump(me_data, f, ensure_ascii=False, indent=2)

    # --- 最终报告 ---
    elapsed = time.time() - t0
    logging.info("")
    logging.info("=" * 60)
    logging.info("Apple Health ETL v2 — 解析完成")
    logging.info("=" * 60)
    logging.info("总耗时: %.1fs", elapsed)
    logging.info("Record 总数: %s", f"{total_records:,}")
    logging.info("Workout 总数: %s", f"{workout_count:,}")
    logging.info("ActivitySummary 总数: %s", f"{activity_count:,}")
    logging.info("")

    logging.info("--- 输出文件 ---")
    all_files = sorted(record_counts.items(), key=lambda x: -x[1])
    for filename, count in all_files:
        fpath = os.path.join(output_dir, filename)
        size = os.path.getsize(fpath)
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        logging.info("  %s %s 行  %s", f"{filename:<35s}", f"{count:>10,}", f"{size_str:>10s}")

    if me_data:
        me_size = os.path.getsize(me_json_path)
        logging.info("  %s %s  %s B", f"{'me.json':<35s}", f"{'':>10s}", f"{me_size:>10}")

    # --- 未映射类型 ---
    if unmapped_types:
        logging.info("")
        logging.info("--- 未映射 Record 类型 (%d 种) ---", len(unmapped_types))
        for rtype, cnt in sorted(unmapped_types.items(), key=lambda x: -x[1]):
            logging.info("  %s %s", f"{rtype:<60s}", f"{cnt:>10,}")
    else:
        logging.info("")
        logging.info("所有 Record 类型均已映射。")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) != 3:
        logging.warning("用法: %s <input_xml> <output_dir>", sys.argv[0])
        sys.exit(1)

    input_xml = sys.argv[1]
    output_dir = sys.argv[2]

    if not os.path.isfile(input_xml):
        logging.warning("错误: 文件不存在 — %s", input_xml)
        sys.exit(1)

    logging.info("输入: %s", input_xml)
    logging.info("输出目录: %s", output_dir)
    logging.info("")

    parse(input_xml, output_dir)


if __name__ == "__main__":
    main()
