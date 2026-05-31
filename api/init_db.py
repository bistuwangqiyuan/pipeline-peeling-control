from http.server import BaseHTTPRequestHandler
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api._lib.db import get_connection
from api._lib.auth import hash_password
import psycopg2.extras

# ---------------------------------------------------------------------------
# 论文第四章 6 表数据模型：users / projects / tests / data_points / settings /
# audit_log。所有力值单位为牛顿(N)，量程 0–1000N，与真实数据集一致。
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'user',
    phone VARCHAR(20),
    auth_code VARCHAR(64),
    status SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    pipe_diameter DECIMAL(10,2) NOT NULL DEFAULT 1016,
    layer_width DECIMAL(10,2) NOT NULL DEFAULT 600,
    layer_thickness DECIMAL(10,4) NOT NULL DEFAULT 1.0,
    strip_width DECIMAL(10,2) NOT NULL DEFAULT 20,
    location VARCHAR(200),
    status VARCHAR(20) NOT NULL DEFAULT 'created',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tests (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    test_number VARCHAR(64) NOT NULL,
    sample_name VARCHAR(128),
    operator VARCHAR(100),
    peel_speed DECIMAL(8,2) NOT NULL DEFAULT 10,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ambient_temp DECIMAL(5,2),
    pipe_temp DECIMAL(5,2),
    humidity DECIMAL(5,2),
    notes TEXT,
    n_strips INTEGER NOT NULL DEFAULT 0,
    total_positions INTEGER NOT NULL DEFAULT 0,
    current_position DECIMAL(10,2) NOT NULL DEFAULT 0,
    max_force DECIMAL(10,2),
    pass_rate DECIMAL(6,2),
    profiles JSONB,
    is_running BOOLEAN NOT NULL DEFAULT FALSE,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_points (
    id BIGSERIAL PRIMARY KEY,
    test_id INTEGER REFERENCES tests(id) ON DELETE CASCADE,
    strip_number INTEGER NOT NULL,
    position_mm DECIMAL(10,2) NOT NULL,
    force_value DECIMAL(10,4) NOT NULL,
    speed DECIMAL(8,2),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    description TEXT,
    updated_by INTEGER REFERENCES users(id),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details JSONB,
    ip_address VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_points_test ON data_points(test_id);
CREATE INDEX IF NOT EXISTS idx_data_points_test_strip ON data_points(test_id, strip_number);
CREATE INDEX IF NOT EXISTS idx_tests_project ON tests(project_id);
CREATE INDEX IF NOT EXISTS idx_tests_status ON tests(status);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""

# 幂等迁移：兼容旧 schema（users.is_active / projects 缺列等），保证升级到论文模型。
MIGRATE_SQL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS status SMALLINT NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_code VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS strip_width DECIMAL(10,2) DEFAULT 20;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS layer_thickness DECIMAL(10,4) DEFAULT 1.0;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS location VARCHAR(200);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'created';
"""

# 销毁式重建（reset=1）：清理旧实现与本实现的全部表后重建。
DROP_SQL = """
DROP TABLE IF EXISTS data_points, strip_data, test_results, simulation_state,
    audit_log, tests, peeling_tests, settings, system_settings, projects, users CASCADE;
"""

DEFAULT_USERS = [
    ('admin', 'admin', 'admin', None),
    ('admin1', 'admin1', 'admin', None),
    ('admin2', 'admin2', 'admin', None),
    ('user1', 'user1', 'user', None),
    ('test1', 'test1', 'user', 'test12'),
]

# 全部参数对齐论文与真实数据（力值单位 N，刷新 200ms）
DEFAULT_SETTINGS = [
    ('pipe_diameter', '1016', '管道直径(mm)'),
    ('layer_width', '600', '防腐层宽度(mm)'),
    ('layer_thickness', '1.0', '防腐层厚度(mm)'),
    ('strip_width', '20', '每条带宽度(mm)'),
    ('peel_speed', '10', '剥离速度(mm/min)'),
    ('force_sensor_range', '1000', 'S型拉压力传感器量程(N)'),
    ('pass_threshold', '70', '合格剥离力阈值(N)'),
    ('good_bond_platform', '96', '良好粘接平台力值(N)'),
    ('force_alarm_high', '120', '剥离力上限报警(N)'),
    ('force_alarm_low', '5', '剥离力下限报警(N)'),
    ('polling_interval', '200', '实时刷新间隔(ms)'),
    ('position_step', '5', '模拟位置步进(mm/step)'),
    ('sampling_rate', '10', '力位同步采集频率(Hz)'),
]

SEED_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'analysis', 'seed_data.json'
)


def _load_seed():
    try:
        with open(SEED_JSON, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _seed_real_data(conn):
    """写入由真实数据集生成的项目 / 试验 / 力-位数据点。"""
    seed = _load_seed()
    if not seed:
        return {'seeded': False, 'reason': 'seed_data.json 未找到'}

    admin_id = None
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        row = cur.fetchone()
        admin_id = row[0] if row else None

    project_ids = {}
    test_ids = {}
    with conn.cursor() as cur:
        for p in seed.get('projects', []):
            cur.execute(
                """INSERT INTO projects
                   (name, description, pipe_diameter, layer_width, layer_thickness,
                    location, status, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (p['name'], p.get('description', ''), p.get('pipe_diameter', 1016),
                 p.get('layer_width', 600), p.get('layer_thickness', 1.0),
                 p.get('location', ''), p.get('status', 'completed'), admin_id)
            )
            project_ids[p['key']] = cur.fetchone()[0]

        for t in seed.get('tests', []):
            cur.execute(
                """INSERT INTO tests
                   (project_id, test_number, sample_name, operator, peel_speed,
                    status, n_strips, total_positions, current_position, max_force,
                    pass_rate, is_running, start_time, end_time, created_by)
                   VALUES (%s,%s,%s,%s,%s,'completed',%s,%s,%s,%s,%s,FALSE,
                           NOW(), NOW(), %s) RETURNING id""",
                (project_ids[t['project_key']], t['test_number'], t.get('sample_name'),
                 t.get('operator', ''), t.get('peel_speed', 10),
                 t.get('n_strips', 0), t.get('n_positions', 0),
                 t.get('n_positions', 0), t.get('max_force'), t.get('pass_rate'),
                 admin_id)
            )
            test_ids[t['key']] = cur.fetchone()[0]

        rows = []
        for d in seed.get('data_points', []):
            tid = test_ids.get(d['test_key'])
            if tid is None:
                continue
            rows.append((tid, d['strip_number'], d['position_mm'],
                         d['force_value'], d.get('speed', 10)))
        if rows:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO data_points
                   (test_id, strip_number, position_mm, force_value, speed)
                   VALUES %s""",
                rows, page_size=2000
            )
    conn.commit()
    return {'seeded': True, 'projects': len(project_ids),
            'tests': len(test_ids), 'data_points': len(seed.get('data_points', []))}


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

    def _reset_requested(self):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        return q.get('reset', ['0'])[0] in ('1', 'true', 'yes')

    def _init(self):
        conn = get_connection()
        reset = self._reset_requested()
        try:
            # 1) 销毁式重建（可选）
            if reset:
                with conn.cursor() as cur:
                    cur.execute(DROP_SQL)
                    conn.commit()

            # 2) 建表（幂等）+ 迁移旧 schema（幂等）
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
                conn.commit()
            with conn.cursor() as cur:
                try:
                    cur.execute(MIGRATE_SQL)
                    conn.commit()
                except Exception:
                    conn.rollback()

            # 3) 预置账号与系统设置（幂等）
            with conn.cursor() as cur:
                for username, password, role, auth_code in DEFAULT_USERS:
                    cur.execute(
                        """INSERT INTO users (username, password_hash, role, auth_code)
                           VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING""",
                        (username, hash_password(password), role, auth_code)
                    )
                for key, value, desc in DEFAULT_SETTINGS:
                    cur.execute(
                        """INSERT INTO settings (setting_key, setting_value, description)
                           VALUES (%s, %s, %s) ON CONFLICT (setting_key) DO NOTHING""",
                        (key, value, desc)
                    )
                conn.commit()

            # 4) 真实数据种子（仅当 tests 为空时写入，保证幂等）
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM tests")
                test_count = cur.fetchone()[0]

            seed_result = {'seeded': False, 'reason': 'tests 已有数据'}
            if test_count == 0:
                seed_result = _seed_real_data(conn)

            self._json({'message': '数据库初始化/迁移成功', 'status': 'initialized',
                        'reset': reset, 'seed': seed_result})
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
