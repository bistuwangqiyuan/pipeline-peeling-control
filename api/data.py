from http.server import BaseHTTPRequestHandler
import json
import csv
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.auth import get_user_from_request
from api._lib.response import json_response, error_response, options_response, get_query_params, CustomEncoder


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        params = get_query_params(self)
        action = params.get('action', 'history')
        if action == 'history':
            self._history(params)
        elif action == 'analysis':
            self._analysis(params)
        elif action == 'export':
            self._export(params)
        else:
            error_response(self, 'Unknown action')

    def _history(self, params):
        try:
            payload = get_user_from_request(self.headers)
            if not payload:
                error_response(self, '未授权访问', 401)
                return

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
                where_params, fetchone=True
            )

            data = query(
                f"""SELECT strip_number, position_angle, force_value, speed, displacement, timestamp
                    FROM strip_data WHERE {where_sql}
                    ORDER BY timestamp ASC, strip_number ASC
                    LIMIT %s OFFSET %s""",
                where_params + [per_page, offset], fetchall=True
            )

            json_response(self, {'data': data, 'total': count_result['total'], 'page': page})
        except Exception as e:
            error_response(self, str(e), 500)

    def _analysis(self, params):
        try:
            payload = get_user_from_request(self.headers)
            if not payload:
                error_response(self, '未授权访问', 401)
                return

            test_id = params.get('test_id')
            if not test_id:
                error_response(self, '缺少试验ID')
                return

            test = query(
                """SELECT t.*, p.name as project_name FROM peeling_tests t
                   LEFT JOIN projects p ON t.project_id = p.id WHERE t.id = %s""",
                (test_id,), fetchone=True
            )
            if not test:
                error_response(self, '试验不存在', 404)
                return

            strip_stats = query(
                """SELECT strip_number,
                    ROUND(AVG(force_value)::numeric, 2) as avg_force,
                    ROUND(MAX(force_value)::numeric, 2) as max_force,
                    ROUND(MIN(force_value)::numeric, 2) as min_force,
                    ROUND(STDDEV(force_value)::numeric, 2) as std_force,
                    ROUND(MAX(displacement)::numeric, 2) as total_displacement,
                    COUNT(*) as data_points
                FROM strip_data WHERE test_id = %s
                GROUP BY strip_number ORDER BY strip_number""",
                (test_id,), fetchall=True
            )

            force_distribution = query(
                """SELECT width_bucket(force_value, 0, 2000, 20) as bucket,
                    COUNT(*) as count,
                    ROUND(MIN(force_value)::numeric, 0) as range_min,
                    ROUND(MAX(force_value)::numeric, 0) as range_max
                FROM strip_data WHERE test_id = %s AND force_value > 0
                GROUP BY bucket ORDER BY bucket""",
                (test_id,), fetchall=True
            )

            force_vs_angle = query(
                """SELECT strip_number,
                    ROUND(position_angle::numeric, 1) as angle,
                    ROUND(AVG(force_value)::numeric, 2) as avg_force
                FROM strip_data WHERE test_id = %s
                GROUP BY strip_number, ROUND(position_angle::numeric, 1)
                ORDER BY strip_number, angle""",
                (test_id,), fetchall=True
            )

            overall_stats = query(
                """SELECT ROUND(AVG(force_value)::numeric, 2) as overall_avg,
                    ROUND(MAX(force_value)::numeric, 2) as overall_max,
                    ROUND(MIN(CASE WHEN force_value > 0 THEN force_value END)::numeric, 2) as overall_min,
                    ROUND(STDDEV(force_value)::numeric, 2) as overall_std,
                    COUNT(*) as total_points,
                    COUNT(DISTINCT strip_number) as strips_tested
                FROM strip_data WHERE test_id = %s""",
                (test_id,), fetchone=True
            )

            json_response(self, {
                'test': test, 'strip_stats': strip_stats,
                'force_distribution': force_distribution,
                'force_vs_angle': force_vs_angle,
                'overall_stats': overall_stats
            })
        except Exception as e:
            error_response(self, str(e), 500)

    def _export(self, params):
        try:
            payload = get_user_from_request(self.headers)
            if not payload:
                error_response(self, '未授权访问', 401)
                return

            test_id = params.get('test_id')
            if not test_id:
                error_response(self, '缺少试验ID')
                return

            data = query(
                """SELECT strip_number, position_angle, force_value, speed, displacement, timestamp
                   FROM strip_data WHERE test_id = %s
                   ORDER BY timestamp ASC, strip_number ASC""",
                (test_id,), fetchall=True
            )

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['条带编号', '位置角度(°)', '剥离力(N)', '速度(mm/s)', '位移(mm)', '时间戳'])
            for row in data:
                writer.writerow([
                    row['strip_number'], row['position_angle'], row['force_value'],
                    row['speed'], row['displacement'],
                    row['timestamp'].isoformat() if row['timestamp'] else ''
                ])

            csv_content = output.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename=peeling_test_{test_id}.csv')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write('\ufeff'.encode('utf-8'))
            self.wfile.write(csv_content.encode('utf-8'))
        except Exception as e:
            error_response(self, str(e), 500)
