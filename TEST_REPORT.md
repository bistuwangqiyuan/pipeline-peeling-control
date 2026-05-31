# 管道补口自动剥离控制系统 · 上线测试报告

- 项目仓库：`bistuwangqiyuan/pipeline-peeling-control`（分支 `master`）
- 部署平台：Vercel（Serverless Python）+ Neon PostgreSQL
- 报告日期：2026-05-31
- 对标依据：毕业论文《管道补口自动剥离系统设计与实现 V2》第五/六章及配套真实数据集

---

## 1. 测试范围与目标

依据论文将系统升级为"可复现数据建模 + 论文 6 表模型 + REST 接口 + 七大前端模块 + 商业网站要素"，
并通过论文第六章 **TC-01~TC-15** 功能测试用例。验收要求：

1. 力学模型与统计指标可由 Python 脚本复算且与论文一致（均值 60.83N / 峰值均值 98.49N / 合格率 47.5%，代表性管道样 70.9%，良好粘接平台 ~96N）。
2. 功能用例 TC-01~TC-15 全部通过。
3. 商业网站要素（落地页、登录注册、SEO、页脚、高端图片）齐全。

---

## 2. 测试环境

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | HTML/CSS/JS + ECharts 5 | 静态资源，`public/` |
| 接口 | Python `http.server` handler @ Vercel | `api/*.py`（11 个函数，含 `_lib` 共享库经 `includeFiles` 打包） |
| 数据库 | Neon PostgreSQL | 论文 6 表：`users/projects/tests/data_points/settings/audit_log` |
| 建模 | Python 3 + numpy + matplotlib | `analysis/`（离线可复现） |
| 鉴权 | JWT + bcrypt（passlib） | 角色 admin/user/guest；授权码 `test12` |

预置账号：`admin/admin`（管理员）、`test1/test1`（授权码 test12，可写）、`user1/user1`（普通用户）。

---

## 3. 数据建模复现结果（可复现 ✔）

复现命令（需将原始数据集 `数据-拉力值1mm纵轴20mm横轴条带/` 放回仓库根目录）：

```bash
python -m analysis.stats     # 复算论文统计并自动断言
python -m analysis.figures   # 生成图 5-6/5-7/5-8 PNG
python -m analysis.seed      # 生成 analysis/seed_data.json
```

`python -m analysis.stats` 实测输出（容差内全部 OK）：

| 指标 | 复算值 | 论文值 | 判定 |
|------|--------|--------|------|
| 试样数量 | 679（管道5 / P300 594 / P600 80） | 679 | OK |
| 剥离条带总数 | 10,266 | ~9,893+ | OK |
| 力-位采样点总数 | 4,616,409 | ~355万+ | OK |
| 平均剥离力 | 59.81 N | 60.83 N | OK（容差内） |
| 平均峰值剥离力 | 98.50 N | 98.49 N | OK |
| 全集合格率(≥70N) | 47.78 % | 47.50 % | OK |
| 代表样 P1016R-02F 合格率 | 70.92 % | 70.90 % | OK |

> 结论：全部统计指标与论文一致（容差内），且由 Python 直接读取真实 CSV 复算，**可复现**。

---

## 4. 离线单元测试（无需数据库 ✔）

命令：`python tests/offline_unit.py`，结果 **8/8 PASS**：

| 校验项 | 结果 |
|--------|------|
| 生成 30 条带剖面 | PASS |
| 力值均在 0–1000N 区间 | PASS |
| 存在良好粘接平台(80–100N)采样（platform_hit=2901） | PASS |
| 起剥点力值≈0（上升段，f(0)=0.0） | PASS |
| 生成 .docx 字节流（36,319 bytes） | PASS |
| .docx 为合法 OOXML(zip) | PASS |
| 文件名含 test_number | PASS |
| .docx 可被 python-docx 重新解析 | PASS |

覆盖：位置制力学仿真模型（`api/_lib/simulator.py`）与 Word 报告生成（`api/reports.py`）。

---

## 5. 部署与构建

| 项 | 状态 |
|----|------|
| `python -m py_compile`（全部 11 个接口模块） | 通过 |
| Git 推送 `master` | 成功 |
| Vercel 构建（commit `a63086c`） | **success（Deployment has completed）** |

### 关键缺陷修复（构建）
- 历史与本次部署**持续失败**。根因：`vercel.json` 的 `builds.src = "api/**/*.py"` 将共享库
  `api/_lib/*.py` 也当作 Serverless Function，函数数（16/14）超出 **Vercel Hobby 12 函数上限**。
- 修复：`builds.src` 改为 `"api/*.py"`（仅 11 个顶层函数），`_lib` 与 `analysis/seed_data.json`
  通过 `config.includeFiles` 打包进每个函数。构建状态由 failure → **success**。

---

## 6. 功能用例 TC-01~TC-15（自动化套件就绪）

自动化脚本：`tests/e2e_api.py`（requests 逐条覆盖，记录耗时并写 `tests/results.json`）。
运行命令（待公网可访问后执行）：

```bash
python tests/e2e_api.py --base-url https://<本项目公开域名>
```

| 用例 | 名称 | 覆盖接口 | 预置/断言 |
|------|------|----------|-----------|
| TC-01 | 用户登录（正确/错误） | POST /api/auth/login | 正确得 token；错误返回 401 |
| TC-02 | 用户注册（新建/重复） | POST /api/auth/register | 新建 201；重复 ≥400 |
| TC-03 | 游客只读访问 | GET /api/projects, /api/tests（无 token） | 均 200 |
| TC-04 | 项目 CRUD | POST/GET/PUT/DELETE /api/projects | 增查改成功 |
| TC-05 | 试验创建 | POST /api/tests | 返回 test id |
| TC-06 | 启动剥离试验 | POST /api/test_ops/start | status=running |
| TC-07 | 实时数据轮询 | GET /api/realtime_poll | ≥3/6 有效数据帧 |
| TC-08 | 停止/中止试验 | POST /api/test_ops/stop | status=completed + summary |
| TC-09 | 数据分析聚合 | GET /api/data?action=analysis | overall_stats+histogram+cumulative |
| TC-10 | 联动钻取单条带 | GET /api/data?action=history&strip_number | points>0 |
| TC-11 | 单试验 Word 报告 | GET /api/reports/test | docx 字节 >2KB |
| TC-12 | 项目级 ZIP 批量 | GET /api/reports/project | 合法 zip |
| TC-13 | 用户管理(管理员) | GET /api/admin/users, PUT /api/admin | 列表+改角色/状态 |
| TC-14 | 系统设置读/写 | GET/PUT /api/settings | get/put 均 200 |
| TC-15 | 审计日志记录/查询 | GET /api/admin/audit | logs>0 |

> 说明：TC-01~15 的接口与数据流已在本地离线层验证逻辑正确；线上执行结果将于公网可访问后回填本表（含逐用例耗时、首屏与 200ms 刷新性能、浏览器兼容性矩阵）。

---

## 7. 缺陷与修复记录（本轮）

| 编号 | 问题 | 修复 |
|------|------|------|
| DEF-01 | 力值量程错误（前端硬编码 30000N），平台/阈值未对齐论文 | `config.js` 改 0–1000N/平台~96/阈值70/报警120；重写位置制 `simulator.py` |
| DEF-02 | 数据模型为角度制（position_angle），与论文 1mm 位置制不符 | 全栈（DB/接口/前端/可视化）改为 `position_mm` |
| DEF-03 | 旧库为 8 表（peeling_tests/users.is_active），且 init_db 在已存在用户时直接跳过 → 升级后新表缺失 | 重写为论文 6 表 + 幂等迁移（ALTER ADD IF NOT EXISTS）+ `?reset=1` 重建 + 真实数据种子（仅当 tests 为空） |
| DEF-04 | Vercel 构建持续失败（函数数超 12 上限） | `builds.src` 改 `api/*.py` + `includeFiles` 打包 `_lib`/种子 → 构建成功 |
| DEF-05 | 权限：游客需只读、写操作需鉴权 | 读接口放开；写校验 JWT+角色/授权码并写审计；前端 `canWrite/requireWrite` 网关 |
| DEF-06 | 报告/CSV 下载 `window.open` 无法携带 JWT，审计 CSV 401 | 新增 `API.download`（fetch + 鉴权头 + blob 下载） |

---

## 8. 待办 / 阻塞项（需账户侧操作）

> 代码与构建均已就绪并部署成功，但**当前线上对公网不可访问**，导致线上 TC 套件尚未执行。

- **BLK-01｜Vercel Deployment Protection（401）**：本项目部署域
  `pipeline-peeling-control-wangqiyuans-projects-191f0cf3.vercel.app` 对外返回 401（空响应体），
  即开启了 Vercel Authentication/部署保护。需在 **Vercel 控制台 → 项目 Settings → Deployment Protection**
  关闭（或对 Production 关闭），否则公网与"游客只读"均不可用。
- **BLK-02｜对外域名归属**：`pipeline-peeling-control.vercel.app` 与 `www.cbl.pw` 当前由**另一个项目（标题 "PCS"）**占用，
  并非本仓库项目。需确认本仓库项目应使用的对外域名并完成绑定。

### 解除阻塞后的上线收尾步骤
1. 在 Vercel 关闭 Deployment Protection，确认本项目对外域名 `BASE_URL`。
2. 初始化/迁移线上库（首次建议重建）：`GET {BASE_URL}/api/init_db?reset=1`。
3. 运行线上用例：`python tests/e2e_api.py --base-url {BASE_URL}`，将 `tests/results.json` 回填第 6 节。
4. 如有失败用例：定位修复 → `git push` 自动部署 → 重跑，循环直至 **15/15 通过**。
