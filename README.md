# AI Agent 可观测性系统 (Agent-Insight)

一个轻量级但具备高并发扩展能力的 AI Agent 可观测性基础设施原型。

> 本项目是一个完整的 AI Agent 可观测性系统，涵盖从 SDK 自动埋点、数据采集存储到 Dashboard 可视化的全链路，可作为简历项目展示。

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AI Agent 应用层                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  OpenAI Client / 自定义 Tool / Memory / Planner                  │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
│                           │                                            │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │  Agent Insight SDK (非侵入式拦截)                                 │  │
│  │  - TraceContext 上下文传递 (contextvars)                         │  │
│  │  - OpenAIInterceptor LLM 调用拦截                                │  │
│  │  - StreamMonitor 流式响应监控 (prefill/decode/TPS)               │  │
│  │  - ToolSDK 装饰器自动埋点                                        │  │
│  │  - TraceAPI 显式 startTrace/startSpan/endSpan                    │  │
│  │  - AsyncBatchUploader 异步批量上报                               │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
└───────────────────────────┼────────────────────────────────────────────┘
                            │ HTTP POST /api/v1/collect
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          后端服务层                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Collector (v0.3.0)                                      │  │
│  │  - 5 种数据类型参数校验 → Kafka 投递 → 立即返回 202              │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
│                           │                                            │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │  Kafka (KRaft 模式, 无需 Zookeeper)                               │  │
│  │  Topic: agent-logs                                               │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
│                           │                                            │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │  Kafka Consumer → ClickHouse 按类型分流写入 5 张表               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Query API (5 个路由模块)                                         │  │
│  │  /api/v1/collect  /traces  /sessions  /prompts  /tool-calls      │  │
│  │  /api/v1/metrics/compare  /leaderboard                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          前端展示层                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  React 18 + TypeScript + Vite + Recharts                         │  │
│  │  - Trace Tree 瀑布图 (展开每个 Span 查看详情)                     │  │
│  │  - Timeline 时间线 (按 span 类型着色)                             │  │
│  │  - Prompt Replay (Prompt / Response / Tool 调用记录)             │  │
│  │  - Session 会话列表 (多维度筛选 + 关联链路)                       │  │
│  │  - 模型效能对比 (Prefill / Decode / TPS 柱状图)                   │  │
│  │  - 统计分析 (Token 分布 / 成本分布 / 性能折线图)                  │  │
│  │  - 排行榜 (最慢 Tool / Token 消耗 / 失败次数)                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **探针 SDK** | Python 3.10+ | 异步/同步拦截，基于 contextvars 传递 |
| **后端服务** | FastAPI | 异步框架，高并发 Ingestion |
| **消息中间件** | Kafka (KRaft) | 单机 Docker 版，高并发削峰，无需 Zookeeper |
| **数据存储** | ClickHouse | 列式数据库，6 张表 + 2 个物化视图 |
| **前端展示** | React 18 + TypeScript | Vite 构建，Recharts 图表，React Router v6 |
| **容器化** | Docker Compose | 一键启动 Kafka + ClickHouse |

## 项目结构

```
agent-observability/
├── docker-compose.yml              # Docker 编排 (Kafka + ClickHouse)
├── docker/
│   └── clickhouse/
│       └── init.sql                # ClickHouse 初始化 (6 表 + 2 物化视图)
│
├── sdk/                            # Python 探针 SDK
│   ├── agent_insight_sdk/
│   │   ├── __init__.py             # 模块入口 (6 个公开 API)
│   │   ├── context.py              # TraceContext 上下文管理 (contextvars)
│   │   ├── interceptor.py          # OpenAIInterceptor LLM 调用拦截
│   │   ├── stream_monitor.py       # StreamMonitor 流式响应监控
│   │   ├── tool_sdk.py             # ToolSDK 装饰器自动埋点
│   │   ├── trace_api.py            # TraceAPI 显式 startTrace/startSpan/endSpan
│   │   └── uploader.py             # AsyncBatchUploader 异步批量上报
│   ├── examples/
│   │   ├── lesson1_simple_agent.py # 第1课：无埋点简单 Agent 演示
│   │   └── lesson3_sdk_demo.py     # 第3课：SDK 完整功能演示
│   ├── tests/
│   │   └── test_agent_simulation.py
│   ├── setup.py
│   └── SDK_USAGE.md                # SDK 完整使用文档
│
├── backend/                        # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口 (8 个路由注册)
│   │   ├── config.py               # 配置管理
│   │   ├── api/                    # API 路由模块
│   │   │   ├── collect.py          # POST /api/v1/collect (5 种数据类型校验)
│   │   │   ├── traces.py           # GET /api/v1/traces + /sessions
│   │   │   ├── metrics.py          # GET /api/v1/metrics/compare
│   │   │   ├── prompts.py          # GET /api/v1/prompts + /tool-calls
│   │   │   └── leaderboard.py      # GET /api/v1/leaderboard (3 维度排行)
│   │   ├── kafka/
│   │   │   ├── producer.py         # Kafka 生产者
│   │   │   └── consumer.py         # Kafka 消费者 (按 span_type 分流 5 表)
│   │   └── clickhouse/
│   │       └── client.py           # ClickHouse 客户端 (5 insert + 6 query)
│   ├── tests/
│   │   └── test_api.py
│   └── requirements.txt
│
└── frontend/                       # React + TypeScript 前端
    ├── src/
    │   ├── main.tsx                # 入口
    │   ├── App.tsx                 # 路由 + 侧边栏 (7 个页面入口)
    │   ├── types.ts                # 全局类型定义 (15+ 接口)
    │   ├── index.css               # 深色主题样式
    │   └── pages/
    │       ├── TraceView.tsx        # 链路瀑布图
    │       ├── Timeline.tsx         # 时间线
    │       ├── PromptReplay.tsx     # Prompt 回放
    │       ├── SessionList.tsx      # Session 会话列表
    │       ├── MetricsCompare.tsx   # 模型效能对比
    │       ├── StatsDashboard.tsx   # 统计分析 (柱/饼/折线图)
    │       └── Leaderboard.tsx      # 排行榜
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    └── vite.config.ts
```

## 快速开始

### 前置条件

- Docker Desktop（已安装）
- Python 3.10+
- Node.js 18+

### 1. 启动基础设施

```bash
docker-compose up -d
```

这将启动：
- **Kafka** on `localhost:9092/9093`（KRaft 模式，无需 Zookeeper）
- **ClickHouse** on `localhost:8123`/`9000`（自动执行 init.sql 建表）

验证：

```bash
curl http://localhost:8123/ping      # 应返回 Ok
```

### 2. 启动后端服务

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

验证：

```bash
curl http://localhost:8000/health    # 应返回 {"status":"ok"}
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

### 4. 运行 SDK 示例验证全链路

```bash
cd sdk
pip install -e .
python examples/lesson1_simple_agent.py     # 第1课演示
python examples/lesson3_sdk_demo.py         # 第3课 SDK 完整演示
python tests/test_agent_simulation.py       # 模拟测试
```

## API 接口一览

### 数据采集

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/collect` | 接收 SDK 上报，支持 trace / llm_metrics / prompt / tool_call / session 五种 span_type，投递 Kafka 后立即返回 202 |

### 数据查询

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| `GET` | `/api/v1/traces` | `trace_id`, `limit` | 链路追踪数据，传 trace_id 查看完整 Trace Tree |
| `GET` | `/api/v1/sessions` | `agent_name`, `limit` | Session 会话列表，支持按 Agent 名称筛选 |
| `GET` | `/api/v1/prompts` | `trace_id`, `limit` | Prompt / Response 回放记录 |
| `GET` | `/api/v1/tool-calls` | `trace_id`, `limit` | Tool 调用记录（输入/输出/耗时/状态） |
| `GET` | `/api/v1/metrics/compare` | `model_names`, `hours` | 多模型效能对比（Prefill / Decode / TPS / Cost） |
| `GET` | `/api/v1/leaderboard` | `metric`, `limit` | 排行榜：`slowest_tool` / `most_tokens` / `most_failed` |

## 数据库设计

ClickHouse 包含 6 张业务表 + 2 个物化视图：

| 表名 | 说明 | Engine |
|------|------|--------|
| `agent_traces` | 链路追踪 Span 数据 | MergeTree |
| `llm_metrics` | LLM 性能指标（prefill/decode/TPS/cost） | MergeTree |
| `prompt_logs` | Prompt/Response 记录 | MergeTree |
| `tool_calls` | Tool 调用记录 | MergeTree |
| `sessions` | Agent Session 会话 | MergeTree |
| `model_stats_daily` | 模型按日聚合统计（物化视图） | SummingMergeTree |
| `tool_stats` | Tool 调用聚合统计（物化视图） | SummingMergeTree |

## SDK 核心能力

```python
from agent_insight_sdk import (
    TraceContext,          # 上下文管理
    OpenAIInterceptor,     # LLM 调用拦截
    StreamMonitor,         # 流式响应监控
    ToolSDK,               # Tool 自动埋点
    TraceAPI,              # 显式 Trace API
    AsyncBatchUploader,    # 异步批量上报
)
```

| 组件 | 功能 |
|------|------|
| `TraceContext` | 基于 contextvars 的异步安全上下文，自动维护 trace_id / span_id / parent_span_id |
| `OpenAIInterceptor` | 包装 OpenAI 客户端，自动拦截所有 LLM 调用，记录 model / stream / tokens / latency |
| `StreamMonitor` | 监控流式响应的 chunk，精确计算 prefill_ms（首字耗时）和 decode_ms（生成耗时） |
| `ToolSDK` | `@tool_sdk.instrument()` 装饰器，自动记录 Tool 输入/输出/耗时/异常 |
| `TraceAPI` | 显式 `startTrace()` / `startSpan()` / `endSpan()` API，适用于需要手动控制链路场景 |
| `AsyncBatchUploader` | 内存队列 + 后台任务，每 500ms 或满 20 条自动批量上报至后端 |

## 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 链路跟踪 | `/` | Span 瀑布图，可选中链路查看子 Span 层级 |
| 时间线 | `/timeline` | 按时间轴展示 Span，按类型着色（trace/llm/tool） |
| Prompt 回放 | `/prompt-replay` | 查看 LLM 的 Prompt/Response 和 Tool 调用记录 |
| Session 会话 | `/sessions` | Session 列表，汇总统计，支持点开查看关联链路 |
| 模型效能对比 | `/metrics` | 多模型 Prefill / Decode / TPS 柱状图 + 详细数据表 |
| 统计分析 | `/stats` | 汇总卡片 + Token 分布柱状图 + 成本饼图 + 性能折线图 |
| 排行榜 | `/leaderboard` | 最慢 Tool / Token 消耗 / 失败次数 三维度排行 |

## 课程大纲

本项目按照以下 6 个阶段逐步构建：

### 第 1 课 - AI Agent 与可观测系统概述

- 使用 OpenAI API 搭建简单 Agent（用户输入 → LLM → 输出）
- 为 Agent 增加 Tool（计算器 / 天气查询）
- 打印执行流程日志，分析日志问题，引出可观测系统需求
- **示例**: `sdk/examples/lesson1_simple_agent.py`

### 第 2 课 - Trace 模型设计

- 设计 Trace / Span / Event 核心数据结构
- 为 Agent 每个步骤创建 Span（LLM / Tool / Memory）
- 实现 Parent Span → Child Span 调用树
- 自动计算耗时、状态、错误信息
- **实现**: `sdk/agent_insight_sdk/context.py`

### 第 3 课 - SDK 自动埋点

- `OpenAIInterceptor` — 封装 LLM SDK，自动记录 Prompt / Completion / Token / Latency
- `StreamMonitor` — 流式响应监控，精确计算 prefill_ms / decode_ms / TPS
- `ToolSDK` — 装饰器自动记录 Tool 输入/输出/异常/耗时
- `TraceAPI` — 显式 `startTrace()` / `startSpan()` / `endSpan()` API
- `AsyncBatchUploader` — 异步批量上报至后端
- **示例**: `sdk/examples/lesson3_sdk_demo.py`

### 第 4 课 - Collector 与存储

- FastAPI Collector 服务，接收 5 种 span_type 并进行参数校验
- Kafka 消息中间件削峰，Consumer 按类型分流写入 5 张 ClickHouse 表
- 6 张业务表 + 2 个物化视图
- 提供查询接口：traces / sessions / prompts / tool-calls / metrics / leaderboard
- **实现**: `backend/app/api/` + `backend/app/kafka/consumer.py` + `backend/app/clickhouse/client.py`

### 第 5 课 - Dashboard 可视化

- 7 个前端页面，React 18 + TypeScript + Recharts
- Trace Tree 瀑布图、Timeline 时间线、Prompt Replay
- Session 会话列表、多模型效能对比
- Token / Cost / Latency 统计图表（柱状图 + 饼图 + 折线图）
- Session / Agent / 模型 多维度筛选
- **实现**: `frontend/src/pages/`

### 第 6 课 - 效能分析与排名

- 排行榜 API 三维度：最慢 Tool / Token 消耗 / 失败次数
- Tool 统计物化视图，自动聚合调用次数、耗时、错误率
- 模型统计物化视图，按日聚合请求数、Token 消耗、成本
- 全 TypeScript 前端 + 严格类型校验，零 tsc 错误
- **实现**: `backend/app/api/leaderboard.py` + `frontend/src/pages/Leaderboard.tsx`

## 开发进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 第 1 课 | AI Agent 与可观测系统概述 | ✅ 完成 |
| 第 2 课 | Trace 模型设计 | ✅ 完成 |
| 第 3 课 | SDK 自动埋点 | ✅ 完成 |
| 第 4 课 | Collector 与存储 | ✅ 完成 |
| 第 5 课 | Dashboard 可视化 | ✅ 完成 |
| 第 6 课 | 企业级能力与项目优化 | ✅ 完成 |

## License

MIT
