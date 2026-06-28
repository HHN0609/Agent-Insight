# AI Agent 可观测性系统 (Agent-Insight)

一个轻量级但具备高并发扩展能力的 AI Agent 可观测性基础设施原型。

## 架构概述

系统采用"重后端、轻前端"的设计哲学，核心复杂度集中在：
- Python 探针 SDK 的非侵入式拦截
- 异步批量上报
- 后端的数据流管道

## 技术栈

- **探针 SDK**: Python 3.10+ (异步/同步拦截，基于 Context 传递)
- **后端服务**: Python FastAPI 异步框架
- **消息中间件**: Kafka (单机 Docker 版，高并发削峰)
- **数据存储**: ClickHouse (日志与时序链路) + SQLite (元数据与配置)
- **前端展示**: React (轻量级单页应用，瀑布图与性能指标看板)
- **容器化**: Docker Compose 一键启动

## 项目结构

```
agent-observability/
├── docker-compose.yml          # Docker 编排文件
├── docker/
│   └── clickhouse/
│       └── init.sql           # ClickHouse 初始化脚本
├── sdk/                       # Python 探针 SDK
│   ├── agent_insight_sdk/
│   │   ├── __init__.py
│   │   ├── context.py         # 上下文管理 (contextvars)
│   │   ├── interceptor.py     # LLM 拦截器
│   │   ├── stream_monitor.py  # 流式响应监控
│   │   └── uploader.py        # 异步批量上报器
│   ├── tests/
│   └── setup.py
├── backend/                   # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── api/              # API 路由
│   │   ├── kafka/            # Kafka 生产者与消费者
│   │   └── clickhouse/       # ClickHouse 客户端
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/                  # React 前端
    ├── src/
    ├── public/
    └── package.json
```

## 快速开始

### 1. 启动基础设施

```bash
docker-compose up -d
```

这将启动：
- Zookeeper (端口 2181)
- Kafka (端口 9092/9093)
- ClickHouse (端口 8123/9000)

### 2. 安装 SDK

```bash
cd sdk
pip install -e .
```

### 3. 启动后端服务

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. 启动前端

```bash
cd frontend
npm install
npm start
```

## 核心功能

### 探针 SDK

- **上下文管理**: 基于 `contextvars` 维持异步环境下的 trace_id 和 span_id 链条
- **LLM 拦截器**: 自动拦截 OpenAI 客户端调用
- **流式监控**: 精确计算 prefill_ms (首字耗时) 和 decode_ms
- **TPS 计算**: 每秒 Token 吞吐量 = Output Tokens / Decode Time (s)
- **异步批量上报**: 内存队列 + 后台任务定期上报

### 后端服务

- **Ingestion API**: `/api/v1/collect` 极速接收，投递 Kafka 后立即返回 202
- **流式清洗消费器**: Kafka 消费者批量写入 ClickHouse
- **查询 API**: `/api/v1/traces` 和 `/api/v1/metrics/compare`

### 前端看板

- **链路跟踪页**: 瀑布图展示单次 Agent 任务全链路
- **多模型效能对比**: 横向对比不同模型的 Prefill 延迟、Decode 速度 (TPS)、Token 消耗

## 开发阶段

1. ✅ 基础设施与容器化环境搭建
2. ⏳ Python 探针 SDK 开发
3. ⏳ 高并发后端日志处理服务
4. ⏳ 轻量级 React 前端与全链路可视化

## License

MIT
