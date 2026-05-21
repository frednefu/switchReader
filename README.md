# IPAM

企业 IP 地址管理系统（IP Address Management），通过 SNMP 自动采集交换机 ARP/FDB/路由表数据，Web 界面管理 IP 资源。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | FastAPI (Python 3.10+) |
| ORM | SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 / SQLite (开发) |
| SNMP | pysnmp 7.1+ (Slim API) |
| 前端 | Vue.js 3 + Element Plus + ECharts |
| 部署 | Docker Compose (MySQL + Redis + backend + frontend) |

## 功能

- **仪表盘** — 交换机/子网/IP/MAC 统计、地址段利用率图表、可用 IP 查询
- **交换机管理** — CRUD、SNMP 连接测试、按交换机配置扫描间隔
- **SNMP 扫描** — 自动识别 L2/L3 交换机，支持标准 MIB 和华为私有 MIB，数据合并
- **扫描结果** — 主机信息（IP/MAC/VLAN/端口）翻页列表、路由表翻页列表
- **地址段管理** — CRUD、IP 可用性计算
- **搜索** — IP 或 MAC 快速查找
- **用户认证** — JWT + bcrypt，admin/user 角色

## 快速开始

```bash
# 1. 启动全部服务
docker-compose up -d

# 2. 初始化种子数据
docker-compose exec backend python seed.py

# 3. 访问
# 前端: http://localhost
# API 文档: http://localhost:8000/docs
```

默认账号：`admin` / `Admin123!`、`viewer` / `Viewer123!`

### 本地开发

```bash
# 后端 (SQLite)
cd backend
cp .env.example .env  # 编辑 DATABASE_URL=sqlite:///./ipam.db
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 项目结构

```
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + lifespan
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database.py          # SQLAlchemy engine
│   │   ├── models/              # User, Switch, ScanResult, RouteTable, ScanLog, Subnet
│   │   ├── schemas/             # Pydantic 请求/响应
│   │   ├── api/                 # auth, switches, results, scan_logs, dashboard, subnets, search
│   │   ├── services/            # scanner_service, subnet_service
│   │   └── utils/               # security (JWT, bcrypt)
│   ├── seed.py                  # 默认用户初始化
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/               # Login, Dashboard, SwitchList, SwitchDetail, Results, Routes, SubnetManage, SearchResult
│   │   ├── components/          # AppLayout, SwitchFormDialog
│   │   ├── api/                 # Axios 封装
│   │   ├── store/               # Pinia auth
│   │   └── router/              # Vue Router
│   └── nginx.conf
└── switchReader/
    └── switchReader.py          # SNMP 采集引擎（Web 后端复用）
```

## API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 登录 |
| GET | /api/auth/me | 当前用户信息 |
| CRUD | /api/switches | 交换机管理 |
| POST | /api/switches/test | SNMP 连接测试 |
| POST | /api/switches/{id}/scan | 触发扫描 |
| GET | /api/results | 扫描结果（分页+过滤） |
| GET | /api/results/routes | 路由表（分页+过滤） |
| GET | /api/scan-logs | 扫描日志 |
| GET | /api/dashboard/stats | 仪表盘统计 |
| GET | /api/dashboard/subnet-utilization | 地址段利用率 |
| GET | /api/dashboard/available-ips | 可用 IP 列表 |
| CRUD | /api/subnets | 地址段管理 |
| GET | /api/search | IP/MAC 搜索 |

## 交换机配置

SNMP v2c，通过 Web 界面添加交换机（IP + community）。支持两种 MIB 模式：

- **标准 MIB** — IP-MIB + Q-BRIDGE-MIB + BRIDGE-MIB，适用于通用厂商
- **华为私有 MIB** — HUAWEI-L2MAM-MIB + HUAWEI-ARP-MIB，支持 BD 模式

Web 后端复用了 `switchReader/switchReader.py` 的所有 SNMP 采集函数，每次扫描创建独立的 pysnmp Slim 实例。

## 开发阶段

| 阶段 | 状态 |
|------|------|
| Phase 1: 项目脚手架 + Docker + 认证 | ✅ |
| Phase 2: 交换机管理 + SNMP 扫描 | ✅ |
| Phase 3: 仪表盘 + 地址段 + IP 搜索 | ✅ |
| Phase 4: 历史追踪（IP↔MAC 变更记录） | 🔜 |
| Phase 5: 定时任务 + 用户管理 + 个人中心 | 🔜 |
| Phase 6: 生产就绪 + 路由导入 | 🔜 |
