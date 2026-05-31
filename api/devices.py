from http.server import BaseHTTPRequestHandler
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.response import json_response, error_response, options_response

# 自动剥离装置状态（论文 4.2 装置参数）。当前为单台单工位设备，
# 状态依据是否存在运行中的试验综合给出。
DEVICE_SPEC = {
    'device_id': 'PEEL-V1.2-001',
    'name': '管道补口自动剥离装置 V1.2（单杆伺服）',
    'actuator': '单杆伺服电动推杆',
    'force_sensor': 'S型拉压力传感器 0-1000N / ±0.1%FS',
    'position_sensor': '绝对式磁编码器 0.01mm',
    'bus': 'RS485 (10ms 周期)',
    'speed_range': '1-100 mm/min',
    'speed_accuracy': '优于 ±0.5% (实测 0.42%)',
    'position_repeat': '优于 ±0.5 mm',
}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        try:
            running = query(
                """SELECT t.id, t.test_number, t.current_position, t.total_positions,
                          t.peel_speed, p.name as project_name
                   FROM tests t LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.is_running = TRUE ORDER BY t.start_time DESC LIMIT 1""",
                fetchone=True)

            if running:
                status = 'running'
                connection = 'online'
            else:
                status = 'idle'
                connection = 'online'

            json_response(self, {
                'device': DEVICE_SPEC,
                'status': status,
                'connection': connection,
                'rs485': 'normal',
                'emergency_stop': False,
                'current_test': running,
            })
        except Exception as e:
            error_response(self, str(e), 500)
