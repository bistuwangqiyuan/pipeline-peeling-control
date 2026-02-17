from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute, get_connection
from api._lib.auth import get_user_from_request
from api._lib.response import json_response, error_response, options_response, get_query_params
from api._lib.simulator import generate_simulation_batch, compute_test_results
import psycopg2.extras


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

            if not test_id:
                error_response(self, '缺少试验ID')
                return

            sim_state = query(
                "SELECT * FROM simulation_state WHERE test_id = %s",
                (test_id,),
                fetchone=True
            )

            test = query(
                "SELECT * FROM peeling_tests WHERE id = %s",
                (test_id,),
                fetchone=True
            )

            if not test:
                error_response(self, '试验不存在', 404)
                return

            if sim_state and sim_state['is_running']:
                current_angle = float(sim_state['current_angle'])
                profiles = sim_state['profiles']
                if isinstance(profiles, str):
                    profiles = json.loads(profiles)

                if current_angle >= 360.0:
                    execute(
                        "UPDATE simulation_state SET is_running = FALSE WHERE test_id = %s",
                        (test_id,)
                    )
                    execute(
                        """UPDATE peeling_tests SET status = 'completed', end_time = CURRENT_TIMESTAMP
                           WHERE id = %s""",
                        (test_id,)
                    )
                    compute_test_results(int(test_id))
                    test = query("SELECT * FROM peeling_tests WHERE id = %s", (test_id,), fetchone=True)
                else:
                    new_angle, rows = generate_simulation_batch(
                        int(test_id), profiles, current_angle
                    )
                    execute(
                        """UPDATE simulation_state
                           SET current_angle = %s, updated_at = CURRENT_TIMESTAMP
                           WHERE test_id = %s""",
                        (new_angle, test_id)
                    )
                    execute(
                        "UPDATE peeling_tests SET current_angle = %s WHERE id = %s",
                        (new_angle, test_id)
                    )

            latest_data = query(
                """SELECT strip_number,
                          position_angle,
                          force_value,
                          speed,
                          displacement,
                          timestamp
                   FROM strip_data
                   WHERE test_id = %s
                     AND id IN (
                         SELECT MAX(id) FROM strip_data
                         WHERE test_id = %s
                         GROUP BY strip_number
                     )
                   ORDER BY strip_number""",
                (test_id, test_id),
                fetchall=True
            )

            recent_history = query(
                """SELECT strip_number, position_angle, force_value, timestamp
                   FROM strip_data
                   WHERE test_id = %s
                   ORDER BY id DESC LIMIT 300""",
                (test_id,),
                fetchall=True
            )

            progress = 0
            if sim_state:
                progress = min(100, float(sim_state['current_angle']) / 360.0 * 100)

            total_force = sum(float(d['force_value']) for d in latest_data) if latest_data else 0
            avg_force = total_force / len(latest_data) if latest_data else 0
            max_force = max((float(d['force_value']) for d in latest_data), default=0)

            json_response(self, {
                'test': test,
                'is_running': bool(sim_state and sim_state['is_running']),
                'current_angle': float(sim_state['current_angle']) if sim_state else 0,
                'progress': round(progress, 2),
                'latest_data': latest_data,
                'recent_history': recent_history,
                'stats': {
                    'total_force': round(total_force, 2),
                    'avg_force': round(avg_force, 2),
                    'max_force': round(max_force, 2),
                    'active_strips': len([d for d in latest_data if float(d['force_value']) > 0])
                }
            })
        except Exception as e:
            error_response(self, str(e), 500)
