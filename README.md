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
│  │  - AsyncBatchUploader 异步批量上报                               │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
└───────────────────────────┼────────────────────────────────────────────┘
                            │ HTTP POST /api/v1/collect
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          后端服务层                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Collector                                               │  │
│  │  - 参数校验 → Kafka 投递 → 立即返回 202                          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                           │                                            │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │  Kafka (KRaft 模式, 高并发削峰)                                   │  │
│  │  Topic: agent-logs                                               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                           │                                            │
│  ┌────────────────────────▼─────────────────────────────────────────┐  │
│  │  Kafka Consumer → ClickHouse 批量写入                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Query API: /api/v1/traces, /api/v1/metrics/compare              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          前端展示层                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  React Dashboard                                                 │  │
│  │  - Trace Tree 瀑布图 (展开每个 Span 查看详情)                     │  │
│  │  - Timeline 耗时展示                                             │  │
│  │  - Prompt Replay (查看 Prompt/Response/Tool 调用记录)            │  │
│  │  - Token/Cost/Latency 统计图表                                   │  │
│  │  - 多模型效能对比 (Prefill 延迟, Decode 速度, Token 消耗)        │  │
│  │  - Session/Agent/模型 多维度筛选                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **探针 SDK** | Python 3.10+ | 异步/同步拦截，基于 Context 传递 |
| **后端服务** | FastAPI | 异步框架，高并发 Ingestion |
| **消息中间件** | Kafka (KRaft) | 单机 Docker 版，高并发削峰，无需 Zookeeper |
| **数据存储** | ClickHouse | 列式数据库，日志与时序链路存储 |
| **前端展示** | React + Vite | 轻量级单页应用，瀑布图与性能指标看板 |
| **容器化** | Docker Compose | 一键启动基础设施 |

## 项目结构

```
agent-observability/
├── docker-compose.yml          # Docker 编排文件 (Kafka + ClickHouse)
├── docker/
│   └── clickhouse/
│       ── init.sql           # ClickHouse 初始化脚本
├── sdk/                       # Python 探针 SDK
│   ├── agent_insight_sdk/
│   │   ├── __init__.py        # 模块入口
│   │   ├── context.py         # 上下文管理 (contextvars)
│   │   ├── interceptor.py     # LLM 拦截器 (OpenAI 客户端打桩)
│   │   ├── stream_monitor.py  # 流式响应监控 (prefill/decode/TPS)
│   │   └── uploader.py        # 异步批量上报器
│   ├── tests/
│   │   └── test_agent_simulation.py  # Agent 模拟测试
│   ├── setup.py
│   └── SDK_USAGE.md           # SDK 使用文档
├── backend/                   # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置管理
│   │   ├── api/              # API 路由
│   │   │   ├── collect.py    # 数据接收接口
│   │   │   ├── traces.py     # 链路查询接口
│   │   │   └── metrics.py    # 指标对比接口
│   │   ├── kafka/            # Kafka 生产者与消费者
│   │   │   ├── producer.py
│   │   │   └── consumer.py
│   │   └── clickhouse/       # ClickHouse 客户端
│   │       └── client.py
│   ├── tests/
│   │   └── test_api.py
│   └── requirements.txt
└── frontend/                  # React 前端
    ├── src/
    │   ├── pages/
    │   │   ├── TraceView.jsx      # 链路瀑布图
    │   │   └── MetricsCompare.jsx # 多模型效能对比
    │   ├── App.jsx
    │   └── main.jsx
    ├── index.html
    ├── package.json
    └── vite.config.js
```

## 快速开始

### 1. 启动基础设施

```bash
docker-compose up -d
```

这将启动：
- **Kafka** (端口 9092/9093) - 使用 KRaft 模式，无需 Zookeeper
- **ClickHouse** (端口 8123 HTTP / 9000 Native)

### 2. 安装 SDK

```bash
cd sdk
pip install -e .
```

### 3. 启动后端服务

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 5. 验证全链路

```bash
cd sdk
python tests/test_agent_simulation.py
```

然后访问 http://localhost:3000 查看 Dashboard。

## 核心功能

### 探针 SDK

| 功能 | 说明 |
|------|------|
| **上下文管理** | 基于 `contextvars` 维持异步环境下的 trace_id 和 span_id 链条 |
| **LLM 拦截器** | 自动拦截 OpenAI 客户端调用，记录 model/stream/tokens/latency |
| **流式监控** | 精确计算 prefill_ms (首字耗时) 和 decode_ms |
| **TPS 计算** | 每秒 Token 吞吐量 = Output Tokens / Decode Time (s) |
| **异步批量上报** | 内存队列 + 后台任务，每 500ms 或满 20 条触发上报 |
| **错误捕获** | 自动记录异常 span，包含错误信息 |

### 后端服务

| 功能 | 说明 |
|------|------|
| **Ingestion API** | `/api/v1/collect` 极速接收，投递 Kafka 后立即返回 202 |
| **流式清洗消费器** | Kafka 消费者批量写入 ClickHouse |
| **Trace 查询** | `/api/v1/traces` 支持根据 TraceId 查看完整执行过程 |
| **指标对比** | `/api/v1/metrics/compare` 多模型效能横向对比 |
| **健康检查** | `/health` 服务状态检测 |

### 前端看板

| 功能 | 说明 |
|------|------|
| **Trace Tree** | 瀑布图展示单次 Agent 任务全链路，可展开每个 Span 查看详情 |
| **Timeline** | 展示每个步骤的耗时分布 |
| **Prompt Replay** | 查看 Prompt、Response、Tool 调用记录 |
| **统计图表** | Token、Cost、Latency 等维度统计 |
| **多模型对比** | 横向对比不同模型的 Prefill 延迟、Decode 速度 (TPS)、Token 消耗 |
| **多维度筛选** | 支持 Session、Agent、模型等维度筛选数据 |

## 课程大纲

本项目按照以下 6 个阶段逐步构建：

### 第 1 课 - AI Agent 与可观测系统概述

- **核心知识点**: AI Agent 架构 (LLM, Planner, Tool, Memory)，AI Observability 概念，Harness/LangFuse/LangSmith 对比，为什么传统 APM 不适用于 AI Agent
- **实践内容**:
  1. 使用 OpenAI API 搭建一个简单 Agent (用户输入→LLM→输出)
  2. 为 Agent 增加一个 Tool (如天气查询、搜索、计算器)
  3. 打印 Agent 整个执行流程日志 (Prompt, Tool, Response)
  4. 分析日志存在的问题 (难以定位、无法统计、无法回放)，引出可观测系统的需求
- **课后成果**: 搭建一个最小可运行的 AI Agent，并理解可观测系统的价值

### 第 2 课 - Trace 模型设计

- **核心知识点**: Trace, Span, Event, Workflow, Session；OpenTelemetry 思想；Agent 生命周期建模
- **实践内容**:
  1. 设计 Trace、Span、Event 等核心数据结构
  2. 为 Agent 每个步骤创建 Span (LLM, Tool, Memory)
  3. 实现 Trace 树，记录 Parent Span 与 Child Span
  4. 自动计算每个 Span 的耗时、状态、错误信息
  5. 输出 JSON 格式 Trace，方便后续 Collector 接收
- **课后成果**: Agent 已具备完整 Trace 能力，可生成调用树

### 第 3 课 - SDK 自动埋点

- **核心知识点**: SDK 设计、Decorator、Middleware、Context Propagation、事件采集
- **实践内容**:
  1. 编写 Trace SDK，对外提供 `startTrace()`、`startSpan()`、`endSpan()` 等 API
  2. 封装 LLM SDK，实现自动记录 Prompt、Completion、Token、Latency
  3. 封装 Tool SDK，实现自动记录输入、输出、异常、耗时
  4. 自动关联 TraceId、SpanId，业务代码无需手动传递
  5. 实现 SDK 日志导出，为 Collector 做准备
- **课后成果**: 完成一个可复用的 Agent Observability SDK

### 第 4 课 - Collector 与存储

- **核心知识点**: Collector、事件接收、数据库设计、批量写入、查询接口
- **实践内容**:
  1. 使用 FastAPI 开发 Collector 服务
  2. 接收 SDK 上传的 Trace 数据并进行参数校验
  3. 设计数据库 (Trace, Span, Prompt, ToolCall, Session 等表)
  4. 实现批量写入，提高数据采集性能
  5. 提供查询接口，支持根据 TraceId 查看完整执行过程
- **课后成果**: 完成后端数据采集与存储链路

### 第 5 课 - Dashboard 可视化

- **核心知识点**: Trace Tree、Timeline、Prompt Replay、Token Dashboard、统计分析
- **实践内容**:
  1. 使用 React 搭建管理后台
  2. 实现 Trace Tree，可展开每个 Span 查看详情
  3. 实现 Timeline，展示每个步骤的耗时
  4. 实现 Prompt Replay，查看 Prompt、Response、Tool 调用记录
  5. 实现 Token、Cost、Latency 等统计图表
  6. 支持 Session、Agent、模型等维度筛选数据
- **课后成果**: 拥有完整的 AI Agent 可观测性平台前端

### 第 6 课 - 企业级能力与项目优化

- **核心知识点**: Harness 架构、多 Agent、MCP、Prompt Version、告警系统、生产实践
- **实践内容**:
  1. 增加多 Agent 支持，展示多个 Agent 协同执行过程
  2. 增加 Prompt Version，记录 Prompt 历史版本
  3. 增加告警规则 (Tool 连续失败、Token 激增、LLM 超时)
  4. 增加排行榜 (最耗 Token、最慢 Tool、最常失败 Agent)
  5. 对接 OpenTelemetry 数据模型，兼容标准 Trace
  6. 完善 README、系统架构图、部署脚本，形成可展示的个人项目
- **课后成果**: 完成一个接近企业级的 Mini Harness，可作为简历项目展示

## 开发进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 第 1 课 | AI Agent 与可观测系统概述 | ✅ 完成 |
| 第 2 课 | Trace 模型设计 | ✅ 完成 |
| 第 3 课 | SDK 自动埋点 | ✅ 完成 |
| 第 4 课 | Collector 与存储 |  进行中 |
| 第 5 课 | Dashboard 可视化 | 🚧 进行中 |
| 第 6 课 | 企业级能力与项目优化 | ⏳ 待开发 |

## License

MIT
