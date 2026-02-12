# chat2sql

基于 LangGraph 的 NL2SQL Agent，支持多轮对话、Schema 检索、多候选 SQL 生成与选优、校验执行。

后端项目结构基于 [FastScaff](https://github.com/lee-hangzhou/fastscaff) 脚手架生成。

## 技术栈

**后端:** FastAPI, LangGraph, LangChain, Tortoise ORM, Milvus, MySQL, Redis

**前端:** React, TypeScript, Vite, Tailwind CSS, Zustand

**可观测性:** Arize Phoenix (OpenTelemetry)

## Agent 流程

```
schema_retriever
  ↓
intent_parse
  ↓
  ├─ 意图不明确 → follow_up（挂起等待用户回复）→ 回到 intent_parse
  ↓
sql_generator
  ↓
sql_validator
  ↓
sql_selector
  ├─ 结果一致 ────────────────→ executor
  ├─ 结果不一致（首次）→ sql_generator（仲裁）→ 回到 sql_validator
  └─ 结果不一致（仲裁后）→ sql_judge → executor
                                         ↓
                                  result_summarizer
```

- **schema_retriever**: 基于 Milvus 向量检索匹配的表结构
- **intent_parse**: LLM 判断用户意图是否明确、Schema 是否充足
- **follow_up**: 意图不明确时挂起等待用户补充信息
- **sql_generator**: 并发生成多条候选 SQL
- **sql_validator**: 语法校验 + EXPLAIN 验证 + 性能分析
- **sql_selector**: 执行候选并比对结果集，多数投票选优；无多数时触发仲裁
- **sql_judge**: LLM 语义裁决，从结果不一致的候选中选择最优
- **executor**: 执行最终 SQL
- **result_summarizer**: LLM 根据用户问题和查询结果生成自然语言总结

## 项目结构

```
chat2sql/
├── app/                    # 后端
│   ├── main.py
│   ├── agent/              # NL2SQL Agent
│   │   ├── graph.py        # LangGraph 流程定义
│   │   ├── states.py       # 全局状态
│   │   ├── prompts.py      # Prompt 模板构建
│   │   └── nodes/          # 各节点实现
│   ├── api/v1/endpoints/   # API 接口
│   ├── core/               # 配置、数据库、安全、LLM、日志
│   ├── models/             # Tortoise ORM 模型
│   ├── schemas/            # Pydantic 模型
│   ├── repositories/       # 数据访问层
│   ├── services/           # 业务逻辑层
│   ├── middleware/         # JWT、日志、安全、Tracing 中间件
│   ├── utils/              # 公共工具（消息裁剪、计时等）
│   └── exceptions/         # 异常定义
├── web/                    # 前端（React）
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── requirements.txt
```

## 环境要求

- Python >= 3.12, < 3.14
- Node.js >= 20
- Docker & Docker Compose

## 运行方式

项目支持两种运行方式：

### 方式一：本地开发（推荐）

后端和前端在本地运行，MySQL、Redis、Milvus 通过 Docker 容器运行。

**1. 克隆项目并初始化**

```bash
git clone https://github.com/lee-hangzhou/chat2sql && cd chat2sql

# 创建 Python 虚拟环境
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 一键初始化（安装依赖 + 生成 .env）
make setup
```

首次启动会自动下载嵌入模型（BAAI/bge-large-zh-v1.5，约 1.3GB）

**2. 编辑配置**

打开 `.env`，以下两项**必须配置**，否则无法正常运行：

```bash
# [必填] LLM 配置 — 二选一

# 方式一：OpenAI 等云服务
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4o-mini

# 方式二：Ollama 等本地模型
# OPENAI_API_KEY=ollama
# OPENAI_BASE_URL=http://localhost:11434/v1
# OPENAI_MODEL=qwen3:8b

# [必填] 业务数据库 — 替换为你实际要查询的数据库地址
BUSINESS_DATABASE_URL=mysql://root:123456@localhost:3306/your_business_db
```

其他配置项均有合理默认值，参见 `.env.example`。生产环境务必修改 `JWT_SECRET_KEY`。

**3. 启动基础设施服务**

```bash
make services-up
```

该命令会通过 Docker Compose 启动 MySQL、Redis、Milvus（含 etcd、MinIO）、Phoenix。首次启动需要拉取镜像，耗时较长。

可通过 `docker compose ps` 确认所有服务状态为 healthy。

**4. 初始化数据库**

```bash
make db-init
```

该命令会根据 `.env` 中的 `DATABASE_URL` 自动创建应用数据库（如 `chat2sql`）。应用启动时会自动建表。

**5. 启动后端**

```bash
make dev
```

后端启动后会自动创建数据库表。API 文档：http://localhost:8000/docs

**6. 启动前端**

```bash
make fe-dev
```

前端默认运行在 http://localhost:3000 。

**7. 同步业务库表结构**

首次使用前，需要将业务数据库的表结构灌入 Milvus 向量库，Agent 才能检索到可用的表。可以通过前端界面点击「同步 Schema」按钮，或直接调用接口：

```bash
curl -X POST http://localhost:8000/api/v1/chat/schema/sync \
  -H "Authorization: Bearer <token>"
```

**8. 停止基础设施服务**

```bash
make services-down
```

### 方式二：Docker Compose 全栈部署

所有组件（应用、MySQL、Redis、Milvus）通过 Docker Compose 一键启动

**1. 准备配置**

```bash
cp .env.example .env
```

编辑 `.env`，**必须配置**以下内容：

```bash
# [必填] LLM 配置
# 使用 Ollama 本地模型时，Docker 内 localhost 不可达宿主机，需使用 host.docker.internal
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen3:8b
OPENAI_BASE_URL=http://host.docker.internal:11434/v1

# [必填] 业务数据库
# Docker 内使用服务名 mysql 而非 localhost，密码与 MYSQL_ROOT_PASSWORD 一致
BUSINESS_DATABASE_URL=mysql://root:chat2sql@mysql:3306/your_business_db
```

**2. 构建并启动**

```bash
make docker-build
make docker-up
```

应用运行在 http://localhost:8000 ，前端已内嵌在后端中。

首次构建需要下载基础镜像和安装依赖，耗时较长。

**3. 查看日志**

```bash
make docker-logs
```

**4. 停止**

```bash
make docker-down
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `make help` | 查看所有可用命令 |
| `make setup` | 首次初始化（安装依赖 + 生成 .env） |
| `make db-init` | 创建应用数据库 |
| `make services-up` | 启动基础设施服务 |
| `make services-down` | 停止基础设施服务 |
| `make dev` | 启动后端开发服务器 |
| `make fe-dev` | 启动前端开发服务器 |
| `make fe-build` | 构建前端生产包 |
| `make lint` | 代码检查 |
| `make format` | 代码格式化 |
| `make test` | 运行测试 |

## API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 可观测性

Phoenix 随基础设施服务一起启动，自动采集 LLM 调用和 Agent 执行链路。

- Phoenix UI: http://localhost:6006

## License

MIT
