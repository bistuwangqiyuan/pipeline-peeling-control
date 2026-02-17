from http.server import BaseHTTPRequestHandler
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import get_connection
from api._lib.auth import hash_password

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    auth_code VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    pipe_diameter DECIMAL(10,2) NOT NULL DEFAULT 1000,
    layer_width DECIMAL(10,2) NOT NULL DEFAULT 600,
    layer_thickness DECIMAL(10,4) NOT NULL DEFAULT 1.0,
    strip_count INTEGER NOT NULL DEFAULT 30,
    strip_width DECIMAL(10,2) NOT NULL DEFAULT 20,
    estimated_force DECIMAL(12,2) NOT NULL DEFAULT 30000,
    location VARCHAR(200),
    status VARCHAR(20) DEFAULT 'created',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS peeling_tests (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    test_number VARCHAR(50) NOT NULL,
    operator VARCHAR(100),
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending',
    ambient_temp DECIMAL(5,2),
    pipe_temp DECIMAL(5,2),
    humidity DECIMAL(5,2),
    notes TEXT,
    current_angle DECIMAL(10,4) DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strip_data (
    id BIGSERIAL PRIMARY KEY,
    test_id INTEGER REFERENCES peeling_tests(id) ON DELETE CASCADE,
    strip_number INTEGER NOT NULL CHECK (strip_number BETWEEN 1 AND 30),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    position_angle DECIMAL(10,4),
    force_value DECIMAL(12,4),
    speed DECIMAL(10,4),
    displacement DECIMAL(10,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_results (
    id SERIAL PRIMARY KEY,
    test_id INTEGER REFERENCES peeling_tests(id) ON DELETE CASCADE,
    strip_number INTEGER NOT NULL,
    avg_force DECIMAL(12,4),
    max_force DECIMAL(12,4),
    min_force DECIMAL(12,4),
    std_force DECIMAL(12,4),
    total_displacement DECIMAL(10,4),
    pass_fail BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(test_id, strip_number)
);

CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    description TEXT,
    updated_by INTEGER REFERENCES users(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details JSONB,
    ip_address VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_state (
    test_id INTEGER PRIMARY KEY REFERENCES peeling_tests(id) ON DELETE CASCADE,
    profiles JSONB NOT NULL,
    current_angle DECIMAL(10,4) DEFAULT 0,
    is_running BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_strip_data_test_id ON strip_data(test_id);
CREATE INDEX IF NOT EXISTS idx_strip_data_test_strip ON strip_data(test_id, strip_number);
CREATE INDEX IF NOT EXISTS idx_strip_data_timestamp ON strip_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_peeling_tests_project ON peeling_tests(project_id);
CREATE INDEX IF NOT EXISTS idx_peeling_tests_status ON peeling_tests(status);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
"""


DEFAULT_SETTINGS = [
    ('pipe_diameter', '1000', '管道直径(mm)'),
    ('layer_width', '600', '防腐层宽度(mm)'),
    ('layer_thickness', '1.0', '防腐层厚度(mm)'),
    ('strip_count', '30', '剥离条数'),
    ('strip_width', '20', '每条宽度(mm)'),
    ('estimated_force', '30000', '预估拉力(N)'),
    ('force_alarm_high', '35000', '拉力上限报警(N)'),
    ('force_alarm_low', '100', '拉力下限报警(N)'),
    ('polling_interval', '1500', '轮询间隔(ms)'),
    ('simulation_speed', '2.0', '模拟角度步进(deg/step)'),
]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        return self._init()

    def do_POST(self):
        return self._init()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def _init(self):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_name = 'users')")
                exists = cur.fetchone()[0]

            if exists:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM users")
                    count = cur.fetchone()[0]
                if count > 0:
                    self._json({'message': '数据库已初始化', 'status': 'already_initialized'})
                    return

            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
                conn.commit()

            default_users = [
                ('admin', hash_password('admin'), None, 'admin', None),
                ('admin1', hash_password('admin1'), None, 'admin', None),
                ('admin2', hash_password('admin2'), None, 'admin', None),
                ('user1', hash_password('user1'), None, 'user', None),
                ('test1', hash_password('test1'), None, 'test', None),
            ]
            with conn.cursor() as cur:
                for u in default_users:
                    cur.execute(
                        """INSERT INTO users (username, password_hash, phone, role, auth_code)
                           VALUES (%s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING""",
                        u
                    )
                for s in DEFAULT_SETTINGS:
                    cur.execute(
                        """INSERT INTO system_settings (setting_key, setting_value, description)
                           VALUES (%s, %s, %s) ON CONFLICT (setting_key) DO NOTHING""",
                        s
                    )
                conn.commit()

            self._json({'message': '数据库初始化成功', 'status': 'initialized'})
        except Exception as e:
            conn.rollback()
            self._json({'error': str(e)}, 500)
        finally:
            conn.close()

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
