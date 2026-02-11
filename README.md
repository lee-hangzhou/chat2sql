# chat2sql

基于 LangGraph 的 NL2SQL Agent，支持多轮对话、Schema 检索、SQL 生成与校验执行。

## 技术栈

**后端:** FastAPI, LangGraph, Tortoise ORM, LangChain, Milvus, MySQL, Redis

**前端:** React, TypeScript, Vite, Tailwind CSS, Zustand

## 项目结构

```
chat2sql/
├── app/                    # 后端
│   ├── main.py
│   ├── agent/              # NL2SQL Agent（nodes / graph / states / prompts）
│   ├── api/v1/endpoints/   # API 接口
│   ├── core/               # 配置、数据库、安全、LLM、日志
│   ├── models/             # Tortoise ORM 模型
│   ├── schemas/            # Pydantic 模型
│   ├── repositories/       # 数据访问层
│   ├── services/           # 业务逻辑层
│   ├── middleware/         # JWT、日志、安全中间件
│   └── exceptions/         # 异常定义
├── web/                    # 前端（React）
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── requirements.txt
```

## 环境要求

- Python >= 3.12
- Node.js >= 20
- Docker & Docker Compose（用于运行基础设施服务）

## 运行方式

项目支持两种运行方式：

### 方式一：本地开发（推荐）

后端和前端在本地运行，MySQL、Redis、Milvus 通过 Docker 容器运行。

**1. 克隆项目并初始化**

```bash
git clone https://github.com/lee-hangzhou/chat2sql && cd chat2sql

# 创建 Python 虚拟环境
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 一键初始化（安装依赖 + 生成 .env）
make setup
```

**2. 编辑配置**

打开 `.env`，根据你的 LLM 使用方式配置：

```bash
# 使用 OpenAI
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4o-mini

# 使用 Ollama 等本地模型（无需 API Key）
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5

# 业务数据库（NL2SQL 的查询目标库）
BUSINESS_DATABASE_URL=mysql://root:123456@localhost:3306/your_business_db
```

其他配置项均有默认值，参见 `.env.example`。

**3. 启动基础设施服务**

```bash
make services-up
```

该命令会通过 Docker Compose 启动 MySQL、Redis、etcd、MinIO、Milvus。首次启动需要拉取镜像，耗时较长。

可通过 `docker compose ps` 确认所有服务状态为 healthy。

**4. 启动后端**

```bash
make dev
```

后端启动后会自动创建数据库表。API 文档：http://localhost:8000/docs

**5. 启动前端**

```bash
make fe-dev
```

前端默认运行在 http://localhost:3000 。

**6. 停止基础设施服务**

```bash
make services-down
```

### 方式二：Docker Compose 全栈部署

所有组件（应用、MySQL、Redis、Milvus）通过 Docker Compose 一键启动。适用于演示或生产部署。

**1. 准备配置**

```bash
cp .env.example .env
# 编辑 .env，配置 OPENAI_API_KEY 等必填项
```

**2. 构建并启动**

```bash
make docker-build
make docker-up
```

应用运行在 http://localhost:8000 ，前端已内嵌在后端中。

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
| `make services-up` | 启动基础设施服务 |
| `make services-down` | 停止基础设施服务 |
| `make dev` | 启动后端开发服务器 |
| `make fe-dev` | 启动前端开发服务器 |
| `make fe-build` | 构建前端生产包 |
| `make lint` | 代码检查 |
| `make format` | 代码格式化 |
| `make test` | 运行测试 |

## API 文档

启动后端后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT
