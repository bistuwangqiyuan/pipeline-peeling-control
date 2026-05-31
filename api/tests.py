from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute_returning
from api._lib.auth import get_user_from_request, can_modify
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        try:
            params = get_query_params(self)
            tid = params.get('id')

            if tid:
                test = query(
                    """SELECT t.*, p.name as project_name
                       FROM tests t LEFT JOIN projects p ON t.project_id = p.id
                       WHERE t.id = %s""",
                    (tid,), fetchone=True
                )
                if not test:
                    error_response(self, '试验不存在', 404)
                    return
                json_response(self, {'test': test})
                return

            project_id = params.get('project_id')
            status_filter = params.get('status')
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '20'))
            offset = (page - 1) * per_page

            where_clauses = []
            where_params = []
            if project_id:
                where_clauses.append("t.project_id = %s")
                where_params.append(project_id)
            if status_filter:
                where_clauses.append("t.status = %s")
                where_params.append(status_filter)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            count_result = query(
                f"SELECT COUNT(*) as total FROM tests t WHERE {where_sql}",
                where_params, fetchone=True
            )
            tests = query(
                f"""SELECT t.*, p.name as project_name, u.username as creator_name
                    FROM tests t
                    LEFT JOIN projects p ON t.project_id = p.id
                    LEFT JOIN users u ON t.created_by = u.id
                    WHERE {where_sql}
                    ORDER BY t.created_at DESC
                    LIMIT %s OFFSET %s""",
                where_params + [per_page, offset], fetchall=True
            )

            json_response(self, {
                'tests': tests, 'total': count_result['total'],
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
            project_id = body.get('project_id')
            test_number = body.get('test_number', '').strip()

            if not project_id or not test_number:
                error_response(self, '项目ID和试验编号不能为空')
                return

            test = execute_returning(
                """INSERT INTO tests
                   (project_id, test_number, sample_name, operator, peel_speed,
                    ambient_temp, pipe_temp, humidity, notes, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (project_id, test_number, body.get('sample_name'),
                 body.get('operator', ''), body.get('peel_speed', 10),
                 body.get('ambient_temp'), body.get('pipe_temp'),
                 body.get('humidity'), body.get('notes', ''), payload['user_id'])
            )

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details) VALUES (%s, %s, %s, %s, %s)",
                (payload['user_id'], 'create', 'test', test['id'], json.dumps({'test_number': test_number}))
            )

            json_response(self, {'test': test}, 201)
        except Exception as e:
            error_response(self, str(e), 500)
