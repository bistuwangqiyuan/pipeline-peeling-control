"""复现论文图 5-6 / 5-7 / 5-8（高端科技蓝深色风格）。

运行：
    python -m analysis.figures

输出 PNG 到 public/assets/figures/：
    fig_5_6_force_displacement.png   实测拉力-位移曲线（P1016R-02F 第30条带）
    fig_5_7_heatmap.png              剥离力空间分布热力图（全 82 条带）
    fig_5_8_histogram.png            剥离力幅值分布直方图（双峰特征）

所有图均由脚本直接读取原始 CSV 绘制，全过程可复现。
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from .dataset import (
    DATA_DIR,
    GOOD_BOND_PLATFORM_N,
    PASS_THRESHOLD_N,
    load_sample,
)

# 中文字体（Windows 优先 YaHei，回退 SimHei / DejaVu）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public", "assets", "figures",
)

# 科技蓝深色主题
BG = "#0a1428"
PANEL = "#0d1b33"
GRID = "#1d3a5f"
CYAN = "#22d3ee"
BLUE = "#3b82f6"
GREEN = "#34d399"
RED = "#f87171"
TEXT = "#cfe6ff"

CMAP = LinearSegmentedColormap.from_list(
    "peeling", ["#05192e", "#0e3a5f", "#1f7a8c", "#22d3ee", "#bdf3ff"]
)


def _style(ax):
    ax.set_facecolor(PANEL)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=TEXT)
    ax.grid(True, color=GRID, alpha=0.4, linewidth=0.6)
    ax.title.set_color(TEXT)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)


def fig_force_displacement(matrix: np.ndarray, strip_idx: int = 29) -> str:
    strip_idx = min(strip_idx, matrix.shape[1] - 1)
    force = matrix[:, strip_idx]
    pos = np.arange(force.size) * 1.0
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=130)
    fig.patch.set_facecolor(BG)
    _style(ax)
    ax.plot(pos, force, color=CYAN, lw=1.1)
    ax.fill_between(pos, force, color=CYAN, alpha=0.12)
    ax.axhline(GOOD_BOND_PLATFORM_N, color=GREEN, ls="--", lw=1,
               label=f"良好粘接平台 ~{GOOD_BOND_PLATFORM_N:.0f}N")
    ax.axhline(PASS_THRESHOLD_N, color=RED, ls=":", lw=1,
               label=f"合格阈值 {PASS_THRESHOLD_N:.0f}N")
    ax.set_xlabel("剥离位移 / mm")
    ax.set_ylabel("剥离力 / N")
    ax.set_title(f"实测拉力-位移曲线  P1016R-02F  第{strip_idx + 1}条带"
                 f"（峰值{force.max():.1f}N / 均值{force.mean():.1f}N）")
    ax.set_ylim(0, max(110, force.max() * 1.1))
    leg = ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="lower left")
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig_5_6_force_displacement.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def fig_heatmap(matrix: np.ndarray) -> str:
    # x = 位移(mm), y = 条带编号
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=130)
    fig.patch.set_facecolor(BG)
    _style(ax)
    ax.grid(False)
    data = matrix.T  # [strip, position]
    im = ax.imshow(data, aspect="auto", origin="lower", cmap=CMAP,
                   extent=[0, data.shape[1], 1, data.shape[0]],
                   vmin=0, vmax=max(100, np.percentile(data, 99)))
    ax.set_xlabel("剥离位移 / mm")
    ax.set_ylabel("条带编号（沿管周，每条 20mm）")
    ax.set_title("补口剥离力空间分布热力图  P1016R-02F（82 条带 / 近 2.8m 行程）")
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("剥离力 / N", color=TEXT)
    cbar.ax.yaxis.set_tick_params(color=TEXT)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=TEXT)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig_5_7_heatmap.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def fig_histogram(matrix: np.ndarray) -> str:
    flat = matrix.reshape(-1)
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=130)
    fig.patch.set_facecolor(BG)
    _style(ax)
    n, bins, patches = ax.hist(flat, bins=60, color=BLUE, alpha=0.85,
                               edgecolor="#0a1428", linewidth=0.4)
    # 高值峰着色为青色
    for b, p in zip(bins[:-1], patches):
        if b >= 80:
            p.set_facecolor(CYAN)
        elif b < 40:
            p.set_facecolor(RED)
    ax.axvline(PASS_THRESHOLD_N, color=GREEN, ls="--", lw=1.2,
               label=f"合格阈值 {PASS_THRESHOLD_N:.0f}N")
    ax.set_xlabel("剥离力 / N")
    ax.set_ylabel("采样点频数")
    pass_rate = 100.0 * (flat >= PASS_THRESHOLD_N).mean()
    ax.set_title(f"补口剥离力幅值分布直方图  P1016R-02F"
                 f"（双峰：~96N 良好粘接 / 20~30N 缺陷；合格率 {pass_rate:.1f}%）")
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig_5_8_histogram.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def run() -> list[str]:
    os.makedirs(OUT_DIR, exist_ok=True)
    matrix = load_sample(os.path.join(DATA_DIR, "P1016R-02F.csv"))
    outs = [
        fig_force_displacement(matrix),
        fig_heatmap(matrix),
        fig_histogram(matrix),
    ]
    for o in outs:
        print("generated", os.path.relpath(o))
    return outs


if __name__ == "__main__":
    run()
