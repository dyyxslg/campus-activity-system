# 校园社团活动报名与智能数据分析后端系统

基于 **FastAPI + MySQL + Redis + Celery/RabbitMQ + 大模型 AI** 的校园社团活动报名后端，面向真实使用场景设计：学生报名、管理员运营、大数据量报表导出、活动状态自动流转、AI 运营复盘，一套系统全链路跑通。

> 工程上重点解决三类真实痛点：
> **并发抢报超报**（Redis 分布式锁）、**大数据量导出 HTTP 超时**（Celery 异步 + 流式写盘）、**AI 能力可选**（开关可控，不成为系统硬依赖）。

---

## 一、技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| Web 框架 | FastAPI + Pydantic v2 | REST API、请求/响应校验、自动 OpenAPI 文档 |
| ORM / 数据库 | SQLAlchemy 2.0 + MySQL 8.0 | 关系模型、`isolation_level=READ_COMMITTED` |
| 缓存 / 锁 | Redis | 分布式锁防超报、报名数缓存、限流、任务进度缓存 |
| 异步任务 | Celery + RabbitMQ | 报表导出 / AI 分析 / 定时任务，规避 HTTP 超时 |
| 定时调度 | Celery-Beat | 活动状态自动流转、过期报表清理 |
| 鉴权 | JWT (python-jose) + bcrypt | 学生/管理员双角色 |
| AI | Deepseek API（OpenAI 兼容，可开关） | 报名数据运营分析，失败自动降级 |
| 部署 | Docker Compose + Dockerfile | 一键多服务编排（MySQL/Redis/RabbitMQ/API/Worker/Beat） |

---

## 二、核心特性

### 1. 活动全生命周期状态机
`DRAFT → OPEN → CLOSED → FINISHED`，状态转移白名单校验（`app/services/activity_service.py` 中 `ACTIVITY_TRANSITIONS`），不允许非法跳转；Celery-Beat 每分钟自动执行基于时间的流转（到报名截止自动 CLOSED、到活动结束自动 FINISHED）。

### 2. 并发报名防超报（分布式锁）
抢报场景下，同一活动大量学生同时报名。系统用 **Redis 分布式锁** 串行化「查人数 → 判断是否已满 → 写报名」关键区：

- `SET key token NX EX` 加锁 + **Lua 脚本原子释放**（防误删他人锁）；
- 自旋重试，获取失败超时即拒（名额已满）；
- 报名数写 Redis 缓存并带 TTL，缓存失效自动回源 DB 兜底；
- 底层将 MySQL 连接设为 `READ_COMMITTED`，**解决 REPEATABLE READ 快照导致锁内读到旧数据的问题**。

**效果**：并发 50 抢 30 名额 → 加锁模式严格 30 人（零超报）；去掉锁 + 人为放大查询间隙 → 稳定复现超报（33 人），对照组证明锁的必要性。

### 3. 异步报表导出（规避 HTTP 超时）
大活动几万行报名记录，同步生成 CSV 会触发网关超时。方案：

- 提交接口立即返回 `202 + task_id`，Celery worker 后台执行；
- **主键游标分页**（`id > last_id`，每批 2000 行）代替 OFFSET 深翻页，内存恒定；
- 流式写临时文件 → 全部完成后 `os.replace` **原子改名**对外可见；
- 单条脏数据逐行容错：跳过并计数，最终状态 `PARTIAL_FAIL`（部分失败）而非整体失败；
- 进度实时写入 Redis，前端秒级轮询到真实百分比。

### 4. 任务进度实时查询
`Redis JSON 快路径 + DB 兜底`：进度优先读缓存（毫秒级），缓存缺失自动回表。

### 5. AI 数据分析（可一键关闭）
对活动报名行为数据（报名量/取消率/容量利用率/按小时与按天分布/高峰时段）调用 Deepseek 产出运营复盘与改进建议：

- **`AI_ENABLE=false` 时提交接口直接 400 拒绝，任务体内二次校验兜底**，主系统完全不受影响；
- 大模型调用失败自动**降级为规则化摘要**，任务仍正常落库，AI 不是硬依赖；
- 分析结果独立落表 `ai_analysis`，支持历史结果查询。

### 6. 接口限流
Redis 固定窗口计数（`INCR + EXPIRE`），对注册/登录接口限流；Redis 故障时**自动降级放行**，不拖垮鉴权。

### 7. 定时任务（Celery-Beat）
- 每分钟：活动状态自动流转；
- 每日 03:17：清理过期 CSV 报表文件与历史任务记录（避免磁盘占满），时间错开整点。

---

## 三、系统架构

```
                        ┌─────────────────────────────────────────────┐
                        │                客户端（学生 / 管理员）          │
                        └──────────────────────┬──────────────────────┘
                                               │ HTTPS/JSON
                        ┌──────────────────────▼──────────────────────┐
                        │               FastAPI 应用层                 │
                        │  JWT 鉴权 → 限流 → 路由 → 服务层              │
                        │  活动CRUD / 报名业务 / 报表/AI 提交           │
                        └───┬───────────┬───────────┬─────────────────┘
                            │           │           │
                 ┌──────────▼──┐  ┌─────▼────┐  ┌───▼─────────────┐
                 │   MySQL 8   │  │  Redis   │  │   RabbitMQ       │
                 │  业务持久化  │  │ 锁/缓存/ │  │  任务队列         │
                 │ READ_COMMITTED│ │ 限流/进度│  └───┬─────────────┘
                 └─────────────┘  └──────────┘      │
                                                    │
                              ┌─────────────────────▼──────────────────┐
                              │   Celery Worker（报表/清理/状态/AI）     │
                              │   └ Celery-Beat（定时调度）             │
                              └───────────────────────────────────────┘
```

### 目录结构

```
xm2/
├── app/
│   ├── main.py                 # FastAPI 入口（/health、路由注册）
│   ├── api/
│   │   ├── deps.py             # 依赖注入：鉴权、限流、get_db
│   │   └── v1/                 # auth / activities / registrations / tasks
│   ├── core/
│   │   ├── config.py           # pydantic-settings 配置中心
│   │   ├── security.py         # bcrypt 哈希 + JWT 签发/校验
│   │   └── redis.py            # Redis 客户端 + 分布式锁（Lua 原子释放）
│   ├── db/
│   │   ├── base.py             # DeclarativeBase
│   │   └── session.py          # 引擎（READ_COMMITTED）、会话、建表
│   ├── models/                 # user/activity/registration/task_record/ai_analysis/enums
│   ├── schemas/                # Pydantic 请求响应模型
│   ├── services/               # 活动、报名（分布式锁核心）、任务、AI 统计
│   └── tasks/                  # Celery：celery_app / report / scheduled / ai_analysis
├── scripts/
│   └── create_admin.py         # 创建管理员账号
├── tests/
│   ├── concurrency_signup.py   # 并发抢报测试（加锁 PASS / 不加锁复现超报）
│   └── seed_data.py            # 批量造数（万级报名，带晚间高峰分布）
├── docker-compose.yml          # MySQL/Redis/RabbitMQ/API/Worker/Beat
├── Dockerfile
├── .env.example                # 配置模板（容器内网互联）
└── requirements.txt
```

---

## 四、快速开始

### 方式 A：Docker Compose 一键部署（推荐，模拟生产）

```bash
# 1. 准备配置
cp .env.example .env          # 容器内使用 mysql/redis/rabbitmq 主机名，无需修改

# 2. 启动全部服务
docker compose up -d --build

# 3. 等依赖健康后创建管理员
docker compose exec api python scripts/create_admin.py \
    --username admin --password admin123456 --nickname 管理员

# 4. 访问
# API 文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health
```

> 注意：本地已占用 3306 端口时，compose 将 MySQL 映射为宿主机 **3307**（见 `MYSQL_PORT` 说明）。

### 方式 B：本地虚拟环境开发

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
# Windows:  .venv\Scripts\activate        Linux/macOS: source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 准备 .env（本地开发，host 用 127.0.0.1）
cp .env.example .env
#    修改: MYSQL_HOST=127.0.0.1  MYSQL_PORT=3307  REDIS_URL=redis://127.0.0.1:6379/0
#          RABBITMQ_URL=amqp://127.0.0.1:5672//  REPORT_DIR=./reports

# 4. 启动依赖中间件（MySQL 8 / Redis / RabbitMQ，可用 docker compose up -d mysql redis rabbitmq 或本地服务）

# 5. 启动 API
uvicorn app.main:app --reload --port 8000

# 6. 启动 Celery（Windows 需 --pool=threads）
celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=threads
celery -A app.tasks.celery_app.celery_app beat --loglevel=info

# 7. 创建管理员
python scripts/create_admin.py --username admin --password admin123456
```

> 首次启动自动建表（`create_tables`，生产环境建议改用 Alembic 迁移）。

---

## 五、API 一览

前缀 `/api/v1`，完整交互文档见 `/docs`。

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | /auth/register | 公开（限流） | 学生注册 |
| POST | /auth/login | 公开（限流） | 登录，返回 JWT |
| GET | /auth/me | 登录 | 当前用户信息 |
| POST | /activities | 管理员 | 创建活动（DRAFT） |
| GET | /activities | 登录 | 活动列表（学生不可见 DRAFT） |
| GET | /activities/{id} | 登录 | 活动详情（含已报名数） |
| PUT | /activities/{id} | 管理员 | 编辑活动 |
| POST | /activities/{id}/status | 管理员 | 手动状态流转（白名单校验） |
| DELETE | /activities/{id} | 管理员 | 删除活动 |
| POST | /registrations/{activity_id} | 学生 | 报名（分布式锁防超报） |
| DELETE | /registrations/{activity_id} | 学生 | 取消报名 |
| GET | /registrations/my | 学生 | 我的报名 |
| GET | /registrations/{activity_id}/status | 学生 | 我在某活动报名状态 |
| GET | /registrations/activity/{activity_id} | 管理员 | 某活动报名名单 |
| POST | /tasks/reports/{activity_id} | 管理员 | 提交报表导出（202 异步） |
| GET | /tasks/reports/{record_id}/progress | 管理员 | 任务进度（Redis 快路径） |
| GET | /tasks/reports/{record_id}/download | 管理员 | 下载 CSV 报表 |
| GET | /tasks/reports | 管理员 | 我的报表任务列表 |
| POST | /tasks/ai/{activity_id} | 管理员 | 提交 AI 分析（AI_ENABLE=false 时 400） |
| GET | /tasks/ai/{activity_id}/result | 管理员 | 查询最新 AI 分析结果 |

---

## 六、测试脚本

```bash
# 1. 并发报名测试：验证分布式锁防超报
python tests/concurrency_signup.py --capacity 30 --users 50            # 加锁：最终严格 30 人
python tests/concurrency_signup.py --capacity 30 --users 50 --no-lock  # 不加锁：复现超报

# 2. 批量造数据：为大数据量报表/AI 分析准备数据
python tests/seed_data.py                          # 默认大活动 5000 报名
python tests/seed_data.py --signups 20000 --capacity 30000   # 压力测试 2 万+报名
python tests/seed_data.py --quick                  # 小批量快速验证
python tests/seed_data.py --clean                  # 清理全部种子数据
```

---

## 七、部署与生产建议

- **安全**：上线前必须修改 `.env` 中 `SECRET_KEY`，使用强随机值；数据库/Redis/RabbitMQ 设置独立强密码。
- **迁移**：当前在 `app.main` 启动时自动建表，适合演示；生产建议接入 **Alembic** 做版本化迁移。
- **Worker 池**：Linux 容器默认 prefork；Windows 本地运行 Celery 必须加 `--pool=threads`。
- **报表保留**：`REPORT_RETENTION_DAYS`（默认 7 天）控制 CSV 与任务记录保留期，Celery-Beat 每日自动清理。
- **AI 密钥**：`AI_ENABLE=true` 后配置 `DEEPSEEK_API_KEY`；调用失败自动降级，不影响主流程。
- **限流**：`RATE_LIMIT_PER_SECOND` 按接口独立计数，Redis 故障自动放行。
- **监控**：生产建议叠加日志采集（如 Loki）、指标（Prometheus + /metrics）、进程守护（systemd / 容器健康检查已内置）。

### 常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| MySQL 3306 被本地占用 | compose 已映射为宿主 3307，`.env` 同步改 `MYSQL_PORT=3307` |
| 并发报名仍超报 | 检查引擎是否 `isolation_level=READ_COMMITTED`；锁未开启或 TTL 过短 |
| worker 报 `unregistered task` | worker 启动早于任务模块存在 → 重启 worker（`include` 已配置全部任务） |
| Windows 下 Celery 无法启动 | 必须 `--pool=threads`（默认 prefork 在 Windows 不可用） |
| 报表下载 404 | 已过保留期被清理，或任务未完成 |
| AI 提交 400 | `AI_ENABLE=false`，去 `.env` 打开并重启 API |

---

## 八、简历与面试材料

### 项目一句话介绍
> 基于 FastAPI + Redis + Celery 的校园社团活动报名与智能数据分析后端，覆盖报名抢报防超报、异步大数据量报表导出、AI 运营复盘与定时自动化运维。

### 项目描述（简历用）

**校园社团活动报名与智能数据分析后端系统** | FastAPI · SQLAlchemy · MySQL · Redis · Celery · RabbitMQ · Docker

- 设计并实现活动全生命周期状态机（DRAFT→OPEN→CLOSED→FINISHED），白名单校验非法流转，Celery-Beat 每分钟按时间自动流转、每日定时清理过期报表。
- 解决并发抢报超报：用 **Redis 分布式锁**（SET NX EX + Lua 原子释放 + 自旋重试）串行化「查数-判断-写入」，并将 MySQL 设为 `READ_COMMITTED` 消除 REPEATABLE READ 快照读到旧数据的问题；并发 50 抢 30 名额严格 30 人，对照组稳定复现超报证明方案有效性。
- 规避导出超时：提交接口返回 202 异步执行，worker 内**主键游标分页**（每批 2000 行）+ 流式写盘 + 原子改名，逐行容错支持部分失败；进度实时写 Redis 供前端轮询。
- 集成 Deepseek 大模型对报名数据做运营分析（取消率、容量利用率、时段分布、高峰发现），**开关可控（AI_ENABLE）**，调用失败自动降级为规则摘要，AI 不成为系统硬依赖。
- 基于角色（学生/管理员）的 JWT 鉴权、Redis 固定窗口限流（故障自动降级）、Docker Compose 多服务编排部署。

### 面试口头表达（开场 60 秒版）

> 我做的是一个校园社团活动报名后端，面向真实场景。除了常规的报名、取消、活动管理之外，我重点处理了三个工程难点。
>
> 第一是**并发抢报防超报**。同学们同时抢名额，最直接的做法是"先查人数再判断是否已满再插入"，但并发下会有竞态。我用了 Redis 分布式锁把这段关键区串起来：SET NX EX 加锁、Lua 脚本原子释放、自旋重试。而且这里我踩过一个很深的坑——就算有锁，MySQL 默认的 REPEATABLE READ 隔离级别会在事务开始时建立快照，锁内重新查询还是旧数据，照样超报。我把引擎切到 READ_COMMITTED 才真正解决。我用 50 个线程抢 30 个名额做了对照实验：加锁严格 30 人，去掉锁稳定超报到 33 人，证明锁是真实有效的。
>
> 第二是**大数据量导出不超时**。几万条报名记录如果同步生成 CSV，HTTP 早就超时了。我的做法是提交接口立刻返回任务 ID，Celery worker 在后台分页拉取，用主键游标而不是 OFFSET 深翻页，流式写临时文件，全部写完再原子改名。单条脏数据也不会拖垮整个任务，最终状态是部分失败。进度实时写 Redis，前端能秒级看到百分比。
>
> 第三是**AI 能力可选**。我接了大模型对报名数据做运营分析，比如取消率、报名高峰时段。但大模型调用可能失败、也可能密钥没配，所以系统里 AI 有独立开关，关了主流程完全不受影响，调用失败会降级成规则摘要，保证任务一定能落库。
>
> 整个项目用 Docker Compose 编排 MySQL、Redis、RabbitMQ 和 API、Worker、Beat 六个服务，本地和容器两套环境都验证过全链路。

### 可能追问与回答要点

- **为什么用分布式锁而不是数据库唯一约束 / 乐观锁？** 唯一约束只能保证同一用户不重复报名，防不了"超过名额上限"；这里名额上限是聚合判断，需要把"查-判-写"变成原子操作。乐观锁对高频抢报冲突多、重试成本高。
- **锁过期了怎么办？** 当前用固定 TTL + 任务内短事务兜底，业务操作毫秒级完成远小于 TTL；生产可再叠加"锁续期 watchdog"或 value 校验删除。
- **为什么报表不用 OFFSET 分页？** 深翻页要扫描并丢弃前 N 行，随页码增长性能恶化；主键游标只取 `id > 上一批最大 id`，每次都是索引范围扫描，内存恒定。
- **AI_ENABLE 关闭时系统能否完整使用？** 能。AI 只影响 /tasks/ai 两个接口（提交直接 400），报名、活动、报表、定时任务全部独立可用，任务体内还有二次校验兜底。
- **Celery 在 Windows 上怎么跑？** 默认 prefork 池依赖 fork，Windows 不支持，需 `--pool=threads`；Linux 容器里用默认池。

---

## 九、测试结果汇总（开发验证记录）

| 模块 | 验证内容 | 结果 |
|---|---|---|
| 鉴权/限流 | 注册/登录/me/401；并发限流 | 通过（18×200 + 2×429） |
| 活动 | 10 项 CRUD + 状态机白名单 | 通过 |
| 报名/锁 | 并发 50 抢 30（加锁） | 严格 30 人，零超报 PASS |
| 报名/无锁对照 | 加 race-delay 放大竞态 | 33 人超报复现 |
| 报表导出 | 12 万行内多次导出行数精确一致 | 通过（22,400 行 CSV 端到端 PASS） |
| 定时任务 | beat 每分钟触发、状态流转、过期清理 | 通过（21:26/21:27 tick 正常执行） |
| AI 分析 | 关闭→400；开启→SUCCESS 落库 | 通过 |

> 完整工程细节见各模块代码注释；测试脚本均位于 `tests/`，可直接复跑。
