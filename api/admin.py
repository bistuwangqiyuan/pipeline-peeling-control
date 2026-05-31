from http.server import BaseHTTPRequestHandler
import json
import csv
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import query, execute
from api._lib.auth import get_user_from_request, hash_password, is_admin
from api._lib.response import json_response, error_response, options_response, get_body, get_query_params


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        options_response(self)

    def do_GET(self):
        params = get_query_params(self)
        action = params.get('action', 'users')
        if action == 'users':
            self._list_users(params)
        elif action == 'audit':
            if params.get('export') == 'csv':
                self._audit_csv(params)
            else:
                self._audit_log(params)
        else:
            error_response(self, 'Unknown action')

    def do_PUT(self):
        self._update_user()

    def do_DELETE(self):
        self._delete_user()

    def _list_users(self, params):
        try:
            payload = get_user_from_request(self.headers)
            if not is_admin(payload):
                error_response(self, '需要管理员权限', 403)
                return
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '50'))
            offset = (page - 1) * per_page
            count_result = query("SELECT COUNT(*) as total FROM users", fetchone=True)
            users = query(
                """SELECT id, username, phone, role, auth_code, status, created_at, updated_at
                   FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (per_page, offset), fetchall=True)
            json_response(self, {'users': users, 'total': count_result['total'], 'page': page})
        except Exception as e:
            error_response(self, str(e), 500)

    def _update_user(self):
        try:
            payload = get_user_from_request(self.headers)
            if not is_admin(payload):
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
            for key in ['role', 'phone', 'auth_code']:
                if key in body:
                    fields.append(f"{key} = %s")
                    values.append(body[key])
            if 'status' in body:
                fields.append("status = %s")
                values.append(int(body['status']))
            if body.get('password'):
                fields.append("password_hash = %s")
                values.append(hash_password(body['password']))
            if not fields:
                error_response(self, '没有要更新的字段')
                return
            fields.append("updated_at = NOW()")
            values.append(user_id)
            execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", values)
            query(
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details) VALUES (%s,%s,%s,%s,%s)",
                (payload['user_id'], 'update_user', 'user', int(user_id),
                 json.dumps({k: v for k, v in body.items() if k != 'password'})))
            user = query(
                "SELECT id, username, phone, role, auth_code, status FROM users WHERE id = %s",
                (user_id,), fetchone=True)
            json_response(self, {'user': user})
        except Exception as e:
            error_response(self, str(e), 500)

    def _delete_user(self):
        try:
            payload = get_user_from_request(self.headers)
            if not is_admin(payload):
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
                "INSERT INTO audit_log (user_id, action, resource_type, resource_id) VALUES (%s,%s,%s,%s)",
                (payload['user_id'], 'delete_user', 'user', int(user_id)))
            json_response(self, {'message': '用户已删除'})
        except Exception as e:
            error_response(self, str(e), 500)

    def _audit_filters(self, params):
        where = []
        wp = []
        if params.get('action_filter'):
            where.append("a.action = %s")
            wp.append(params['action_filter'])
        if params.get('user'):
            where.append("u.username ILIKE %s")
            wp.append(f"%{params['user']}%")
        return (" AND ".join(where) if where else "1=1"), wp

    def _audit_log(self, params):
        try:
            payload = get_user_from_request(self.headers)
            if not is_admin(payload):
                error_response(self, '需要管理员权限', 403)
                return
            page = int(params.get('page', '1'))
            per_page = int(params.get('per_page', '50'))
            offset = (page - 1) * per_page
            where_sql, wp = self._audit_filters(params)
            count_result = query(
                f"SELECT COUNT(*) as total FROM audit_log a LEFT JOIN users u ON a.user_id=u.id WHERE {where_sql}",
                wp, fetchone=True)
            logs = query(
                f"""SELECT a.*, u.username FROM audit_log a
                    LEFT JOIN users u ON a.user_id = u.id WHERE {where_sql}
                    ORDER BY a.created_at DESC LIMIT %s OFFSET %s""",
                wp + [per_page, offset], fetchall=True)
            json_response(self, {'logs': logs, 'total': count_result['total'], 'page': page})
        except Exception as e:
            error_response(self, str(e), 500)

    def _audit_csv(self, params):
        try:
            payload = get_user_from_request(self.headers)
            if not is_admin(payload):
                error_response(self, '需要管理员权限', 403)
                return
            where_sql, wp = self._audit_filters(params)
            logs = query(
                f"""SELECT a.created_at, u.username, a.action, a.resource_type,
                           a.resource_id, a.details FROM audit_log a
                    LEFT JOIN users u ON a.user_id = u.id WHERE {where_sql}
                    ORDER BY a.created_at DESC LIMIT 10000""",
                wp, fetchall=True)
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['时间', '用户', '操作', '资源类型', '资源ID', '详情'])
            for r in logs:
                writer.writerow([
                    r['created_at'].isoformat() if r['created_at'] else '',
                    r['username'] or '', r['action'], r['resource_type'] or '',
                    r['resource_id'] or '',
                    json.dumps(r['details'], ensure_ascii=False) if r['details'] else ''])
            content = output.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename=audit_log.csv')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write('\ufeff'.encode('utf-8'))
            self.wfile.write(content.encode('utf-8'))
        except Exception as e:
            error_response(self, str(e), 500)
