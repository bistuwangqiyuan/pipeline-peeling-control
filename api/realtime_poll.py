from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.response import json_response, error_response, options_response, get_query_params
from api._lib.simulator import generate_simulation_batch, compute_test_summary


POSITION_STEP_MM = 5.0


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        try:
            params = get_query_params(self)
            test_id = params.get('test_id')
            if not test_id:
                error_response(self, '缺少试验ID')
                return

            test = query("SELECT * FROM tests WHERE id = %s", (test_id,), fetchone=True)
            if not test:
                error_response(self, '试验不存在', 404)
                return

            total_mm = float(test['total_positions'] or 600)

            # 推进仿真（仅在运行中）
            if test['is_running']:
                current = float(test['current_position'] or 0)
                profiles = test['profiles']
                if isinstance(profiles, str):
                    profiles = json.loads(profiles)

                if current >= total_mm:
                    execute("""UPDATE tests SET is_running=FALSE, status='completed',
                               end_time=NOW() WHERE id=%s""", (test_id,))
                    compute_test_summary(int(test_id))
                    test = query("SELECT * FROM tests WHERE id = %s", (test_id,), fetchone=True)
                elif profiles:
                    speed = float(test['peel_speed'] or 10)
                    generate_simulation_batch(int(test_id), profiles, current, total_mm, speed)
                    new_pos = current + POSITION_STEP_MM
                    execute("UPDATE tests SET current_position=%s WHERE id=%s",
                            (new_pos, test_id))

            # 各条带最新值
            latest = query(
                """SELECT strip_number, position_mm, force_value, speed, timestamp
                   FROM data_points
                   WHERE test_id = %s AND id IN (
                       SELECT MAX(id) FROM data_points WHERE test_id = %s GROUP BY strip_number
                   )
                   ORDER BY strip_number""",
                (test_id, test_id), fetchall=True
            )

            recent_history = query(
                """SELECT strip_number, position_mm, force_value, timestamp
                   FROM data_points WHERE test_id = %s
                   ORDER BY id DESC LIMIT 600""",
                (test_id,), fetchall=True
            )

            cur_pos = float(test['current_position'] or 0)
            progress = min(100.0, cur_pos / total_mm * 100.0) if total_mm else 0.0
            forces = [float(d['force_value']) for d in latest] if latest else []
            total_force = sum(forces)
            avg_force = total_force / len(forces) if forces else 0
            max_force = max(forces, default=0)

            json_response(self, {
                'test': test,
                'is_running': bool(test['is_running']),
                'current_position': cur_pos,
                'total_mm': total_mm,
                'progress': round(progress, 2),
                'latest_data': latest,
                'recent_history': recent_history,
                'stats': {
                    'total_force': round(total_force, 2),
                    'avg_force': round(avg_force, 2),
                    'max_force': round(max_force, 2),
                    'active_strips': len([f for f in forces if f > 0]),
                }
            })
        except Exception as e:
            error_response(self, str(e), 500)
