"""离线单元测试（无需数据库）：验证力学仿真模型与 Word 报告生成逻辑。

运行：python tests/offline_unit.py
"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


# 1) 真实数据回放引擎（无 mock 生成）
from api._lib import simulator

check("已移除 mock 生成函数 generate_simulation_batch",
      not hasattr(simulator, 'generate_simulation_batch'))
check("已移除随机剖面函数 generate_strip_profiles",
      not hasattr(simulator, 'generate_strip_profiles'))

# 1a) build_replay_template：用伪造的"真实"序列查询验证模板结构
FAKE_SERIES_ROWS = []
for s in range(1, 4):
    for pos in (0.0, 5.0, 10.0, 15.0, 20.0):
        FAKE_SERIES_ROWS.append({'strip_number': s, 'position_mm': pos,
                                 'force_value': 90.0 - s + pos * 0.1, 'speed': 10.0})


def fake_sim_query(sql, params=None, fetchone=False, fetchall=False):
    s = ' '.join(sql.split())
    if 'GROUP BY test_id' in s:
        return {'test_id': 99, 'c': 15}
    if 'ORDER BY strip_number, position_mm' in s:
        return FAKE_SERIES_ROWS
    return None


simulator.query = fake_sim_query
tpl = simulator.build_replay_template(1)
check("生成回放模板", tpl is not None)
check("模板含 3 条带", tpl and tpl['n_strips'] == 3, f"n_strips={tpl['n_strips'] if tpl else None}")
check("模板 max_pos=20", tpl and abs(tpl['max_pos'] - 20.0) < 1e-6, f"max_pos={tpl['max_pos'] if tpl else None}")
all_real = all(0 <= p[1] <= simulator.FORCE_SENSOR_RANGE
               for pts in tpl['replay'].values() for p in pts)
check("回放力值均在 0-1000N 区间", all_real)

# 1b) reveal：仅揭示 (old,new] 区间内的真实点，且数值来自模板（非生成）
captured = {}


class _FakeCur:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def cursor(self):
        return _FakeCur()

    def commit(self):
        pass

    def close(self):
        pass


simulator.get_connection = lambda: _FakeConn()
simulator.psycopg2.extras.execute_values = lambda cur, sql, rows: captured.update(rows=rows)

template = {'replay': {'1': [[0.0, 10.0, 10], [5.0, 90.0, 10], [10.0, 95.0, 10]],
                       '2': [[0.0, 5.0, 10], [5.0, 80.0, 10], [10.0, 85.0, 10]]},
            'max_pos': 10.0, 'n_strips': 2}
n = simulator.reveal(7, template, 0.0, 5.0)
rows = captured.get('rows', [])
check("reveal 仅揭示区间(0,5]的点", n == 2 and len(rows) == 2, f"n={n}")
revealed_forces = sorted(r[3] for r in rows)
check("reveal 数值取自真实模板(80/90)", revealed_forces == [80.0, 90.0], f"forces={revealed_forces}")
n2 = simulator.reveal(7, template, 5.0, 5.0)
check("reveal 空区间不写入", n2 == 0)
check("playback_step>0", simulator.playback_step(2786) > 0)


# 2) Word 报告生成（monkeypatch 数据库）
import api.reports as reports

FAKE_TEST = {
    'id': 1, 'test_number': 'UT-001', 'sample_name': 'P1016R-02F',
    'operator': 'UT', 'peel_speed': 10, 'status': 'completed', 'n_strips': 3,
    'project_name': '单元测试项目', 'pipe_diameter': 1016, 'layer_width': 600,
    'layer_thickness': 1.0, 'location': '实验室',
}
FAKE_STRIPS = [
    {'strip_number': 1, 'avg_force': 90.1, 'max_force': 98.5, 'min_force': 12.0, 'std_force': 8.2, 'pass_fail': True},
    {'strip_number': 2, 'avg_force': 55.3, 'max_force': 96.0, 'min_force': 5.0, 'std_force': 22.0, 'pass_fail': False},
    {'strip_number': 3, 'avg_force': 88.0, 'max_force': 99.0, 'min_force': 20.0, 'std_force': 10.1, 'pass_fail': True},
]
FAKE_OVERALL = {'avg_force': 77.8, 'max_force': 99.0, 'min_force': 5.0,
                'total_points': 360, 'pass_rate': 66.7}


def fake_query(sql, params=None, fetchone=False, fetchall=False):
    s = ' '.join(sql.split())
    if 'GROUP BY strip_number' in s:
        return FAKE_STRIPS
    if 'FROM tests t' in s:
        return FAKE_TEST
    if 'FROM data_points WHERE test_id' in s and 'GROUP BY' not in s:
        return FAKE_OVERALL
    return None


reports.query = fake_query
content, fname = reports._build_report(1)
check("生成 .docx 字节流", content is not None and len(content) > 2000, f"bytes={len(content) if content else 0}")
check("docx 为合法 zip(OOXML)", content[:2] == b'PK')
check("文件名含 test_number", 'UT-001' in fname, fname)

# 验证可被 docx 重新打开
try:
    from docx import Document
    Document(io.BytesIO(content))
    check("docx 可被重新解析", True)
except Exception as e:
    check("docx 可被重新解析", False, str(e))


print("\n" + "=" * 50)
if failures:
    print("离线单元测试失败:", failures)
    sys.exit(1)
print("离线单元测试全部通过")
