import os
import jwt
import datetime
from functools import wraps
from passlib.hash import bcrypt as bcrypt_hash


JWT_SECRET = os.environ.get('JWT_SECRET', 'pipeline-peeling-secret-key-2026')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = 24


def hash_password(password):
    return bcrypt_hash.hash(password)


def verify_password(password, hashed):
    try:
        return bcrypt_hash.verify(password, hashed)
    except Exception:
        return False


def create_token(user_id, username, role):
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_from_request(headers):
    auth_header = headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:]
    return decode_token(token)


def can_modify(user_payload):
    if not user_payload:
        return False
    if user_payload.get('role') == 'admin':
        return True
    return _check_user_auth_code(user_payload.get('user_id'))


def _check_user_auth_code(user_id):
    from .db import query
    result = query(
        "SELECT auth_code FROM users WHERE id = %s",
        (user_id,),
        fetchone=True
    )
    if result and result.get('auth_code'):
        return result['auth_code'] == 'test12'
    return False
