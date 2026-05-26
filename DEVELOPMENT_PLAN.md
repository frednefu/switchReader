# OmniView 开发计划

## 架构目标

分布式扫描平台，支持多 Worker 节点并行执行，前端实时监控扫描进度。

```
核心节点 (API + Web + DB + Cache)

Frontend ──► FastAPI ──► MySQL 8.0
(Nginx)       /api         (业务数据)
               │
               ├──► Redis ── 任务队列 (Celery broker)
               │            扫描日志缓存 (实时进度)
               │            资产画像缓存
               │
               └──► WebSocket ──► 前端实时进度推送
        │
        │ Redis 队列分发
        ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Worker 1 (Docker)│  │ Worker 2 (Docker)│  │ Worker N (Docker)│
│ 能力：全部数据源   │  │ 能力：全部数据源   │  │ 能力：全部数据源   │
│ 注册内容：        │  │ 注册内容：        │  │ 注册内容：        │
│  · SNMP 交换机   │  │  · SNMP 交换机   │  │  · F5            │
│  · vCenter       │  │  · ZDNS          │  │  · QAX           │
│  · F5            │  │  · QAX           │  │  · vCenter       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Worker 注册与任务分发

- Worker 同构 Docker 镜像，所有扫描能力内置，启动时声明扫描内容
- 相同内容可分配多个 Worker 实例，实现多实例并行
- 5 个 Redis 队列按数据源分类：`queue:scan:snmp` / `vcenter` / `f5` / `zdns` / `qax`
- 安全认证：Worker Token + IP 白名单

---

## 实施阶段

### Phase A: MySQL 数据库切换 ✅

> **已提交** `ffb403f`

- 移除 SQLite 特定代码（WAL PRAGMA、check_same_thread、connect 事件监听）
- 迁移函数改用 SQLAlchemy inspect（兼容 MySQL）
- MySQL utf8mb4 字符集配置
- 创建 `.env.example` 模板

---

### Phase B: Celery + Redis 扫描异步化

> **解决核心问题：发起扫描时前台响应慢**

**后端改动：**

| 文件 | 内容 |
|------|------|
| `backend/app/config.py` | 新增 `redis_url` 配置（已有）|
| `backend/requirements.txt` | 添加 `celery[redis]` |
| `backend/app/tasks/__init__.py` | Celery app 实例化 |
| `backend/app/tasks/scan_tasks.py` | 5 个 Celery task：`scan_switch` / `scan_vcenter` / `scan_f5` / `scan_zdns` / `scan_qax` |
| `backend/app/api/switches.py` | `POST /scan` 改为 `push_task_to_queue` → 立即返回 |
| `backend/app/api/vcenters.py` | 同上 |
| `backend/app/api/f5.py` | 同上 |
| `backend/app/api/zdns.py` | 同上 |
| `backend/app/api/qax.py` | 同上 |
| `backend/app/services/scheduler_service.py` | APScheduler job 改为 push 任务到队列，不再直接执行 |

**流程变更：**

```
改造前：POST /scan → 创建 ScanLog → 等待扫描初始化 → 返回 (阻塞10s+)
改造后：POST /scan → 创建 ScanLog → push Redis 队列 → 立即返回 202 (100ms)
        Worker 从队列取任务 → 执行扫描 → 更新 ScanLog
```

**Redis 职责：**

| 用途 | 数据结构 | 说明 |
|------|---------|------|
| 任务队列 | List (BRPOP) | 5 个队列，按数据源分 |
| 扫描进度 | Pub-Sub | Worker → API → WebSocket → 前端 |
| 资产画像缓存 | String (JSON) | 5 分钟 TTL |
| 仪表盘统计缓存 | String (JSON) | 30 秒 TTL |

---

### Phase C: 扫描步骤日志

> **解决核心问题：无法直观查看扫描进度和数据获取过程**

**数据库新增表：**

```sql
CREATE TABLE scan_steps (
    id INT PRIMARY KEY AUTO_INCREMENT,
    scan_log_id INT NOT NULL,
    step_order INT NOT NULL,
    step_name VARCHAR(128),           -- "ARP 表采集"、"FDB 采集"等
    status ENUM('pending','running','success','failed'),
    items_total INT DEFAULT 0,
    items_processed INT DEFAULT 0,
    started_at DATETIME,
    completed_at DATETIME,
    error_message TEXT,
    FOREIGN KEY (scan_log_id) REFERENCES scan_logs(id) ON DELETE CASCADE
);
```

**scan_logs 表补充字段：**

```sql
ALTER TABLE scan_logs ADD COLUMN progress_pct INT DEFAULT 0;
ALTER TABLE scan_logs ADD COLUMN current_step VARCHAR(128);
ALTER TABLE scan_logs ADD COLUMN worker_id INT;
```

**后端改动：**

| 文件 | 内容 |
|------|------|
| `backend/app/models/scan_log.py` | 新增字段 + ScanStep 模型 |
| `backend/app/schemas/scan_log.py` | 新增 Step 响应 Schema |
| `backend/app/api/scan_logs.py` | `GET /scan-logs/{id}/steps` 端点 |
| 各 scanner_service | 在每个采集步骤插入 ScanStep 并更新 progress_pct |

---

### Phase D: WebSocket 扫描进度推送

> **前端实时查看扫描进度**

**后端改动：**

| 文件 | 内容 |
|------|------|
| `backend/app/api/ws.py` | WebSocket 端点 `/ws/scan-progress` |
| `backend/app/services/progress_broker.py` | Redis Pub-Sub 订阅 → WebSocket 推送 |

**前端改动：**

| 文件 | 内容 |
|------|------|
| `frontend/src/views/ScanMonitor.vue` | 新建扫描监控页：所有扫描任务实时进度列表 |
| `frontend/src/components/ScanProgressBar.vue` | 可复用进度条组件（含步骤明细） |
| `frontend/src/router/` | 添加路由 `/scan-monitor` |
| `frontend/src/api/` | WebSocket 连接管理 |

**页面设计：**

```
┌─ 扫描监控 ──────────────────────────────────────────────┐
│  [数据源筛选] [状态筛选]                    自动刷新: 2s │
│  ─────────────────────────────────────────────────────── │
│  交换机   switch-1  运行中  ████████░░ 80%  12s          │
│           └─ ARP 采集        已完成  200/200             │
│           └─ FDB 采集        运行中  150/230             │
│           └─ 路由表          等待中                      │
│  交换机   switch-2  运行中  ████░░░░░░ 40%  28s          │
│  vCenter  vc-1      排队中                              │
│  F5       f5-1      成功    ██████████ 100% 45s          │
│  ZDNS     zdns-1    失败    — 连接超时                   │
│  [全部暂停] [重试失败]                                   │
└─────────────────────────────────────────────────────────┘
```

---

### Phase E: Worker 容器化 + 注册认证

**新增表：**

```sql
CREATE TABLE scan_workers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    worker_name VARCHAR(64) UNIQUE,
    token_hash VARCHAR(128),
    ip_address VARCHAR(45),
    status ENUM('online','offline','busy'),
    capabilities JSON,
    current_tasks INT DEFAULT 0,
    max_tasks INT DEFAULT 4,
    last_heartbeat DATETIME,
    registered_at DATETIME,
    version VARCHAR(32)
);
```

**后端改动：**

| 文件 | 内容 |
|------|------|
| `backend/app/models/scan_worker.py` | Worker 模型 |
| `backend/app/api/workers.py` | Worker 注册/心跳/注销 API |
| `backend/app/middleware/worker_auth.py` | Worker Token 验证中间件 |

**Docker 相关：**

| 文件 | 内容 |
|------|------|
| `docker-compose.worker.yml` | Worker 独立部署模板 |
| `backend/Dockerfile.worker` | Worker 镜像（Celery Worker + 全部扫描能力） |

**Worker 安全认证：**

```
Worker 启动 → 携带 TOKEN 向 API 注册
API 验证 TOKEN + IP 白名单 → 返回 Worker ID
后续通信 Header: Authorization: Bearer <worker-token>
```

---

### Phase F: Worker 管理面板

**前端改动：**

| 文件 | 内容 |
|------|------|
| `frontend/src/views/WorkerManage.vue` | Worker 节点列表：在线状态/当前任务/并发数/启禁用 |
| `frontend/src/api/workers.js` | Worker API 封装 |

---

### Phase G: Redis 缓存优化

- 资产画像关联计算缓存（5 分钟 TTL）
- 仪表盘统计缓存（30 秒 TTL）
- 后端改动集中在 `asset_profile_service.py` 和 `dashboard.py`

---

### Phase H: 远程部署 Worker（远期）

- API 通过 SSH 连接目标服务器，执行 `docker compose up -d`
- 或对接 Docker Remote API / Portainer
- 前端可直接部署扫描引擎 Docker 到指定服务器

---

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + SQLAlchemy 2.0 + Celery |
| 数据库 | MySQL 8.0 |
| 缓存/队列 | Redis 7 |
| 实时推送 | WebSocket + Redis Pub-Sub |
| 前端 | Vue 3 + Element Plus + ECharts |
| 部署 | Docker Compose |

## 当前进度

| 阶段 | 状态 | 提交 |
|------|------|------|
| Phase A: MySQL 切换 | ✅ 已完成 | `ffb403f` |
| Phase B: Celery + Redis 异步化 | 🔲 下一步 | — |
| Phase C: 扫描步骤日志 | 🔲 待开发 | — |
| Phase D: WebSocket 进度推送 | 🔲 待开发 | — |
| Phase E: Worker 容器化 | 🔲 待开发 | — |
| Phase F: Worker 管理面板 | 🔲 待开发 | — |
| Phase G: Redis 缓存 | 🔲 待开发 | — |
| Phase H: 远程部署 | 🔲 远期规划 | — |
