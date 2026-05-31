from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.auth import get_user_from_request, can_modify
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params
from api._lib.simulator import generate_strip_profiles, compute_test_summary


DEFAULT_TOTAL_MM = 600.0


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        """试验详情：含逐条带统计（由 data_points 聚合）与仿真状态。"""
        try:
            params = get_query_params(self)
            tid = params.get('id') or params.get('test_id')
            if not tid:
                error_response(self, '缺少试验ID')
                return

            test = query(
                """SELECT t.*, p.name as project_name
                   FROM tests t LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.id = %s""",
                (tid,), fetchone=True
            )
            if not test:
                error_response(self, '试验不存在', 404)
                return

            results = query(
                """SELECT strip_number,
                          ROUND(AVG(force_value)::numeric, 2) AS avg_force,
                          ROUND(MAX(force_value)::numeric, 2) AS max_force,
                          ROUND(MIN(force_value)::numeric, 2) AS min_force,
                          ROUND(STDDEV(force_value)::numeric, 2) AS std_force,
                          ROUND(MAX(position_mm)::numeric, 2) AS total_displacement,
                          (AVG(force_value) >= 70) AS pass_fail
                   FROM data_points WHERE test_id = %s
                   GROUP BY strip_number ORDER BY strip_number""",
                (tid,), fetchall=True
            )

            json_response(self, {'test': test, 'results': results,
                                 'simulation': {'is_running': test['is_running'],
                                                'current_position': test['current_position']}})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_PUT(self):
        try:
            payload = get_user_from_request(self.headers)
            if not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            params = get_query_params(self)
            tid = params.get('id') or params.get('test_id')
            if not tid:
                error_response(self, '缺少试验ID')
                return

            body = get_body(self)
            fields = []
            values = []
            for key in ['test_number', 'sample_name', 'operator', 'status', 'peel_speed',
                        'ambient_temp', 'pipe_temp', 'humidity', 'notes']:
                if key in body:
                    fields.append(f"{key} = %s")
                    values.append(body[key])

            if fields:
                values.append(tid)
                execute(f"UPDATE tests SET {', '.join(fields)} WHERE id = %s", values)

            test = query("SELECT * FROM tests WHERE id = %s", (tid,), fetchone=True)
            json_response(self, {'test': test})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_POST(self):
        try:
            payload = get_user_from_request(self.headers)
            if not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            params = get_query_params(self)
            body = get_body(self)
            action = params.get('action') or body.get('action', 'start')
            test_id = body.get('test_id') or params.get('test_id') or params.get('id')

            if not test_id:
                error_response(self, '缺少试验ID')
                return

            test = query("SELECT * FROM tests WHERE id = %s", (test_id,), fetchone=True)
            if not test:
                error_response(self, '试验不存在', 404)
                return

            if action == 'start':
                if test['is_running']:
                    error_response(self, '试验已在运行中')
                    return

                n_strips = int(body.get('n_strips', 30))
                total_mm = float(body.get('total_mm', DEFAULT_TOTAL_MM))
                speed = float(body.get('peel_speed', test.get('peel_speed') or 10))
                profiles = generate_strip_profiles(n_strips, total_mm)

                execute("DELETE FROM data_points WHERE test_id = %s", (test_id,))
                execute(
                    """UPDATE tests SET status='running', is_running=TRUE,
                       start_time=NOW(), end_time=NULL, current_position=0,
                       n_strips=%s, total_positions=%s, peel_speed=%s, profiles=%s,
                       max_force=NULL, pass_rate=NULL WHERE id=%s""",
                    (n_strips, int(total_mm), speed, json.dumps(profiles), test_id)
                )
                execute("UPDATE projects SET status='in_progress', updated_at=NOW() WHERE id=%s",
                        (test['project_id'],))
                query(
                    "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s,%s,%s,%s)",
                    (payload['user_id'], 'start_test', 'test', int(test_id))
                )
                json_response(self, {'message': '试验已启动', 'status': 'running',
                                     'n_strips': n_strips, 'total_mm': total_mm})

            elif action == 'stop':
                execute(
                    """UPDATE tests SET status='completed', is_running=FALSE, end_time=NOW()
                       WHERE id=%s""", (test_id,))
                summary = compute_test_summary(int(test_id))
                query(
                    "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s,%s,%s,%s)",
                    (payload['user_id'], 'stop_test', 'test', int(test_id))
                )
                json_response(self, {'message': '试验已停止', 'status': 'completed',
                                     'summary': summary})

            elif action == 'abort':
                execute(
                    """UPDATE tests SET status='aborted', is_running=FALSE, end_time=NOW()
                       WHERE id=%s""", (test_id,))
                query(
                    "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s,%s,%s,%s)",
                    (payload['user_id'], 'abort_test', 'test', int(test_id))
                )
                json_response(self, {'message': '试验已中止（急停）', 'status': 'aborted'})
            else:
                error_response(self, f'未知操作: {action}')
        except Exception as e:
            error_response(self, str(e), 500)
