from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute_returning
from api._lib.auth import hash_password, create_token
from api._lib.response import json_response, error_response, options_response, get_body


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_POST(self):
        try:
            body = get_body(self)
            username = body.get('username', '').strip()
            password = body.get('password', '')
            phone = body.get('phone', '').strip() or None
            auth_code = body.get('auth_code', '').strip() or None

            if not username or not password:
                error_response(self, '用户名和密码不能为空')
                return

            if len(username) < 2 or len(username) > 50:
                error_response(self, '用户名长度需为2-50个字符')
                return

            if len(password) < 3:
                error_response(self, '密码长度不能少于3个字符')
                return

            existing = query(
                "SELECT id FROM users WHERE username = %s",
                (username,),
                fetchone=True
            )
            if existing:
                error_response(self, '用户名已存在')
                return

            password_hash = hash_password(password)

            user = execute_returning(
                """INSERT INTO users (username, password_hash, phone, role, auth_code)
                   VALUES (%s, %s, %s, 'user', %s)
                   RETURNING id, username, role""",
                (username, password_hash, phone, auth_code)
            )

            token = create_token(user['id'], user['username'], user['role'])

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, details) VALUES (%s, %s, %s, %s)",
                (user['id'], 'register', 'auth', json.dumps({'username': username}))
            )

            json_response(self, {
                'token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                }
            }, 201)
        except Exception as e:
            error_response(self, str(e), 500)
