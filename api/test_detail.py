from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.auth import get_user_from_request, can_modify
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params


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
                """SELECT * FROM test_results
                   WHERE test_id = %s ORDER BY strip_number""",
                (tid,),
                fetchall=True
            )

            sim_state = query(
                "SELECT current_angle, is_running FROM simulation_state WHERE test_id = %s",
                (tid,),
                fetchone=True
            )

            json_response(self, {
                'test': test,
                'results': results,
                'simulation': sim_state
            })
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
                        'pipe_temp', 'humidity', 'notes', 'start_time', 'end_time']:
                if key in body:
                    fields.append(f"{key} = %s")
                    values.append(body[key])

            if fields:
                values.append(tid)
                execute(
                    f"UPDATE peeling_tests SET {', '.join(fields)} WHERE id = %s",
                    values
                )

            test = query("SELECT * FROM peeling_tests WHERE id = %s", (tid,), fetchone=True)
            json_response(self, {'test': test})
        except Exception as e:
            error_response(self, str(e), 500)
