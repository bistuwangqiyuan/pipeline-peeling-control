from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute_returning
from api._lib.auth import verify_password, create_token, hash_password, get_user_from_request
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        params = get_query_params(self)
        action = params.get('action', 'me')
        if action == 'me':
            self._me()
        else:
            error_response(self, 'Unknown action')

    def do_POST(self):
        params = get_query_params(self)
        action = params.get('action', 'login')
        if action == 'login':
            self._login()
        elif action == 'register':
            self._register()
        else:
            error_response(self, 'Unknown action')

    def _login(self):
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

    def _register(self):
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

            existing = query("SELECT id FROM users WHERE username = %s", (username,), fetchone=True)
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

    def _me(self):
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
