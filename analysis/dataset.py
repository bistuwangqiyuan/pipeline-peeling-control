"""管道补口剥离力真实数据集读取与统计建模（可复现）。

数据组织（论文 5.7 节）：
    目录 ``数据-拉力值1mm纵轴20mm横轴条带`` 下每个 CSV = 一个试样；
    每一列 = 一条宽 20 mm 的剥离条带；
    每一行 = 沿剥离方向每 1 mm 的一个力值采样点（单位 N）。

本模块只依赖标准库 + numpy，提供：
    - load_sample(path)         读取单个 CSV 为二维 ndarray [position, strip]
    - iter_samples(root)        惰性遍历全部试样
    - sample_metrics(matrix)    单试样的逐条带与整体统计
    - dataset_metrics(root)     全数据集统计（复现论文表 5-4）

所有统计口径在 metrics 字典中以显式键给出，保证"数据有理有据、可复算"。
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

# 数据目录（相对仓库根）。可用环境变量覆盖。
DATA_DIR = os.environ.get(
    "PEELING_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "数据-拉力值1mm纵轴20mm横轴条带"),
)

# 工程常量（论文 2.1 / 3.2 / 5.7）
STRIP_WIDTH_MM = 20.0          # 每条带宽度
POSITION_STEP_MM = 1.0         # 纵轴每 1 mm 一个采样点
FORCE_SENSOR_RANGE_N = 1000.0  # S 型传感器量程 0–1000 N
PASS_THRESHOLD_N = 70.0        # 示例合格阈值（≈35 N/cm）
GOOD_BOND_PLATFORM_N = 96.0    # 良好粘接平台力值


def _sample_kind(name: str) -> str:
    """根据文件名前缀判定试样类别。"""
    base = name.upper()
    if base.startswith("P1016") or base.startswith("P1219"):
        return "pipe"
    if base.startswith("P600"):
        return "plate_p600"
    if base.startswith("P300"):
        return "plate_p300"
    return "other"


def load_sample(path: str) -> np.ndarray:
    """读取单个 CSV 为二维数组 matrix[position_index, strip_index]（单位 N）。"""
    rows: list[list[float]] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for raw in csv.reader(f):
            if not raw or not any(c.strip() for c in raw):
                continue
            vals: list[float] = []
            for c in raw:
                c = c.strip()
                if c == "":
                    continue
                try:
                    vals.append(float(c))
                except ValueError:
                    pass
            if vals:
                rows.append(vals)
    if not rows:
        return np.empty((0, 0), dtype=float)
    width = min(len(r) for r in rows)
    matrix = np.array([r[:width] for r in rows], dtype=float)
    return matrix


@dataclass
class SampleMetrics:
    name: str
    kind: str
    n_strips: int
    n_positions: int
    n_points: int
    mean_force: float
    max_force: float
    min_force: float
    strip_mean: list[float] = field(default_factory=list)
    strip_max: list[float] = field(default_factory=list)
    strip_min: list[float] = field(default_factory=list)
    pass_rate_points: float = 0.0   # 采样点 ≥ 阈值占比
    pass_rate_strips: float = 0.0   # 条带均值 ≥ 阈值占比


def sample_metrics(name: str, matrix: np.ndarray,
                   threshold: float = PASS_THRESHOLD_N) -> SampleMetrics:
    if matrix.size == 0:
        return SampleMetrics(name, _sample_kind(name), 0, 0, 0, 0, 0, 0)
    n_pos, n_strip = matrix.shape
    strip_mean = matrix.mean(axis=0)
    strip_max = matrix.max(axis=0)
    strip_min = matrix.min(axis=0)
    flat = matrix.reshape(-1)
    return SampleMetrics(
        name=name,
        kind=_sample_kind(name),
        n_strips=n_strip,
        n_positions=n_pos,
        n_points=flat.size,
        mean_force=float(flat.mean()),
        max_force=float(flat.max()),
        min_force=float(flat.min()),
        strip_mean=[float(x) for x in strip_mean],
        strip_max=[float(x) for x in strip_max],
        strip_min=[float(x) for x in strip_min],
        pass_rate_points=float((flat >= threshold).mean() * 100.0),
        pass_rate_strips=float((strip_mean >= threshold).mean() * 100.0),
    )


def iter_samples(root: str = DATA_DIR) -> Iterator[tuple[str, np.ndarray]]:
    for name in sorted(os.listdir(root)):
        if not name.lower().endswith(".csv"):
            continue
        yield name, load_sample(os.path.join(root, name))


def dataset_metrics(root: str = DATA_DIR,
                    threshold: float = PASS_THRESHOLD_N) -> dict:
    """复现论文表 5-4 的全数据集统计。"""
    n_samples = 0
    kinds: dict[str, int] = {}
    total_strips = 0
    total_points = 0
    sum_force = 0.0                 # 用于均值（按采样点加权）
    sample_peak_values: list[float] = []  # 每个试样的峰值，用于"平均峰值剥离力"
    strip_mean_values: list[float] = []   # 每条带均值，用于条带级合格率
    pass_points = 0

    for name, matrix in iter_samples(root):
        if matrix.size == 0:
            continue
        n_samples += 1
        kind = _sample_kind(name)
        kinds[kind] = kinds.get(kind, 0) + 1
        n_pos, n_strip = matrix.shape
        total_strips += n_strip
        flat = matrix.reshape(-1)
        total_points += flat.size
        sum_force += float(flat.sum())
        pass_points += int((flat >= threshold).sum())
        sample_peak_values.append(float(matrix.max()))
        strip_mean_values.extend(matrix.mean(axis=0).tolist())

    peaks = np.array(sample_peak_values, dtype=float)
    means = np.array(strip_mean_values, dtype=float)
    return {
        "n_samples": n_samples,
        "kinds": kinds,
        "total_strips": total_strips,
        "total_points": total_points,
        "mean_force": sum_force / total_points if total_points else 0.0,
        "mean_peak_force": float(peaks.mean()) if peaks.size else 0.0,
        "pass_rate_points_pct": 100.0 * pass_points / total_points if total_points else 0.0,
        "pass_rate_strips_pct": 100.0 * float((means >= threshold).mean()) if means.size else 0.0,
        "threshold": threshold,
    }


if __name__ == "__main__":
    m = dataset_metrics()
    print(m)
