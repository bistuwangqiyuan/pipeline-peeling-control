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
            pid = params.get('id')
            if not pid:
                error_response(self, '缺少项目ID')
                return

            project = query(
                """SELECT p.*, u.username as creator_name
                   FROM projects p
                   LEFT JOIN users u ON p.created_by = u.id
                   WHERE p.id = %s""",
                (pid,),
                fetchone=True
            )
            if not project:
                error_response(self, '项目不存在', 404)
                return

            tests = query(
                """SELECT * FROM peeling_tests
                   WHERE project_id = %s ORDER BY created_at DESC""",
                (pid,),
                fetchall=True
            )

            json_response(self, {'project': project, 'tests': tests})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_PUT(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload or not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            params = get_query_params(self)
            pid = params.get('id')
            if not pid:
                error_response(self, '缺少项目ID')
                return

            body = get_body(self)
            fields = []
            values = []
            for key in ['name', 'description', 'pipe_diameter', 'layer_width',
                        'layer_thickness', 'strip_count', 'strip_width',
                        'estimated_force', 'location', 'status']:
                if key in body:
                    fields.append(f"{key} = %s")
                    values.append(body[key])

            if not fields:
                error_response(self, '没有要更新的字段')
                return

            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(pid)

            execute(
                f"UPDATE projects SET {', '.join(fields)} WHERE id = %s",
                values
            )

            project = query("SELECT * FROM projects WHERE id = %s", (pid,), fetchone=True)

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details) VALUES (%s, %s, %s, %s, %s)",
                (payload['user_id'], 'update', 'project', int(pid), json.dumps(body))
            )

            json_response(self, {'project': project})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_DELETE(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload or not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            params = get_query_params(self)
            pid = params.get('id')
            if not pid:
                error_response(self, '缺少项目ID')
                return

            execute("DELETE FROM projects WHERE id = %s", (pid,))

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s, %s, %s, %s)",
                (payload['user_id'], 'delete', 'project', int(pid))
            )

            json_response(self, {'message': '项目已删除'})
        except Exception as e:
            error_response(self, str(e), 500)
