"""由真实数据集生成数据库种子（可复现）。

运行：
    python -m analysis.seed

输出 analysis/seed_data.json，供 api/init_db.py 在首次初始化时写入：
projects / tests / results(逐条带统计) / data_points(降采样力-位序列)。

逐条带统计基于"全分辨率"原始数据计算（保证统计准确），
data_points 序列按步长降采样（保证 Neon 免费额度与前端流畅）。
"""
from __future__ import annotations

import json
import os

import numpy as np

from .dataset import (
    DATA_DIR,
    PASS_THRESHOLD_N,
    STRIP_WIDTH_MM,
    load_sample,
)

OUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_data.json")

MAX_STRIPS_PER_TEST = 30      # 大屏最多展示 30 条，故每个试验入库 <=30 条带
TARGET_POINTS_PER_STRIP = 140  # 每条带降采样后约 140 个力-位点
PEEL_SPEED_MM_MIN = 10.0       # 标准恒速 10 mm/min

# 真实样本 -> 项目/试验 映射（确定性，便于复现）
PROJECTS = [
    {
        "key": "proj_wq3_1016",
        "name": "西气东输三线 Φ1016 补口剥离检测",
        "description": "Φ1016 mm 大口径管道补口热收缩带圆周剥离质量验证。",
        "pipe_diameter": 1016, "layer_width": 600, "layer_thickness": 1.0,
        "location": "甘肃·张掖压气站", "status": "completed",
        "tests": [
            {"sample": "P1016R-02F.csv", "test_number": "WQ3-1016-02F", "operator": "代玮晗"},
        ],
    },
    {
        "key": "proj_cre_1219",
        "name": "中俄东线 Φ1219 补口剥离检测",
        "description": "Φ1219 mm 管道补口防腐层圆周剥离力-位同步采集。",
        "pipe_diameter": 1219, "layer_width": 600, "layer_thickness": 1.0,
        "location": "黑龙江·黑河首站", "status": "completed",
        "tests": [
            {"sample": "P1219R-01F.csv", "test_number": "CRE-1219-01F", "operator": "代玮晗"},
            {"sample": "P1219R-02F.csv", "test_number": "CRE-1219-02F", "operator": "王启源"},
        ],
    },
    {
        "key": "proj_plate_p300",
        "name": "板型试样标定批次 P300",
        "description": "300×300 mm 板型补口试样剥离强度标定与缺陷复现。",
        "pipe_diameter": 0, "layer_width": 300, "layer_thickness": 1.0,
        "location": "实验室·标定台", "status": "completed",
        "tests": [
            {"sample": "P300-08.csv", "test_number": "P300-08", "operator": "实验室"},
            {"sample": "P300-05.csv", "test_number": "P300-05", "operator": "实验室"},
        ],
    },
    {
        "key": "proj_plate_p600",
        "name": "板型试样批次 P600",
        "description": "300×600 mm 板型补口试样剥离力空间分布评估。",
        "pipe_diameter": 0, "layer_width": 600, "layer_thickness": 1.0,
        "location": "实验室·标定台", "status": "completed",
        "tests": [
            {"sample": "P600-05.csv", "test_number": "P600-05", "operator": "实验室"},
        ],
    },
]


def _build_test(matrix: np.ndarray, threshold: float = PASS_THRESHOLD_N):
    n_pos, n_strip = matrix.shape
    n_strip = min(n_strip, MAX_STRIPS_PER_TEST)
    matrix = matrix[:, :n_strip]

    results = []
    for j in range(n_strip):
        col = matrix[:, j]
        results.append({
            "strip_number": j + 1,
            "avg_force": round(float(col.mean()), 4),
            "max_force": round(float(col.max()), 4),
            "min_force": round(float(col.min()), 4),
            "std_force": round(float(col.std()), 4),
            "total_displacement": round(float(n_pos), 4),
            "pass_fail": bool(col.mean() >= threshold),
        })

    stride = max(1, n_pos // TARGET_POINTS_PER_STRIP)
    idx = np.arange(0, n_pos, stride)
    points = []
    for j in range(n_strip):
        col = matrix[:, j]
        for i in idx:
            points.append({
                "strip_number": j + 1,
                "position_mm": round(float(i), 2),
                "force_value": round(float(col[i]), 4),
                "speed": PEEL_SPEED_MM_MIN,
            })

    flat = matrix.reshape(-1)
    meta = {
        "n_strips": n_strip,
        "n_positions": n_pos,
        "max_force": round(float(flat.max()), 2),
        "mean_force": round(float(flat.mean()), 2),
        "pass_rate": round(100.0 * (flat >= threshold).mean(), 2),
        "peel_speed": PEEL_SPEED_MM_MIN,
        "strip_width": STRIP_WIDTH_MM,
    }
    return meta, results, points


def build() -> dict:
    out = {"projects": [], "tests": [], "results": [], "data_points": []}
    for proj in PROJECTS:
        out["projects"].append({k: proj[k] for k in (
            "key", "name", "description", "pipe_diameter",
            "layer_width", "layer_thickness", "location", "status")})
        for t in proj["tests"]:
            path = os.path.join(DATA_DIR, t["sample"])
            if not os.path.exists(path):
                continue
            matrix = load_sample(path)
            if matrix.size == 0:
                continue
            meta, results, points = _build_test(matrix)
            test_key = t["test_number"]
            out["tests"].append({
                "key": test_key,
                "project_key": proj["key"],
                "test_number": t["test_number"],
                "sample_name": t["sample"],
                "operator": t["operator"],
                "status": "completed",
                **meta,
            })
            for r in results:
                out["results"].append({"test_key": test_key, **r})
            for p in points:
                out["data_points"].append({"test_key": test_key, **p})
    return out


def run() -> str:
    data = build()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"projects={len(data['projects'])} tests={len(data['tests'])} "
          f"results={len(data['results'])} data_points={len(data['data_points'])}")
    print("written", os.path.relpath(OUT_JSON))
    return OUT_JSON


if __name__ == "__main__":
    run()
