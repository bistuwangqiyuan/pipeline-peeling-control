from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute_returning, execute
from api._lib.auth import get_user_from_request, can_modify
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    # 读操作：游客可访问（论文 3.1 渐进式开放）
    def do_GET(self):
        try:
            params = get_query_params(self)
            pid = params.get('id')

            if pid:
                project = query(
                    """SELECT p.*, u.username as creator_name
                       FROM projects p LEFT JOIN users u ON p.created_by = u.id
                       WHERE p.id = %s""",
                    (pid,), fetchone=True
                )
                if not project:
                    error_response(self, '项目不存在', 404)
                    return
                tests = query(
                    "SELECT * FROM tests WHERE project_id = %s ORDER BY created_at DESC",
                    (pid,), fetchall=True
                )
                stats = query(
                    """SELECT COUNT(*) AS test_count,
                              ROUND(AVG(max_force)::numeric, 2) AS avg_max_force,
                              ROUND(MAX(max_force)::numeric, 2) AS peak_force,
                              ROUND(AVG(pass_rate)::numeric, 2) AS avg_pass_rate
                       FROM tests WHERE project_id = %s""",
                    (pid,), fetchone=True
                )
                json_response(self, {'project': project, 'tests': tests, 'stats': stats})
                return

            status_filter = params.get('status')
            search = params.get('search', '')
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '20'))
            offset = (page - 1) * per_page

            where_clauses = []
            where_params = []
            if status_filter:
                where_clauses.append("p.status = %s")
                where_params.append(status_filter)
            if search:
                where_clauses.append("(p.name ILIKE %s OR p.location ILIKE %s)")
                where_params.extend([f'%{search}%', f'%{search}%'])

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            count_result = query(
                f"SELECT COUNT(*) as total FROM projects p WHERE {where_sql}",
                where_params, fetchone=True
            )
            projects = query(
                f"""SELECT p.*, u.username as creator_name,
                        (SELECT COUNT(*) FROM tests t WHERE t.project_id = p.id) AS test_count
                    FROM projects p LEFT JOIN users u ON p.created_by = u.id
                    WHERE {where_sql}
                    ORDER BY p.created_at DESC LIMIT %s OFFSET %s""",
                where_params + [per_page, offset], fetchall=True
            )

            json_response(self, {
                'projects': projects, 'total': count_result['total'],
                'page': page, 'per_page': per_page
            })
        except Exception as e:
            error_response(self, str(e), 500)

    def do_POST(self):
        try:
            payload = get_user_from_request(self.headers)
            if not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return

            body = get_body(self)
            name = body.get('name', '').strip()
            if not name:
                error_response(self, '项目名称不能为空')
                return

            project = execute_returning(
                """INSERT INTO projects (name, description, pipe_diameter, layer_width,
                   layer_thickness, strip_width, location, status, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (name, body.get('description', ''), body.get('pipe_diameter', 1016),
                 body.get('layer_width', 600), body.get('layer_thickness', 1.0),
                 body.get('strip_width', 20), body.get('location', ''),
                 body.get('status', 'created'), payload['user_id'])
            )

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details) VALUES (%s, %s, %s, %s, %s)",
                (payload['user_id'], 'create', 'project', project['id'], json.dumps({'name': name}))
            )
            json_response(self, {'project': project}, 201)
        except Exception as e:
            error_response(self, str(e), 500)

    def do_PUT(self):
        try:
            payload = get_user_from_request(self.headers)
            if not can_modify(payload):
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
                        'layer_thickness', 'strip_width', 'location', 'status']:
                if key in body:
                    fields.append(f"{key} = %s")
                    values.append(body[key])

            if not fields:
                error_response(self, '没有要更新的字段')
                return

            fields.append("updated_at = NOW()")
            values.append(pid)
            execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = %s", values)

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s, %s, %s, %s)",
                (payload['user_id'], 'update', 'project', int(pid))
            )

            project = query("SELECT * FROM projects WHERE id = %s", (pid,), fetchone=True)
            json_response(self, {'project': project})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_DELETE(self):
        try:
            payload = get_user_from_request(self.headers)
            if not can_modify(payload):
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
