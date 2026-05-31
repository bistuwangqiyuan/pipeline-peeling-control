"""实时大屏数据源：真实数据回放（replay）。

设计原则（应需求"取消大屏自动 mock 数据增长，以实际数据驱动"）：
    - 不再生成任何随机/合成（mock）力值。
    - 试验启动时，从已入库的真实试样数据（data_points，来源于真实 CSV 种子）
      捕获逐条带"力-位"序列，存入 tests.profiles 作为回放模板。
    - 实时轮询时，仅按位置游标"揭示"模板中的真实数据点（写入运行中试验的
      data_points），不做任何插值/生成。

数据来源：
    - 若该试验自身已有真实数据点（例如对种子真实试样重新启动），回放其自身曲线；
    - 否则选取数据点最多的真实完成试验作为代表性回放源（如 P1016R-02F）。
"""
import datetime

import psycopg2.extras

from .db import get_connection, query

FORCE_SENSOR_RANGE = 1000.0   # S 型传感器量程 0–1000 N
PASS_THRESHOLD = 70.0         # 合格阈值
MAX_STRIPS = 30               # 大屏最多展示 30 条带
PLAYBACK_POLLS = 100          # 完整回放所需轮询数（200ms × 100 ≈ 20s）


def _fetch_series(test_id):
    """读取某试验的逐条带真实力-位序列（按条带、位置升序）。"""
    rows = query(
        """SELECT strip_number, position_mm, force_value, speed
           FROM data_points WHERE test_id = %s
           ORDER BY strip_number, position_mm""",
        (test_id,), fetchall=True
    )
    series = {}
    for r in rows or []:
        series.setdefault(int(r['strip_number']), []).append([
            float(r['position_mm']),
            float(r['force_value']),
            float(r['speed']) if r['speed'] is not None else 10.0,
        ])
    return series


def pick_source_test(exclude_test_id=None):
    """选取数据点最多的真实试验作为回放源。"""
    row = query(
        """SELECT test_id, COUNT(*) AS c FROM data_points
           WHERE (%s::int IS NULL OR test_id <> %s)
           GROUP BY test_id ORDER BY c DESC LIMIT 1""",
        (exclude_test_id, exclude_test_id), fetchone=True
    )
    return int(row['test_id']) if row else None


def build_replay_template(test_id):
    """构建真实数据回放模板。

    返回 {'replay': {strip_str: [[pos, force, speed], ...]},
          'max_pos': float, 'n_strips': int, 'source_test_id': int|None}
    无可用真实数据时返回 None。
    """
    series = _fetch_series(test_id)
    source = None
    if sum(len(v) for v in series.values()) < 10:
        src = pick_source_test(exclude_test_id=test_id)
        if src is None:
            return None
        series = _fetch_series(src)
        source = src

    strips = sorted(series.keys())[:MAX_STRIPS]
    replay = {str(s): series[s] for s in strips if series[s]}
    if not replay:
        return None

    max_pos = 0.0
    for s in strips:
        if series[s]:
            max_pos = max(max_pos, series[s][-1][0])

    return {
        'replay': replay,
        'max_pos': round(max_pos, 2),
        'n_strips': len(replay),
        'source_test_id': source,
    }


def playback_step(max_pos):
    """每次轮询推进的位置步长（mm）。"""
    return max(1.0, float(max_pos) / PLAYBACK_POLLS)


def reveal(test_id, template, old_pos, new_pos):
    """揭示位置区间 (old_pos, new_pos] 内的真实数据点并写入运行中试验。"""
    replay = (template or {}).get('replay', {})
    now = datetime.datetime.utcnow()
    rows = []
    for s_str, pts in replay.items():
        try:
            s = int(s_str)
        except (TypeError, ValueError):
            continue
        for p in pts:
            pos = float(p[0])
            force = float(p[1])
            speed = float(p[2]) if len(p) > 2 else 10.0
            if old_pos < pos <= new_pos:
                rows.append((test_id, s, round(pos, 2), round(force, 4),
                             round(speed, 2), now))

    if not rows:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO data_points
                   (test_id, strip_number, position_mm, force_value, speed, timestamp)
                   VALUES %s""",
                rows
            )
            conn.commit()
    finally:
        conn.close()
    return len(rows)


def compute_test_summary(test_id, threshold=PASS_THRESHOLD):
    """试验结束后回写整体峰值与合格率到 tests 表。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT MAX(force_value) AS max_force,
                          AVG(CASE WHEN force_value >= %s THEN 1.0 ELSE 0.0 END) * 100 AS pass_rate
                   FROM data_points WHERE test_id = %s""",
                (threshold, test_id)
            )
            row = cur.fetchone()
            max_force = float(row[0]) if row and row[0] is not None else 0.0
            pass_rate = float(row[1]) if row and row[1] is not None else 0.0
            cur.execute(
                "UPDATE tests SET max_force = %s, pass_rate = %s WHERE id = %s",
                (round(max_force, 2), round(pass_rate, 2), test_id)
            )
            conn.commit()
    finally:
        conn.close()
    return {'max_force': max_force, 'pass_rate': pass_rate}
