from http.server import BaseHTTPRequestHandler
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.auth import get_user_from_request
from api._lib.response import json_response, error_response, options_response


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload:
                error_response(self, '未授权访问', 401)
                return

            user = query(
                """SELECT id, username, phone, role, auth_code, is_active, created_at
                   FROM users WHERE id = %s""",
                (payload['user_id'],),
                fetchone=True
            )

            if not user:
                error_response(self, '用户不存在', 404)
                return

            has_write_access = user['role'] == 'admin' or user.get('auth_code') == 'test12'

            json_response(self, {
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'phone': user['phone'],
                    'role': user['role'],
                    'is_active': user['is_active'],
                    'has_write_access': has_write_access,
                    'created_at': user['created_at'].isoformat() if user['created_at'] else None
                }
            })
        except Exception as e:
            error_response(self, str(e), 500)
