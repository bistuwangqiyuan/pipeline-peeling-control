"""剥离力实时仿真模型（对齐真实数据集特征）。

物理依据（论文 5.7 + 真实数据集）：
    - 力值量程 0–1000 N，良好粘接区呈 ~96 N 平台；
    - 缺陷区（弱粘 / 气泡 / 脱粘）出现显著力值下凹，最低可至 0 N；
    - 起剥瞬态存在上升段，剥离沿条带长度方向以 1 mm 为采样间隔推进。

仿真按"位置(mm)"推进，为每条带生成一条含平台 + 随机缺陷下凹 + 噪声的
力-位曲线，写入 data_points 表，整体形态与 P1016R-02F 等真实样本一致。
"""
import math
import random
import datetime
from .db import get_connection
import psycopg2.extras


PLATFORM_MIN = 82.0          # 良好粘接平台下限
PLATFORM_MAX = 98.0          # 良好粘接平台上限
RAMP_MM = 20.0               # 起剥上升段长度
NOISE_RATIO = 0.03           # 噪声比例
FORCE_SENSOR_RANGE = 1000.0  # 传感器量程


def generate_strip_profiles(strip_count=30, total_mm=600.0):
    """为每条带生成剥离力剖面：平台值 + 若干缺陷下凹区间。"""
    profiles = []
    for i in range(strip_count):
        platform = random.uniform(PLATFORM_MIN, PLATFORM_MAX)
        n_defects = random.choices([0, 1, 2, 3], weights=[35, 35, 20, 10])[0]
        defects = []
        for _ in range(n_defects):
            width = random.uniform(20, 120)
            start = random.uniform(RAMP_MM, max(RAMP_MM, total_mm - width))
            depth = random.uniform(0.4, 1.0)   # 力值下凹比例
            defects.append({'start': start, 'end': start + width, 'depth': depth})
        profiles.append({
            'strip_number': i + 1,
            'platform': round(platform, 2),
            'defects': defects,
        })
    return profiles


def force_at(position, total_mm, profile):
    """给定位置(mm)返回该条带剥离力(N)。"""
    platform = profile['platform']
    if position < RAMP_MM:
        base = platform * (position / RAMP_MM)
    else:
        base = platform

    factor = 1.0
    for d in profile.get('defects', []):
        if d['start'] <= position <= d['end']:
            # 以半正弦形成平滑下凹
            t = (position - d['start']) / max(1e-6, (d['end'] - d['start']))
            dip = math.sin(t * math.pi)
            factor = min(factor, 1.0 - d['depth'] * dip)

    force = base * max(0.0, factor)
    if force > 0:
        force += random.gauss(0, force * NOISE_RATIO)
    return max(0.0, min(FORCE_SENSOR_RANGE, force))


def generate_simulation_batch(test_id, profiles, current_position, total_mm,
                              speed_mm_min=10.0):
    """在当前位置为所有条带生成一帧力-位数据并写库。"""
    now = datetime.datetime.utcnow()
    rows = []
    for profile in profiles:
        f = force_at(current_position, total_mm, profile)
        rows.append((
            test_id, profile['strip_number'], round(current_position, 2),
            round(f, 4), round(speed_mm_min, 2), now
        ))

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
    return rows


def compute_test_summary(test_id, threshold=70.0):
    """试验结束后回写整体峰值与合格率到 tests 表。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT MAX(force_value) AS max_force,
                          AVG(CASE WHEN force_value >= %s THEN 1.0 ELSE 0.0 END)*100 AS pass_rate
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
