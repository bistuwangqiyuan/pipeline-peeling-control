# 可复现数据建模层 `analysis/`

本目录将论文中的全部数据结论以 Python 程序化、可复现的方式实现。所有数字均
直接读取真实数据集 `数据-拉力值1mm纵轴20mm横轴条带/`（679 个 CSV，每列=20mm
条带，每行=1mm 位置采样点）计算得到。

## 环境

```bash
pip install -r analysis/requirements-analysis.txt
```

## 命令

| 命令 | 作用 | 复现的论文内容 |
|------|------|----------------|
| `python -m analysis.stats` | 复算并校验全数据集统计 | 表 5-4：均值 60.83N、峰值均值 98.49N、合格率 47.5%；代表样 P1016R-02F 合格率 70.9% |
| `python -m analysis.figures` | 生成 3 张图到 `public/assets/figures/` | 图 5-6 力-位曲线、图 5-7 热力图、图 5-8 直方图 |
| `python -m analysis.seed` | 由真实样本生成 `analysis/seed_data.json` | 数据库种子（4 项目 / 6 试验 / 真实力-位序列） |

## 统计口径（与论文对照）

- 平均剥离力 = 全部力值采样点的算术均值。
- 平均峰值剥离力 = 每个试样峰值（最大力）的均值。
- 合格率(≥70N) = 力值 ≥ 70N 的采样点占比（70N ≈ 35 N/cm，论文示例阈值）。
- 良好粘接平台力值 ≈ 96 N；S 型传感器量程 0–1000 N。

运行 `python -m analysis.stats` 的退出码为 0 表示全部指标与论文公布值在容差内一致。
