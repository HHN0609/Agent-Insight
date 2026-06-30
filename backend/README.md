# Agent Insight Backend

AI Agent 可观测性后端服务 —— 接收 SDK 上报的链路追踪和性能指标数据，经 Kafka 异步写入 ClickHouse，并提供查询 API。

## 架构

```
┌──────────┐   POST /api/v1/collect    ┌──────────────┐    produce     ┌───────┐
│   SDK    │ ──────────────────────────▶│   FastAPI    │ ─────────────▶│ Kafka │
└──────────┘                            │   Backend    │               └───┬───┘
                                        └──────────────┘                   │
                                               │                      consume
                                               │  GET /api/v1/*           │
                                               ▼                           ▼
                                        ┌──────────────┐           ┌────────────┐
                                        │   前端 / CLI  │◀──────────│ ClickHouse │
                                        └──────────────┘   query   └────────────┘
```

**数据流**：SDK → `POST /api/v1/collect` → Kafka Producer → Kafka → Kafka Consumer → ClickHouse（5 张表按类型分流）

## 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口
│   ├── config.py                # 配置管理（环境变量）
│   ├── api/
│   │   ├── __init__.py
│   │   ├── collect.py           # 数据收集 API
│   │   ├── traces.py            # 链路查询 & Session 查询 API
│   │   ├── metrics.py           # 多模型效能对比 API
│   │   ├── prompts.py           # Prompt 回放 & Tool 调用查询 API
│   │   └── leaderboard.py       # 排行榜 API
│   ├── kafka/
│   │   ├── __init__.py
│   │   ├── producer.py          # Kafka 生产者（异步投递）
│   │   └── consumer.py          # Kafka 消费者（分流写入 ClickHouse）
│   └── clickhouse/
│       ├── __init__.py
│       └── client.py            # ClickHouse 客户端（写入 + 查询）
├── tests/
│   └── test_api.py              # API 测试脚本
└── requirements.txt
```

## 支持的 5 种数据类型

| span_type      | ClickHouse 表   | 说明                       |
|----------------|-----------------|---------------------------|
| `trace`        | `agent_traces`  | 链路追踪 span              |
| `llm_metrics`  | `llm_metrics`   | LLM 性能指标（prefill/decode/TPS） |
| `prompt`       | `prompt_logs`   | Prompt/Response 日志       |
| `tool_call`    | `tool_calls`    | Tool 调用记录              |
| `session`      | `sessions`      | Session 会话聚合数据       |

## API 接口

### 数据写入

| 方法 | 路径                | 说明                          |
|------|---------------------|------------------------------|
| POST | `/api/v1/collect`   | 接收 SDK 批量上报，投递至 Kafka |

返回 `202 Accepted` 表示数据已入队，实际持久化由 Consumer 异步完成。

### 数据查询

| 方法 | 路径                     | 参数                          | 说明               |
|------|--------------------------|-------------------------------|--------------------|
| GET  | `/api/v1/traces`         | `trace_id`, `limit`           | 链路追踪查询        |
| GET  | `/api/v1/sessions`       | `agent_name`, `limit`         | Session 会话列表    |
| GET  | `/api/v1/prompts`        | `trace_id`, `limit`           | Prompt 日志查询     |
| GET  | `/api/v1/tool-calls`     | `trace_id`, `limit`           | Tool 调用记录查询   |
| GET  | `/api/v1/metrics/compare`| `models`, `hours`             | 多模型效能对比       |
| GET  | `/api/v1/leaderboard`    | `metric`, `limit`             | 排行榜查询          |

### 健康检查

| 方法 | 路径         | 说明       |
|------|-------------|-----------|
| GET  | `/health`   | 服务健康检查 |

### 排行榜指标类型

| metric          | 说明                                  |
|-----------------|--------------------------------------|
| `slowest_tool`  | 最慢 Tool 调用（按平均耗时降序）        |
| `most_tokens`   | Token 消耗排行（按总 Token 数降序）     |
| `most_failed`   | 失败次数排行（按错误次数降序）          |

## 配置

通过环境变量或 `.env` 文件配置（使用 pydantic-settings）：

| 变量                       | 默认值                  | 说明              |
|---------------------------|------------------------|-------------------|
| `kafka_bootstrap_servers` | `localhost:9093`       | Kafka 地址         |
| `kafka_topic`             | `agent-logs`           | Kafka Topic       |
| `kafka_group_id`          | `agent-insight-consumer` | Consumer Group ID |
| `clickhouse_host`         | `localhost`            | ClickHouse 地址    |
| `clickhouse_port`         | `9000`                 | ClickHouse 端口    |
| `clickhouse_database`     | `default`              | 数据库名           |
| `clickhouse_user`         | `default`              | 用户名             |
| `clickhouse_password`     | `""`                   | 密码               |
| `backend_host`            | `0.0.0.0`              | 服务监听地址        |
| `backend_port`            | `8000`                 | 服务端口           |

示例 `.env` 文件：

```env
kafka_bootstrap_servers=localhost:9093
kafka_topic=agent-logs
clickhouse_host=localhost
clickhouse_port=9000
clickhouse_database=default
clickhouse_user=default
clickhouse_password=
```

## 安装与运行

### 前置依赖

- Python 3.10+
- Kafka（默认端口 9093）
- ClickHouse（默认端口 9000）

### 安装

```bash
cd backend
pip install -r requirements.txt
```

### 启动

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 运行测试

```bash
cd backend
python tests/test_api.py
```

测试脚本会依次验证：
1. `/health` — 健康检查
2. `/api/v1/collect` — 数据上报
3. `/api/v1/traces` — 链路查询
4. `/api/v1/metrics/compare` — 模型对比

## 关键设计

### Kafka 分流消费

Consumer 消费 Kafka 消息后，按 `span_type` 字段分流入 5 张 ClickHouse 表。批量阈值 50 条 + 每 5 秒强制刷新，兼顾吞吐和延迟。

### Token 成本计算

Consumer 内置主流模型的 Token 定价表，写入 ClickHouse 时自动计算 `cost_usd`：

| 模型            | 输入 $/1K tokens | 输出 $/1K tokens |
|-----------------|-----------------|------------------|
| gpt-4           | 0.03            | 0.06             |
| gpt-4-turbo     | 0.01            | 0.03             |
| gpt-3.5-turbo   | 0.0005          | 0.0015           |
| claude-3-opus   | 0.015           | 0.075            |
| claude-3-sonnet | 0.003           | 0.015            |
| claude-3-haiku  | 0.00025         | 0.00125          |

未匹配到的模型按 $0.001 / $0.002 默认价格计算。

### 容错设计

- **Kafka Producer**：使用 `send()` + 回调模式，不阻塞 FastAPI handler；SDK 侧有重试兜底
- **ClickHouse 写入**：指数退避重试（1s → 2s → 4s，最多 3 次），失败后丢弃并记录错误日志
- **数据校验**：Collector 按 `span_type` 校验必填字段，不合法数据直接返回 400

## 技术栈

| 组件        | 技术                         |
|------------|------------------------------|
| Web 框架    | FastAPI + Uvicorn            |
| 消息队列    | Kafka（aiokafka 异步客户端）   |
| 数据库      | ClickHouse（clickhouse-driver） |
| 配置管理    | pydantic-settings            |
| 测试        | httpx                        |
