from http.server import BaseHTTPRequestHandler
import csv
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.response import json_response, error_response, options_response, get_query_params

PASS_THRESHOLD = 70.0
HIST_MAX = 120.0
HIST_BINS = 24


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
        elif action == 'dataset':
            self._dataset(params)
        elif action == 'export':
            self._export(params)
        else:
            error_response(self, 'Unknown action')

    # ---- 单试验历史数据点（游客可读） ----
    def _history(self, params):
        try:
            test_id = params.get('test_id')
            if not test_id:
                error_response(self, '缺少试验ID')
                return
            strip_number = params.get('strip_number')
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '1000'))
            offset = (page - 1) * per_page

            where = ["test_id = %s"]
            wp = [test_id]
            if strip_number:
                where.append("strip_number = %s")
                wp.append(strip_number)
            where_sql = " AND ".join(where)

            count_result = query(
                f"SELECT COUNT(*) as total FROM data_points WHERE {where_sql}", wp, fetchone=True)
            data = query(
                f"""SELECT strip_number, position_mm, force_value, speed, timestamp
                    FROM data_points WHERE {where_sql}
                    ORDER BY strip_number ASC, position_mm ASC
                    LIMIT %s OFFSET %s""",
                wp + [per_page, offset], fetchall=True)
            json_response(self, {'data': data, 'total': count_result['total'], 'page': page})
        except Exception as e:
            error_response(self, str(e), 500)

    # ---- 单试验分析（柱图/直方图/累积分布/钻取曲线） ----
    def _analysis(self, params):
        try:
            test_id = params.get('test_id')
            if not test_id:
                error_response(self, '缺少试验ID')
                return

            test = query(
                """SELECT t.*, p.name as project_name FROM tests t
                   LEFT JOIN projects p ON t.project_id = p.id WHERE t.id = %s""",
                (test_id,), fetchone=True)
            if not test:
                error_response(self, '试验不存在', 404)
                return

            strip_stats = query(
                """SELECT strip_number,
                    ROUND(AVG(force_value)::numeric,2) as avg_force,
                    ROUND(MAX(force_value)::numeric,2) as max_force,
                    ROUND(MIN(force_value)::numeric,2) as min_force,
                    ROUND(STDDEV(force_value)::numeric,2) as std_force,
                    (AVG(force_value) >= %s) as pass_fail,
                    COUNT(*) as data_points
                FROM data_points WHERE test_id = %s
                GROUP BY strip_number ORDER BY strip_number""",
                (PASS_THRESHOLD, test_id), fetchall=True)

            hist = query(
                """SELECT width_bucket(force_value, 0, %s, %s) as bucket, COUNT(*) as count
                   FROM data_points WHERE test_id = %s
                   GROUP BY bucket ORDER BY bucket""",
                (HIST_MAX, HIST_BINS, test_id), fetchone=False, fetchall=True)

            # 构造完整直方图 + 累积分布
            bin_w = HIST_MAX / HIST_BINS
            counts = [0] * (HIST_BINS + 2)
            for h in hist:
                b = int(h['bucket']) if h['bucket'] is not None else 0
                if 0 <= b < len(counts):
                    counts[b] += int(h['count'])
            histogram = []
            cumulative = []
            total = sum(counts) or 1
            running = 0
            for b in range(1, HIST_BINS + 1):
                lo = round((b - 1) * bin_w, 1)
                hi = round(b * bin_w, 1)
                c = counts[b]
                running += c
                histogram.append({'range_min': lo, 'range_max': hi, 'count': c})
                cumulative.append({'force': hi, 'cum_pct': round(100.0 * running / total, 2)})

            overall = query(
                """SELECT ROUND(AVG(force_value)::numeric,2) as overall_avg,
                    ROUND(MAX(force_value)::numeric,2) as overall_max,
                    ROUND(MIN(force_value)::numeric,2) as overall_min,
                    ROUND(STDDEV(force_value)::numeric,2) as overall_std,
                    COUNT(*) as total_points,
                    COUNT(DISTINCT strip_number) as strips_tested,
                    ROUND(AVG(CASE WHEN force_value>=%s THEN 1.0 ELSE 0.0 END)*100,2) as pass_rate
                FROM data_points WHERE test_id = %s""",
                (PASS_THRESHOLD, test_id), fetchone=True)

            pass_strips = len([s for s in strip_stats if s['pass_fail']])
            fail_strips = len(strip_stats) - pass_strips

            json_response(self, {
                'test': test, 'strip_stats': strip_stats,
                'histogram': histogram, 'cumulative': cumulative,
                'overall_stats': overall,
                'pass_pie': {'pass': pass_strips, 'fail': fail_strips},
                'threshold': PASS_THRESHOLD,
            })
        except Exception as e:
            error_response(self, str(e), 500)

    # ---- 跨试验数据分析（趋势/对比/合格分布/直方图） ----
    def _dataset(self, params):
        try:
            project_id = params.get('project_id')
            where = ["t.status = 'completed'"]
            wp = []
            if project_id:
                where.append("t.project_id = %s")
                wp.append(project_id)
            where_sql = " AND ".join(where)

            trend = query(
                f"""SELECT t.id, t.test_number, t.created_at,
                        t.max_force, t.pass_rate
                    FROM tests t WHERE {where_sql}
                    ORDER BY t.created_at ASC""",
                wp, fetchall=True)

            comparison = query(
                """SELECT p.id, p.name,
                        ROUND(AVG(t.max_force)::numeric,2) as avg_max_force,
                        ROUND(AVG(t.pass_rate)::numeric,2) as avg_pass_rate,
                        COUNT(t.id) as test_count
                   FROM projects p LEFT JOIN tests t
                        ON t.project_id = p.id AND t.status='completed'
                   GROUP BY p.id, p.name ORDER BY p.id""",
                fetchall=True)

            hist = query(
                f"""SELECT width_bucket(d.force_value, 0, %s, %s) as bucket, COUNT(*) as count
                    FROM data_points d JOIN tests t ON d.test_id = t.id
                    WHERE {where_sql}
                    GROUP BY bucket ORDER BY bucket""",
                [HIST_MAX, HIST_BINS] + wp, fetchall=True)
            bin_w = HIST_MAX / HIST_BINS
            counts = [0] * (HIST_BINS + 2)
            for h in hist:
                b = int(h['bucket']) if h['bucket'] is not None else 0
                if 0 <= b < len(counts):
                    counts[b] += int(h['count'])
            histogram = [{'range_min': round((b - 1) * bin_w, 1),
                          'range_max': round(b * bin_w, 1), 'count': counts[b]}
                         for b in range(1, HIST_BINS + 1)]

            pass_pie = query(
                f"""SELECT
                        SUM(CASE WHEN d.force_value>=%s THEN 1 ELSE 0 END) as pass_pts,
                        SUM(CASE WHEN d.force_value<%s THEN 1 ELSE 0 END) as fail_pts
                    FROM data_points d JOIN tests t ON d.test_id = t.id
                    WHERE {where_sql}""",
                [PASS_THRESHOLD, PASS_THRESHOLD] + wp, fetchone=True)

            json_response(self, {
                'trend': trend, 'comparison': comparison,
                'histogram': histogram,
                'pass_pie': {'pass': int(pass_pie['pass_pts'] or 0),
                             'fail': int(pass_pie['fail_pts'] or 0)},
                'threshold': PASS_THRESHOLD,
            })
        except Exception as e:
            error_response(self, str(e), 500)

    def _export(self, params):
        try:
            test_id = params.get('test_id')
            if not test_id:
                error_response(self, '缺少试验ID')
                return
            data = query(
                """SELECT strip_number, position_mm, force_value, speed, timestamp
                   FROM data_points WHERE test_id = %s
                   ORDER BY strip_number ASC, position_mm ASC""",
                (test_id,), fetchall=True)

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['条带编号', '位置(mm)', '剥离力(N)', '速度(mm/min)', '时间戳'])
            for row in data:
                writer.writerow([row['strip_number'], row['position_mm'], row['force_value'],
                                 row['speed'],
                                 row['timestamp'].isoformat() if row['timestamp'] else ''])

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
