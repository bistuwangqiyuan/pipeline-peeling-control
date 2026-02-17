from http.server import BaseHTTPRequestHandler
import csv
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.auth import get_user_from_request
from api._lib.response import error_response, options_response, get_query_params


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
            fmt = params.get('format', 'csv')

            if not test_id:
                error_response(self, '缺少试验ID')
                return

            test = query(
                "SELECT * FROM peeling_tests WHERE id = %s",
                (test_id,),
                fetchone=True
            )
            if not test:
                error_response(self, '试验不存在', 404)
                return

            data = query(
                """SELECT strip_number, position_angle, force_value, speed, displacement, timestamp
                   FROM strip_data
                   WHERE test_id = %s
                   ORDER BY timestamp ASC, strip_number ASC""",
                (test_id,),
                fetchall=True
            )

            if fmt == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['条带编号', '位置角度(°)', '剥离力(N)', '速度(mm/s)', '位移(mm)', '时间戳'])
                for row in data:
                    writer.writerow([
                        row['strip_number'],
                        row['position_angle'],
                        row['force_value'],
                        row['speed'],
                        row['displacement'],
                        row['timestamp'].isoformat() if row['timestamp'] else ''
                    ])

                csv_content = output.getvalue()
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition',
                                 f'attachment; filename=peeling_test_{test_id}.csv')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write('\ufeff'.encode('utf-8'))
                self.wfile.write(csv_content.encode('utf-8'))
            else:
                import json
                from api._lib.response import CustomEncoder
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Disposition',
                                 f'attachment; filename=peeling_test_{test_id}.json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'test': test,
                    'data': data
                }, cls=CustomEncoder, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            error_response(self, str(e), 500)
