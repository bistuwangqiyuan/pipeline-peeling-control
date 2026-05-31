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


# 1) 仿真模型
from api._lib import simulator

profiles = simulator.generate_strip_profiles(30, 600)
check("生成30条带剖面", len(profiles) == 30)
all_in_range = True
platform_hit = 0
for p in profiles:
    for pos in range(0, 600, 5):
        f = simulator.force_at(pos, 600, p)
        if not (0 <= f <= simulator.FORCE_SENSOR_RANGE):
            all_in_range = False
        if 80 <= f <= 100:
            platform_hit += 1
check("力值均在 0-1000N 区间", all_in_range)
check("存在良好粘接平台(80-100N)采样", platform_hit > 50, f"platform_hit={platform_hit}")
ramp = simulator.force_at(0, 600, profiles[0])
check("起剥点力值≈0(上升段)", ramp < 20, f"f(0)={ramp:.1f}")


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
