"""管道补口自动剥离系统 · 上线功能测试 TC-01~TC-15（接口级，可对线上 URL 运行）。

用法：
    python tests/e2e_api.py --base-url https://<your-vercel-app>.vercel.app
    （或设置环境变量 BASE_URL）

脚本将：
    1) 调用 /api/init_db 确保数据库就绪；
    2) 顺序执行 TC-01~TC-15，记录通过/失败与响应耗时；
    3) 打印汇总，并写出 tests/results.json 供报告生成使用。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile

import requests

CASES = [
    ("TC-01", "用户登录（正确/错误凭据）"),
    ("TC-02", "用户注册（新账号 + 重复校验）"),
    ("TC-03", "游客只读访问（无 Token 读接口）"),
    ("TC-04", "项目管理 CRUD（增/查/改/删）"),
    ("TC-05", "试验创建"),
    ("TC-06", "启动剥离试验（仿真开始）"),
    ("TC-07", "实时数据轮询（力-位数据帧）"),
    ("TC-08", "停止/中止试验并回写统计"),
    ("TC-09", "数据分析（单试验指标聚合）"),
    ("TC-10", "数据分析联动钻取（单条带曲线）"),
    ("TC-11", "单试验 Word 报告导出(.docx)"),
    ("TC-12", "项目级报告批量导出(.zip)"),
    ("TC-13", "用户管理（管理员改角色/状态）"),
    ("TC-14", "系统设置读取/更新"),
    ("TC-15", "审计日志记录与查询"),
]


class Runner:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.token = None
        self.results = []
        self.timings = []

    def url(self, path):
        return f"{self.base}{path}"

    def req(self, method, path, token=None, **kw):
        headers = kw.pop('headers', {})
        if token:
            headers['Authorization'] = f'Bearer {token}'
        t0 = time.time()
        r = requests.request(method, self.url(path), headers=headers, timeout=30, **kw)
        dt = (time.time() - t0) * 1000
        self.timings.append((f"{method} {path}", round(dt, 1)))
        return r, dt

    def record(self, cid, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        self.results.append({"id": cid, "name": name, "status": status, "detail": detail})
        print(f"  [{status}] {cid} {name}  {detail}")
        return ok

    # ------------------------------------------------------------------
    def setup(self):
        print("初始化数据库 /api/init_db ...")
        try:
            r, _ = self.req('GET', '/api/init_db')
            print("  init_db:", r.status_code, r.text[:200])
        except Exception as e:
            print("  init_db 异常:", e)

    def run(self):
        d = {}
        # TC-01 登录
        try:
            r, _ = self.req('POST', '/api/auth/login', json={'username': 'admin', 'password': 'admin'})
            ok_good = r.status_code == 200 and r.json().get('token')
            if ok_good:
                self.token = r.json()['token']
            r2, _ = self.req('POST', '/api/auth/login', json={'username': 'admin', 'password': 'wrong'})
            ok_bad = r2.status_code in (400, 401)
            self.record("TC-01", CASES[0][1], ok_good and ok_bad,
                        f"正确登录={r.status_code} 错误登录={r2.status_code}")
        except Exception as e:
            self.record("TC-01", CASES[0][1], False, str(e))

        # TC-02 注册
        try:
            uname = f"tester_{int(time.time())}"
            r, _ = self.req('POST', '/api/auth/register',
                            json={'username': uname, 'password': 'pass123'})
            ok_new = r.status_code in (200, 201) and r.json().get('token')
            r2, _ = self.req('POST', '/api/auth/register',
                             json={'username': uname, 'password': 'pass123'})
            ok_dup = r2.status_code >= 400
            self.record("TC-02", CASES[1][1], ok_new and ok_dup,
                        f"注册={r.status_code} 重复={r2.status_code}")
        except Exception as e:
            self.record("TC-02", CASES[1][1], False, str(e))

        # TC-03 游客只读
        try:
            r, _ = self.req('GET', '/api/projects')
            r2, _ = self.req('GET', '/api/tests')
            ok = r.status_code == 200 and r2.status_code == 200
            self.record("TC-03", CASES[2][1], ok,
                        f"projects={r.status_code} tests={r2.status_code}")
        except Exception as e:
            self.record("TC-03", CASES[2][1], False, str(e))

        # TC-04 项目 CRUD
        try:
            cr, _ = self.req('POST', '/api/projects', token=self.token,
                             json={'name': '自动化测试项目', 'pipe_diameter': 1016,
                                   'location': 'CI'})
            pid = cr.json().get('project', {}).get('id')
            d['pid'] = pid
            gr, _ = self.req('GET', f'/api/projects?id={pid}')
            ur, _ = self.req('PUT', f'/api/projects?id={pid}', token=self.token,
                             json={'status': 'created', 'description': '更新描述'})
            ok = (cr.status_code in (200, 201) and pid and gr.status_code == 200
                  and ur.status_code == 200)
            self.record("TC-04", CASES[3][1], ok,
                        f"create={cr.status_code} get={gr.status_code} put={ur.status_code}")
        except Exception as e:
            self.record("TC-04", CASES[3][1], False, str(e))

        # TC-05 试验创建
        try:
            tn = f"CI-TEST-{int(time.time())}"
            r, _ = self.req('POST', '/api/tests', token=self.token,
                            json={'project_id': d.get('pid'), 'test_number': tn,
                                  'operator': 'CI', 'peel_speed': 10})
            tid = r.json().get('test', {}).get('id')
            d['tid'] = tid
            self.record("TC-05", CASES[4][1], r.status_code in (200, 201) and tid,
                        f"create={r.status_code} tid={tid}")
        except Exception as e:
            self.record("TC-05", CASES[4][1], False, str(e))

        # TC-06 启动试验
        try:
            r, _ = self.req('POST', '/api/test_ops/start', token=self.token,
                            json={'test_id': d.get('tid'), 'n_strips': 30, 'total_mm': 120})
            self.record("TC-06", CASES[5][1], r.status_code == 200,
                        f"start={r.status_code} {r.json().get('status')}")
        except Exception as e:
            self.record("TC-06", CASES[5][1], False, str(e))

        # TC-07 实时轮询
        try:
            frames = 0
            last = None
            for _ in range(6):
                r, _ = self.req('GET', f"/api/realtime_poll?test_id={d.get('tid')}")
                if r.status_code == 200:
                    j = r.json()
                    last = j
                    if j.get('latest_data'):
                        frames += 1
                time.sleep(0.25)
            ok = frames >= 3 and last and last.get('stats', {}).get('max_force', 0) >= 0
            self.record("TC-07", CASES[6][1], ok,
                        f"有效数据帧={frames}/6 进度={last.get('progress') if last else '-'}%")
        except Exception as e:
            self.record("TC-07", CASES[6][1], False, str(e))

        # TC-08 停止
        try:
            r, _ = self.req('POST', '/api/test_ops/stop', token=self.token,
                            json={'test_id': d.get('tid')})
            ok = r.status_code == 200 and r.json().get('status') == 'completed'
            self.record("TC-08", CASES[7][1], ok,
                        f"stop={r.status_code} summary={r.json().get('summary')}")
        except Exception as e:
            self.record("TC-08", CASES[7][1], False, str(e))

        # 选取一个有数据的试验用于分析/报告（优先 CI 试验，回退种子试验）
        analysis_tid = d.get('tid')
        try:
            r, _ = self.req('GET', '/api/tests?status=completed&per_page=50')
            tests = r.json().get('tests', [])
            for t in tests:
                if t.get('id') == d.get('tid'):
                    break
            if not analysis_tid and tests:
                analysis_tid = tests[0]['id']
            # 若 CI 试验数据点不足，改用种子试验
            if tests:
                seeded = [t for t in tests if (t.get('total_positions') or 0) >= 200]
                if seeded:
                    d['seed_tid'] = seeded[0]['id']
                    d['seed_pid'] = seeded[0]['project_id']
        except Exception:
            pass

        # TC-09 分析
        try:
            tid = analysis_tid or d.get('seed_tid')
            r, _ = self.req('GET', f"/api/data?action=analysis&test_id={tid}")
            j = r.json()
            ok = (r.status_code == 200 and 'overall_stats' in j and 'histogram' in j
                  and 'cumulative' in j)
            self.record("TC-09", CASES[8][1], ok,
                        f"analysis={r.status_code} strips={len(j.get('strip_stats', []))}")
            d['ana_tid'] = tid
        except Exception as e:
            self.record("TC-09", CASES[8][1], False, str(e))

        # TC-10 钻取
        try:
            tid = d.get('seed_tid') or d.get('ana_tid')
            r, _ = self.req('GET', f"/api/data?action=history&test_id={tid}&strip_number=1&per_page=500")
            j = r.json()
            ok = r.status_code == 200 and len(j.get('data', [])) > 0
            self.record("TC-10", CASES[9][1], ok,
                        f"history={r.status_code} points={len(j.get('data', []))}")
        except Exception as e:
            self.record("TC-10", CASES[9][1], False, str(e))

        # TC-11 Word 报告
        try:
            tid = d.get('seed_tid') or d.get('ana_tid')
            r, _ = self.req('GET', f"/api/reports/test?test_id={tid}", token=self.token)
            ctype = r.headers.get('Content-Type', '')
            ok = r.status_code == 200 and ('word' in ctype or 'officedocument' in ctype) and len(r.content) > 2000
            self.record("TC-11", CASES[10][1], ok,
                        f"docx={r.status_code} bytes={len(r.content)}")
        except Exception as e:
            self.record("TC-11", CASES[10][1], False, str(e))

        # TC-12 项目 ZIP
        try:
            pid = d.get('seed_pid')
            if not pid:
                rp, _ = self.req('GET', '/api/projects?per_page=50')
                for p in rp.json().get('projects', []):
                    if (p.get('test_count') or 0) > 0:
                        pid = p['id']
                        break
            r, _ = self.req('GET', f"/api/reports/project?project_id={pid}", token=self.token)
            ok = r.status_code == 200
            if ok:
                try:
                    zf = zipfile.ZipFile(io.BytesIO(r.content))
                    ok = len(zf.namelist()) >= 1
                except Exception:
                    ok = False
            self.record("TC-12", CASES[11][1], ok,
                        f"zip={r.status_code} bytes={len(r.content)}")
        except Exception as e:
            self.record("TC-12", CASES[11][1], False, str(e))

        # TC-13 用户管理
        try:
            r, _ = self.req('GET', '/api/admin/users', token=self.token)
            users = r.json().get('users', [])
            target = next((u for u in users if u['username'].startswith('tester_')), None)
            ok = r.status_code == 200 and len(users) > 0
            if target:
                ur, _ = self.req('PUT', f"/api/admin?id={target['id']}", token=self.token,
                                 json={'role': 'user', 'status': 1})
                ok = ok and ur.status_code == 200
            self.record("TC-13", CASES[12][1], ok,
                        f"users={r.status_code} count={len(users)}")
        except Exception as e:
            self.record("TC-13", CASES[12][1], False, str(e))

        # TC-14 系统设置
        try:
            r, _ = self.req('GET', '/api/settings')
            ur, _ = self.req('PUT', '/api/settings', token=self.token,
                             json={'settings': {'polling_interval': '200'}})
            ok = r.status_code == 200 and ur.status_code == 200
            self.record("TC-14", CASES[13][1], ok,
                        f"get={r.status_code} put={ur.status_code}")
        except Exception as e:
            self.record("TC-14", CASES[13][1], False, str(e))

        # TC-15 审计日志
        try:
            r, _ = self.req('GET', '/api/admin/audit?per_page=20', token=self.token)
            logs = r.json().get('logs', [])
            ok = r.status_code == 200 and len(logs) > 0
            self.record("TC-15", CASES[14][1], ok,
                        f"audit={r.status_code} logs={len(logs)}")
        except Exception as e:
            self.record("TC-15", CASES[14][1], False, str(e))

    def summary(self):
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        total = len(self.results)
        print("\n" + "=" * 60)
        print(f"测试结果: {passed}/{total} 通过")
        print("=" * 60)
        out = {
            'base_url': self.base,
            'passed': passed, 'total': total,
            'results': self.results,
            'timings': self.timings,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("结果已写入", path)
        return passed == total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default=os.environ.get('BASE_URL', ''))
    args = ap.parse_args()
    if not args.base_url:
        print("请通过 --base-url 或环境变量 BASE_URL 指定部署地址")
        sys.exit(2)
    runner = Runner(args.base_url)
    runner.setup()
    runner.run()
    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
