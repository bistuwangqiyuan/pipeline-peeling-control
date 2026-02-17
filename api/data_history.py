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
            test_id = params.get('test_id')
            strip_number = params.get('strip_number')
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '500'))
            offset = (page - 1) * per_page

            if not test_id:
                error_response(self, '缺少试验ID')
                return

            where_clauses = ["test_id = %s"]
            where_params = [test_id]

            if strip_number:
                where_clauses.append("strip_number = %s")
                where_params.append(strip_number)

            where_sql = " AND ".join(where_clauses)

            count_result = query(
                f"SELECT COUNT(*) as total FROM strip_data WHERE {where_sql}",
                where_params,
                fetchone=True
            )

            data = query(
                f"""SELECT strip_number, position_angle, force_value, speed, displacement, timestamp
                    FROM strip_data
                    WHERE {where_sql}
                    ORDER BY timestamp ASC, strip_number ASC
                    LIMIT %s OFFSET %s""",
                where_params + [per_page, offset],
                fetchall=True
            )

            json_response(self, {
                'data': data,
                'total': count_result['total'],
                'page': page,
                'per_page': per_page
            })
        except Exception as e:
            error_response(self, str(e), 500)
