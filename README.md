# 管道防腐层剥离控制系统

Pipeline Anti-Corrosion Layer Peeling Control System

国家管网管道防腐层圆周剥离设备 Web 控制与管理平台。

## 技术栈

- **前端**: HTML / CSS / JavaScript + ECharts
- **API**: Python Flask Serverless Functions (Vercel)
- **数据库**: Neon PostgreSQL
- **部署**: Vercel

## 功能模块

- 实时监控大屏（30条剥离力实时监测）
- 试验控制面板
- 项目管理
- 数据分析（折线图、柱状图、饼图、分布图）
- 试验报告
- 用户与权限管理
- 系统设置与审计日志

## 环境变量

在 Vercel 中设置以下环境变量：

- `DATABASE_URL` - Neon PostgreSQL 连接字符串
- `JWT_SECRET` - JWT 签名密钥

## 部署

1. 推送代码至 GitHub
2. 在 Vercel 中导入项目
3. 设置环境变量
4. 部署完成后访问 `/api/init_db` 初始化数据库

## 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin  | admin | 管理员 |
| admin1 | admin1 | 管理员 |
| admin2 | admin2 | 管理员 |
| user1  | user1 | 普通用户 |
| test1  | test1 | 测试用户 |

授权码: `test12`（普通用户获取写入权限）
