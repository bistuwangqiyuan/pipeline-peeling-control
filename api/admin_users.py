from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.auth import get_user_from_request, hash_password
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload:
                error_response(self, '未授权访问', 401)
                return

            if payload.get('role') != 'admin':
                error_response(self, '需要管理员权限', 403)
                return

            params = get_query_params(self)
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '50'))
            offset = (page - 1) * per_page

            count_result = query("SELECT COUNT(*) as total FROM users", fetchone=True)

            users = query(
                """SELECT id, username, phone, role, auth_code, is_active, created_at, updated_at
                   FROM users
                   ORDER BY created_at DESC
                   LIMIT %s OFFSET %s""",
                (per_page, offset),
                fetchall=True
            )

            json_response(self, {
                'users': users,
                'total': count_result['total'],
                'page': page,
                'per_page': per_page
            })
        except Exception as e:
            error_response(self, str(e), 500)

    def do_PUT(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload or payload.get('role') != 'admin':
                error_response(self, '需要管理员权限', 403)
                return

            params = get_query_params(self)
            user_id = params.get('id')
            if not user_id:
                error_response(self, '缺少用户ID')
                return

            body = get_body(self)
            fields = []
            values = []

            if 'role' in body:
                fields.append("role = %s")
                values.append(body['role'])
            if 'is_active' in body:
                fields.append("is_active = %s")
                values.append(body['is_active'])
            if 'phone' in body:
                fields.append("phone = %s")
                values.append(body['phone'])
            if 'auth_code' in body:
                fields.append("auth_code = %s")
                values.append(body['auth_code'])
            if 'password' in body and body['password']:
                fields.append("password_hash = %s")
                values.append(hash_password(body['password']))

            if not fields:
                error_response(self, '没有要更新的字段')
                return

            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)

            execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s",
                values
            )

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details) VALUES (%s, %s, %s, %s, %s)",
                (payload['user_id'], 'update_user', 'user', int(user_id),
                 json.dumps({k: v for k, v in body.items() if k != 'password'}))
            )

            user = query(
                "SELECT id, username, phone, role, auth_code, is_active FROM users WHERE id = %s",
                (user_id,),
                fetchone=True
            )
            json_response(self, {'user': user})
        except Exception as e:
            error_response(self, str(e), 500)

    def do_DELETE(self):
        try:
            payload = get_user_from_request(self.headers)
            if not payload or payload.get('role') != 'admin':
                error_response(self, '需要管理员权限', 403)
                return

            params = get_query_params(self)
            user_id = params.get('id')
            if not user_id:
                error_response(self, '缺少用户ID')
                return

            if int(user_id) == payload['user_id']:
                error_response(self, '不能删除自己的账号')
                return

            execute("DELETE FROM users WHERE id = %s", (user_id,))

            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s, %s, %s, %s)",
                (payload['user_id'], 'delete_user', 'user', int(user_id))
            )

            json_response(self, {'message': '用户已删除'})
        except Exception as e:
            error_response(self, str(e), 500)
