from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.auth import get_user_from_request, can_modify
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params
from api._lib.simulator import generate_strip_profiles, compute_test_results


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload:
                error_response(self, '未授权访问', 401)
                return

            params = get_query_params(self)
            tid = params.get('id')
            if not tid:
                error_response(self, '缺少试验ID')
                return

            test = query(
                """SELECT t.*, p.name as project_name
                   FROM peeling_tests t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.id = %s""",
                (tid,),
                fetchone=True
            )
            if not test:
                error_response(self, '试验不存在', 404)
                return

            results = query(
                "SELECT * FROM test_results WHERE test_id = %s ORDER BY strip_number",
                (tid,),
                fetchall=True
            )

            sim_state = query(
                "SELECT current_angle, is_running FROM simulation_state WHERE test_id = %s",
                (tid,),
                fetchone=True
            )

            json_response(self, {'test': test, 'results': results, 'simulation': sim_state})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_PUT(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload or not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            params = get_query_params(self)
            tid = params.get('id')
            if not tid:
                error_response(self, '缺少试验ID')
                return

            body = get_body(self)
            fields = []
            values = []
            for key in ['test_number', 'operator', 'status', 'ambient_temp',
                        'pipe_temp', 'humidity', 'notes']:
                if key in body:
                    fields.append(f"{key} = %s")
                    values.append(body[key])

            if fields:
                values.append(tid)
                execute(f"UPDATE peeling_tests SET {', '.join(fields)} WHERE id = %s", values)

            test = query("SELECT * FROM peeling_tests WHERE id = %s", (tid,), fetchone=True)
            json_response(self, {'test': test})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_POST(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload or not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            body = get_body(self)
            test_id = body.get('test_id')
            action = body.get('action', 'start')

            if not test_id:
                error_response(self, '缺少试验ID')
                return

            test = query("SELECT * FROM peeling_tests WHERE id = %s", (test_id,), fetchone=True)
            if not test:
                error_response(self, '试验不存在', 404)
                return

            if action == 'start':
                if test['status'] == 'running':
                    error_response(self, '试验已在运行中')
                    return

                profiles = generate_strip_profiles()
                profiles_json = json.dumps(profiles)

                execute(
                    "UPDATE peeling_tests SET status = 'running', start_time = CURRENT_TIMESTAMP, current_angle = 0 WHERE id = %s",
                    (test_id,)
                )
                execute("DELETE FROM strip_data WHERE test_id = %s", (test_id,))
                execute("DELETE FROM test_results WHERE test_id = %s", (test_id,))
                execute(
                    """INSERT INTO simulation_state (test_id, profiles, current_angle, is_running)
                       VALUES (%s, %s, 0, TRUE)
                       ON CONFLICT (test_id) DO UPDATE
                       SET profiles = %s, current_angle = 0, is_running = TRUE, updated_at = CURRENT_TIMESTAMP""",
                    (test_id, profiles_json, profiles_json)
                )
                execute(
                    "UPDATE projects SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (test['project_id'],)
                )

                query(
                    "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s, %s, %s, %s)",
                    (payload['user_id'], 'start_test', 'test', test_id)
                )
                json_response(self, {'message': '试验已启动', 'status': 'running'})

            elif action == 'stop':
                execute(
                    "UPDATE peeling_tests SET status = 'completed', end_time = CURRENT_TIMESTAMP WHERE id = %s",
                    (test_id,)
                )
                execute("UPDATE simulation_state SET is_running = FALSE WHERE test_id = %s", (test_id,))
                compute_test_results(test_id)

                query(
                    "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s, %s, %s, %s)",
                    (payload['user_id'], 'stop_test', 'test', test_id)
                )
                json_response(self, {'message': '试验已停止', 'status': 'completed'})

            elif action == 'abort':
                execute(
                    "UPDATE peeling_tests SET status = 'aborted', end_time = CURRENT_TIMESTAMP WHERE id = %s",
                    (test_id,)
                )
                execute("UPDATE simulation_state SET is_running = FALSE WHERE test_id = %s", (test_id,))

                query(
                    "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s, %s, %s, %s)",
                    (payload['user_id'], 'abort_test', 'test', test_id)
                )
                json_response(self, {'message': '试验已中止', 'status': 'aborted'})
            else:
                error_response(self, f'未知操作: {action}')
        except Exception as e:
            error_response(self, str(e), 500)
