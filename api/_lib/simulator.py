import math
import random
import datetime
from .db import get_connection
import psycopg2.extras


STRIP_COUNT = 30
PIPE_CIRCUMFERENCE_DEG = 360.0
BASE_FORCE_MIN = 800.0
BASE_FORCE_MAX = 1200.0
NOISE_SIGMA_RATIO = 0.05
ADHESION_FACTOR_MIN = 0.8
ADHESION_FACTOR_MAX = 1.2


def generate_strip_profiles(strip_count=STRIP_COUNT):
    profiles = []
    for i in range(strip_count):
        base_force = random.uniform(BASE_FORCE_MIN, BASE_FORCE_MAX)
        adhesion_factor = random.uniform(ADHESION_FACTOR_MIN, ADHESION_FACTOR_MAX)
        peak_angle = random.uniform(30, 90)
        profiles.append({
            'strip_number': i + 1,
            'base_force': base_force,
            'adhesion_factor': adhesion_factor,
            'peak_angle': peak_angle
        })
    return profiles


def force_curve(angle, base_force, adhesion_factor, peak_angle):
    effective_force = base_force * adhesion_factor
    if angle < 5:
        t = angle / 5.0
        force = effective_force * 0.3 * t
    elif angle < peak_angle:
        t = (angle - 5) / (peak_angle - 5)
        force = effective_force * (0.3 + 0.7 * math.sin(t * math.pi / 2))
    elif angle < peak_angle + 20:
        t = (angle - peak_angle) / 20.0
        force = effective_force * (1.0 - 0.15 * t)
    elif angle < 300:
        base_steady = effective_force * 0.85
        wave = 0.05 * effective_force * math.sin(angle * 0.1)
        force = base_steady + wave
    elif angle < 340:
        t = (angle - 300) / 40.0
        force = effective_force * 0.85 * (1.0 - 0.3 * t)
    else:
        t = (angle - 340) / 20.0
        force = effective_force * 0.595 * max(0, 1.0 - t)

    noise = random.gauss(0, force * NOISE_SIGMA_RATIO) if force > 0 else 0
    return max(0, force + noise)


def generate_simulation_batch(test_id, profiles, current_angle, angle_step=2.0):
    now = datetime.datetime.utcnow()
    rows = []
    for profile in profiles:
        sn = profile['strip_number']
        angle = current_angle
        f = force_curve(
            angle,
            profile['base_force'],
            profile['adhesion_factor'],
            profile['peak_angle']
        )
        speed = random.uniform(3.0, 8.0)
        displacement = angle / 360.0 * math.pi * 1000.0

        rows.append((
            test_id, sn, now, round(angle, 4),
            round(f, 4), round(speed, 4), round(displacement, 4)
        ))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO strip_data
                   (test_id, strip_number, timestamp, position_angle, force_value, speed, displacement)
                   VALUES %s""",
                rows
            )
            conn.commit()
    finally:
        conn.close()

    new_angle = current_angle + angle_step
    return new_angle, rows


def compute_test_results(test_id):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO test_results (test_id, strip_number, avg_force, max_force, min_force, std_force, total_displacement, pass_fail)
                SELECT
                    test_id,
                    strip_number,
                    ROUND(AVG(force_value)::numeric, 4),
                    ROUND(MAX(force_value)::numeric, 4),
                    ROUND(MIN(force_value)::numeric, 4),
                    ROUND(STDDEV(force_value)::numeric, 4),
                    ROUND(MAX(displacement)::numeric, 4),
                    CASE WHEN AVG(force_value) > 0 THEN true ELSE false END
                FROM strip_data
                WHERE test_id = %s
                GROUP BY test_id, strip_number
                ON CONFLICT DO NOTHING
            """, (test_id,))
            conn.commit()
    finally:
        conn.close()
