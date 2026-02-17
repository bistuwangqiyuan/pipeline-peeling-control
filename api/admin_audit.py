from http.server import BaseHTTPRequestHandler
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.auth import get_user_from_request
from api._lib.response import json_response, error_response, options_response, get_query_params


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
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '50'))
            offset = (page - 1) * per_page
            action_filter = params.get('action')
            resource_type = params.get('resource_type')

            where_clauses = []
            where_params = []

            if action_filter:
                where_clauses.append("a.action = %s")
                where_params.append(action_filter)
            if resource_type:
                where_clauses.append("a.resource_type = %s")
                where_params.append(resource_type)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            count_result = query(
                f"SELECT COUNT(*) as total FROM audit_log a WHERE {where_sql}",
                where_params,
                fetchone=True
            )

            logs = query(
                f"""SELECT a.*, u.username
                    FROM audit_log a
                    LEFT JOIN users u ON a.user_id = u.id
                    WHERE {where_sql}
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s""",
                where_params + [per_page, offset],
                fetchall=True
            )

            json_response(self, {
                'logs': logs,
                'total': count_result['total'],
                'page': page,
                'per_page': per_page
            })
        except Exception as e:
            error_response(self, str(e), 500)
