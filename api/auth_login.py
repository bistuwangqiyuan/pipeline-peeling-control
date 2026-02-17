from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query
from api._lib.auth import verify_password, create_token
from api._lib.response import json_response, error_response, options_response, get_body


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_POST(self):
        try:
            body = get_body(self)
            username = body.get('username', '').strip()
            password = body.get('password', '')

            if not username or not password:
                error_response(self, '用户名和密码不能为空')
                return

            user = query(
                "SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s",
                (username,),
                fetchone=True
            )

            if not user:
                error_response(self, '用户名或密码错误', 401)
                return

            if not user['is_active']:
                error_response(self, '账号已被禁用', 403)
                return

            if not verify_password(password, user['password_hash']):
                error_response(self, '用户名或密码错误', 401)
                return

            token = create_token(user['id'], user['username'], user['role'])

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, details) VALUES (%s, %s, %s, %s)",
                (user['id'], 'login', 'auth', json.dumps({'username': username}))
            )

            json_response(self, {
                'token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                }
            })
        except Exception as e:
            error_response(self, str(e), 500)
