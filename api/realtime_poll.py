from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.response import json_response, error_response, options_response, get_query_params
from api._lib.simulator import reveal, playback_step, compute_test_summary


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

            # 回放推进（仅在运行中）：按位置游标揭示真实数据点，绝不生成 mock
            template = test['profiles']
            if isinstance(template, str):
                template = json.loads(template) if template else None

            total_mm = float(test['total_positions'] or 0) or (
                float(template['max_pos']) if template and template.get('max_pos') else 600.0)

            if test['is_running']:
                current = float(test['current_position'] or 0)

                if not template or 'replay' not in template:
                    # 缺少真实回放模板，直接结束以避免空跑
                    execute("""UPDATE tests SET is_running=FALSE, status='completed',
                               end_time=NOW() WHERE id=%s""", (test_id,))
                    test = query("SELECT * FROM tests WHERE id = %s", (test_id,), fetchone=True)
                elif current >= total_mm:
                    execute("""UPDATE tests SET is_running=FALSE, status='completed',
                               end_time=NOW() WHERE id=%s""", (test_id,))
                    compute_test_summary(int(test_id))
                    test = query("SELECT * FROM tests WHERE id = %s", (test_id,), fetchone=True)
                else:
                    new_pos = min(total_mm, current + playback_step(total_mm))
                    reveal(int(test_id), template, current, new_pos)
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

            # 回放模板体积较大，避免随每次轮询回传
            if isinstance(test, dict):
                test.pop('profiles', None)

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
