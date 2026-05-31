from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.auth import get_user_from_request, can_modify
from api._lib.response import json_response, error_response, options_response, get_body


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    # 读取系统设置（游客可读，前端需要阈值/刷新间隔等）
    def do_GET(self):
        try:
            settings = query(
                "SELECT setting_key, setting_value, description, updated_at FROM settings ORDER BY id",
                fetchall=True)
            settings_dict = {s['setting_key']: s['setting_value'] for s in settings}
            json_response(self, {'settings': settings, 'settings_map': settings_dict})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_PUT(self):
        try:
            payload = get_user_from_request(self.headers)
            if not can_modify(payload):
                error_response(self, '无修改权限', 403)
                return
            body = get_body(self)
            updates = body.get('settings', {})
            if not updates:
                error_response(self, '没有要更新的设置')
                return
            for key, value in updates.items():
                execute(
                    """UPDATE settings SET setting_value=%s, updated_by=%s, updated_at=NOW()
                       WHERE setting_key=%s""",
                    (str(value), payload['user_id'], key))
            query(
                "INSERT INTO audit_log (user_id, action, resource_type, details) VALUES (%s,%s,%s,%s)",
                (payload['user_id'], 'update_settings', 'settings', json.dumps(updates)))
            settings = query(
                "SELECT setting_key, setting_value, description FROM settings ORDER BY id",
                fetchall=True)
            json_response(self, {'settings': settings, 'message': '设置已更新'})
        except Exception as e:
            error_response(self, str(e), 500)
