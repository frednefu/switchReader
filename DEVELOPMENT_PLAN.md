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

> **已提交** `ffb403f` → `b4d4770`（含适配修复）

- 移除 SQLite 特定代码（WAL PRAGMA、check_same_thread、connect 事件监听）
- 迁移函数改用 SQLAlchemy inspect（兼容 MySQL + SQLite）
- MySQL utf8mb4 字符集配置
- 创建 `.env.example` 模板
- 修复 `vm_inventory` 表索引键过长问题（String(1024) → String(255)，MySQL utf8mb4 索引限制 3072 字节）
- 本地开发模式：`docker-compose.local.yml`（仅 MySQL + Redis 容器，前后端本地运行）

---

### Phase B: Celery + Redis 扫描异步化 ✅

> **已提交** `147873e`

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

### Phase C: 扫描步骤日志 + 实时监控面板 ✅

> **已提交** `f172f61`

> **解决核心问题：无法直观查看扫描进度和数据获取过程**

**数据库改动：**

- `scan_logs` 表新增 `progress_pct`、`current_step`、`log_output`、`worker_id` 字段
- 新增 `scan_steps` 表：`scan_log_id`、`step_order`、`step_name`、`status`、`items_total`、`items_processed`、`error_message`

**后端核心文件：**

| 文件 | 内容 |
|------|------|
| `backend/app/services/scan_step_service.py` | 统一扫描步骤追踪服务：`mark_queued()`/`mark_started()`/`update_progress()`/`append_log()`/`add_step()`/`finish_step()` |
| `backend/app/models/scan_log.py` | ScanLog 扩展字段 + ScanStep 模型（独立 DB 会话） |
| `backend/app/api/scan_logs.py` | `GET /{id}/steps`、`GET /{id}/output`、`DELETE /{id}`、批量清除支持 `status` 过滤 |
| 6 个 scanner_service | 增强日志输出（VM 分布/OS 统计/Pool 状态/记录类型/内外网分布）和细粒度进度更新（7-10 节点） |
| 修复各扫描器 `scan_log` 始终 `success` | 新增 `scan_successful` 标志，异常路径正确标记 `failed` |

**前端核心文件：**

| 文件 | 内容 |
|------|------|
| `frontend/src/views/ScanMonitor.vue` | 实时任务监控面板：进度卡片 + 展开步骤列表 + 终端输出 + 取消/删除/全部清除 |
| `frontend/src/api/scanLogs.js` | 新增 `deleteScanLog`、`clearScanLogs(status)` |
| `frontend/src/router/index.js` | 新增 `/scan-monitor` 路由 |

**已实现功能：**
- 6 类数据源扫描进度卡片实时展示（进度条 + 当前步骤 + 已用时间）
- 点击展开：分步详情（步骤状态 + 成功/失败计数）+ 终端实时输出
- 2 秒自动轮询刷新 + 手动刷新 + 运行中任务计数
- 按数据源/状态筛选，单条删除 + 一键清除全部失败记录
- 扫描器终端输出包含丰富统计信息（采集数量/分布/明细快照）

---

### Phase D: WebSocket 进度推送

> **将 ScanMonitor 的 2 秒轮询替换为 WebSocket 实时推送，消除延迟和无效请求**

**现状：** ScanMonitor.vue 已完整实现，目前通过 `setInterval(fetchAll, 2000)` 轮询 `/api/scan-logs` 获取进度。

**改造目标：**

```
当前：前端 ──每2秒──► GET /api/scan-logs ──► 返回全量列表
改造：前端 ──WebSocket──► /ws/scan-progress ──► 仅推送变化的任务
```

**后端改动：**

| 文件 | 内容 |
|------|------|
| `backend/app/api/ws.py` | WebSocket 端点 `/ws/scan-progress`：认证 JWT token，订阅 Redis channel |
| `backend/app/services/progress_broker.py` | Redis Pub-Sub 发布/订阅：`scan_step_service` 更新进度时发布消息到 `channel:scan:{scan_log_id}` |

**前端改动：**

| 文件 | 内容 |
|------|------|
| `frontend/src/views/ScanMonitor.vue` | 替换 `setInterval` 轮询为 WebSocket 连接，接收增量更新并合并到 items 列表 |
| `frontend/src/api/ws.js` | WebSocket 封装：自动重连、心跳保活、JWT 鉴权 |

**消息格式（JSON）：**

```json
{"id": 42, "status": "running", "progress_pct": 65, "current_step": "ARP采集完成",
 "hosts_found": 320, "duration_seconds": 8.3, "steps": [...], "log_output_tail": "..."}
```

**优势：**
- 进度更新零延迟（Worker 写 DB → 发布 Redis → WebSocket 推前端，<100ms）
- 减少 HTTP 请求（从每 2 秒 1 次变成 0 次轮询）
- 支持多客户端同时监控（每个浏览器连接独立 WebSocket）
- 保留短轮询作为 fallback（WebSocket 断开时自动降级）

**Redis Pub-Sub Channel 设计：**

```
channel:scan:{scan_log_id}    — 单个任务进度更新
channel:scan:list              — 任务列表变更（新增/完成）
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
| Phase B: Celery + Redis 异步化 | ✅ 已完成 | `147873e` |
| Phase C: 扫描步骤日志 + 监控面板 | ✅ 已完成 | `f172f61` |
| Phase D: WebSocket 进度推送 | ✅ 已完成 | `716a6c0` |
| Phase E: Worker 容器化 | 🔲 下一步 | — |
| Phase F: Worker 管理面板 | 🔲 待开发 | — |
| Phase G: Redis 缓存 | 🔲 待开发 | — |
| Phase H: 远程部署 | 🔲 远期规划 | — |
