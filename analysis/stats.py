"""复算并校验论文统计指标（表 5-4 与 5.7 节代表性试样）。

运行：
    python -m analysis.stats

输出全数据集统计，并与论文公布值对照（带容差断言），同时给出
代表性管道试样 P1016R-02F 的合格率（论文称 70.9%）。所有数字均由
本脚本直接读取原始 CSV 计算，全过程可复现。
"""
from __future__ import annotations

import os

from .dataset import (
    DATA_DIR,
    PASS_THRESHOLD_N,
    dataset_metrics,
    load_sample,
    sample_metrics,
)

# 论文公布值（表 5-4 / 5.7 节）
PAPER = {
    "n_samples": 679,            # 674 板型 + 5 管道
    "mean_force": 60.83,
    "mean_peak_force": 98.49,
    "pass_rate_pct": 47.5,
    "representative_pass_pct": 70.9,  # P1016R-02F
}


def _fmt(label, got, expect, unit="", tol=2.0):
    ok = abs(got - expect) <= tol
    flag = "OK " if ok else "DIFF"
    return f"  [{flag}] {label:<22} 计算={got:8.2f}{unit}  论文={expect:.2f}{unit}", ok


def run() -> bool:
    print("=" * 64)
    print("管道补口剥离力数据集统计复算（论文表 5-4）")
    print("=" * 64)
    m = dataset_metrics()
    print(f"  试样数量            : {m['n_samples']} ({m['kinds']})")
    print(f"  剥离条带总数        : {m['total_strips']}")
    print(f"  力-位采样点总数     : {m['total_points']:,}")
    print("-" * 64)
    lines = []
    all_ok = True
    for label, key, paperkey, unit, tol in [
        ("平均剥离力", "mean_force", "mean_force", " N", 1.5),
        ("平均峰值剥离力", "mean_peak_force", "mean_peak_force", " N", 1.0),
        ("全集合格率(>=70N)", "pass_rate_points_pct", "pass_rate_pct", " %", 1.5),
    ]:
        line, ok = _fmt(label, m[key], PAPER[paperkey], unit, tol)
        lines.append(line)
        all_ok = all_ok and ok
    print("\n".join(lines))

    # 代表性管道试样 P1016R-02F
    rep_path = os.path.join(DATA_DIR, "P1016R-02F.csv")
    if os.path.exists(rep_path):
        sm = sample_metrics("P1016R-02F", load_sample(rep_path))
        print("-" * 64)
        print(f"  代表性试样 P1016R-02F: {sm.n_strips} 条带 x {sm.n_positions} mm")
        print(f"    峰值={sm.max_force:.1f}N  均值={sm.mean_force:.1f}N")
        line, ok = _fmt("  合格率(采样点>=70N)", sm.pass_rate_points,
                        PAPER["representative_pass_pct"], " %", 2.0)
        print(line)
        all_ok = all_ok and ok
    print("=" * 64)
    print("结论:", "全部指标与论文一致(容差内)" if all_ok else "存在偏差(见上)")
    return all_ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
