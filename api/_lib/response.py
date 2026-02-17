import json
import datetime
from decimal import Decimal


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        return super().default(obj)


def json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.end_headers()
    body = json.dumps(data, cls=CustomEncoder, ensure_ascii=False)
    handler.wfile.write(body.encode('utf-8'))


def error_response(handler, message, status=400):
    json_response(handler, {'error': message}, status)


def options_response(handler):
    handler.send_response(200)
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.end_headers()


def get_body(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    if content_length == 0:
        return {}
    body = handler.rfile.read(content_length)
    return json.loads(body.decode('utf-8'))


def get_query_params(handler):
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
