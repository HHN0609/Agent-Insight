# 项目总览

## 一句话定位

Agent-Insight 是一个 **AI Agent 可观测性系统**：用非侵入式 SDK 采集 LLM 调用 / Tool 调用 / 会话数据，经 Kafka 缓冲后写入 ClickHouse，再通过 FastAPI 查询接口和 React Dashboard 可视化。解决"LLM 延迟多少、哪个模型最省钱、哪个 Tool 是瓶颈"等问题。

## 系统数据流

```
Agent 代码
  │  LLMInterceptor.wrap(client) / @instrument / start_trace()
  ▼
SDK 探针层（contextvars 上下文 + StreamMonitor 计时 + SessionSDK 聚合）
  │  AsyncBatchUploader（有界队列 10000，每 20 条 / 500ms 批量上报）
  ▼
FastAPI Collector   POST /api/v1/collect  → 校验 → Kafka send() → 202 Accepted
  ▼
Kafka（KRaft 模式，topic: agent-logs，无 Zookeeper）
  ▼
Kafka Consumer（按 span_type 分流，50 条/批 或 5 秒强制刷新）
  ▼
ClickHouse（5 业务表 + 2 聚合表 + 2 物化视图）
  ▼
FastAPI Query API（6 个查询接口）
  ▼
React Dashboard（7 个页面）
```

**关键设计意图**：
- Collector 只投递 Kafka 立刻返回 202，**不等 ClickHouse 写完**，保证高并发接入不阻塞。
- Kafka 做削峰与解耦，ClickHouse 宕机时数据暂存 Kafka，恢复后继续消费。
- ClickHouse 列式存储适合"写多读少、聚合分析为主"的可观测场景。

## 技术栈

| 层 | 技术 | 版本 | 关键说明 |
|----|------|------|---------|
| SDK | Python | 3.10+ | contextvars 异步安全；Provider Adapter 多厂商 |
| 后端 | FastAPI + Uvicorn | 0.3.x | 异步框架，`asyncio.to_thread` 包装同步 ClickHouse IO |
| 消息队列 | Kafka（KRaft） | confluentinc/cp-kafka:7.5.0 | 无 Zookeeper，端口 9093 |
| 存储 | ClickHouse | 23.8 | Native 9000 / HTTP 8123 |
| 前端 | React 18 + TypeScript + Vite | - | Recharts 图表，React Router v6，深色主题 |
| 容器 | Docker Compose | - | 一键起 Kafka + ClickHouse |

## 模块边界与依赖方向

```
sdk/  ──HTTP POST──▶  backend/  ──produce──▶  Kafka  ──consume──▶  backend/  ──write──▶  ClickHouse
                                                                                    ▲
                                                frontend/  ──GET query──  backend/
```

- **依赖是单向的**：SDK 只依赖后端的 HTTP 接口，不知道 Kafka/ClickHouse 存在；后端不知道前端存在；前端只依赖后端查询 API。
- **禁止反向耦合**：后端不得 import SDK 代码；前端不得假设后端存储细节。
- **跨层共享的只有数据契约**（5 种 span_type 的字段定义），见 [invariants.md](./invariants.md)。

## 三层职责速览

### SDK（`sdk/agent_insight_sdk/`）

| 模块 | 职责 |
|------|------|
| `context.py` | contextvars 管理 trace_id / span_id / parent_span_id |
| `providers/base.py` | `LLMInterceptor` 统一入口 + `BaseProviderAdapter` 抽象 |
| `providers/openai_compatible.py` / `anthropic.py` | 各厂商 Adapter |
| `stream_monitor.py` | 流式响应 prefill_ms / decode_ms / TPS 计算 |
| `tool_sdk.py` | `@instrument` / `@instrument_mcp` / `@instrument_rag` 装饰器 |
| `span_api.py` | 显式 `start_trace` / `start_span` / `end_span` |
| `session_sdk.py` | 会话生命周期自动聚合 + **Token 定价表** |
| `uploader.py` | `AsyncBatchUploader` 有界队列 + `SpanData`（5 种 span_type） |

### Backend（`backend/app/`）

| 模块 | 职责 |
|------|------|
| `main.py` | FastAPI 入口，CORS，路由注册，启动/关闭钩子 |
| `api/collect.py` | `POST /api/v1/collect`，按 span_type 校验必填字段 |
| `api/traces.py` / `metrics.py` / `prompts.py` / `leaderboard.py` | 6 个查询接口 |
| `kafka/producer.py` | `send()` + 回调，非阻塞投递 |
| `kafka/consumer.py` | 按 span_type 分流 + **Token 定价表**（与 SDK 双向同步） |
| `clickhouse/client.py` | `_SPECS` 注册表驱动的通用写入/查询 |

### Frontend（`frontend/src/`）

7 个页面：链路瀑布图 / 时间线 / Prompt 回放 / Session 列表 / 模型对比 / 统计仪表盘 / 排行榜。严格 TypeScript，字段 snake_case 对接后端。详见 `frontend/src/types.ts`。

## 基础设施

- `docker-compose.yml`：Kafka（9092/9093）+ ClickHouse（8123/9000）。
- `docker/clickhouse/init.sql`：建 5 业务表 + 2 聚合表 + 2 物化视图。**仅在数据卷为空时执行**，已有库升级需手动幂等 ALTER（见 [invariants.md](./invariants.md)）。
- `.env.example`：后端地址 + 各 LLM 厂商 API Key 模板。
