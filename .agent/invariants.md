# 不可破坏的硬约束（Invariants）

> **这是本目录最重要的文件。** 以下每一条都是已落地的设计决策，违反会导致数据错乱、服务崩溃或全链路断裂。动任何代码前必读；若某条约束阻碍正当需求，应先与维护者确认，而非擅自绕过。

每条约束标注了**涉及位置**与**违反后果**，便于判断改动影响面。

---

## 1. 数据契约：5 种 span_type 必须四端闭环

系统全程围绕 5 种 `span_type` 流转，它们必须在 **4 个位置**保持一致定义：

| span_type | ClickHouse 表 | 说明 |
|-----------|---------------|------|
| `custom` | `agent_traces` | 链路 Span |
| `llm_metrics` | `llm_metrics` | LLM 性能指标 |
| `prompt` | `prompt_logs` | Prompt/Response |
| `tool_call` | `tool_calls` | Tool 调用 |
| `session` | `sessions` | 会话汇总 |

**涉及位置**（改一处必须同步其余三处）：
1. `sdk/agent_insight_sdk/uploader.py` — `SpanData` 的 `span_type` 字段与序列化分支
2. `backend/app/api/collect.py` — `REQUIRED_FIELDS` 校验表
3. `backend/app/kafka/consumer.py` — `PARSE_MAP` 分流表 + `consume_loop` 的分流逻辑
4. `docker/clickhouse/init.sql` — 对应的 `CREATE TABLE`

**违反后果**：新增类型只改了一端，会导致数据被错误分流、写入失败、或校验拒绝合法数据。
**默认行为**：未知 `span_type` 在 collector 与 consumer 中都**回退到 `custom`** 的规则，不要改成"拒绝"否则会破坏向前兼容。

---

## 2. Token 定价表必须 SDK 与 Backend 双向同步

定价表（USD / 1M tokens）在**两处**独立维护，修改任一处必须同步另一处：

- `sdk/agent_insight_sdk/session_sdk.py` — `DEFAULT_PRICING`（SDK 侧估算 session 总成本）
- `backend/app/kafka/consumer.py` — `MODEL_PRICING` / `DEFAULT_PRICING`（后端写入 `llm_metrics.cost_usd`）

**匹配策略必须保持一致**：按 key 长度降序对 `model_name` 做**前缀匹配**，长 key 优先（`gpt-5.4-mini` 必须先于 `gpt-5.4` 命中，避免短 key 误用更高单价）；大小写不敏感；未命中走兜底价。

**违反后果**：SDK 估算的 session 成本与后端落库的 metrics 成本不一致，Dashboard 同一笔数据出现两个价格。

---

## 3. Kafka Producer 必须非阻塞投递

`backend/app/kafka/producer.py` 的 `send_batch` **必须用 `send()` + `add_done_callback`**，禁止改回 `send_and_wait()`。

- 回调中只记录日志，**不向上抛异常**——SDK 侧有重试兜底，Collector 必须保持快速返回路径。
- 回调的成功/失败分支通过 `future.exception() is None` 判定。

**违反后果**：高并发下 `send_and_wait` 阻塞事件循环，Collector 退化为串行，吞吐崩溃。

---

## 4. ClickHouse 写入重试耗尽后丢弃，不抛异常

`backend/app/clickhouse/client.py` 的 `_retry_insert`：
- 仅对 `clickhouse_driver.errors.Error` 重试，指数退避 `1s → 2s → 4s`，最多 3 次。
- 重试耗尽后**记录错误日志并丢弃该批数据**，**不向上抛**——保护 Consumer 主循环不被一批坏数据拖死。
- 非 ClickHouse 异常（如 `ValueError`）**不重试**，直接传播。

**违反后果**：把写入失败抛到消费循环会导致 Consumer 崩溃，Kafka 堆积，全量数据停滞。

---

## 5. 查询 API 异常吞掉，返回 status=error，不返回 500

`backend/app/api/` 下所有查询接口（traces / sessions / prompts / tool-calls / metrics / leaderboard）：
- `try` 包住查询调用，异常时返回 `{"status": "error", "message": str(e), "data": []}` 且 **HTTP 200**。
- ClickHouse 不可用时前端仍能拿到结构化响应并提示，而非连接错误。

**违反后果**：前端 fetch 直接抛网络异常，页面白屏；且 `data` 字段缺失破坏前端类型契约。

> 注意：这是查询接口的约定。`POST /api/v1/collect` 相反——校验失败返回 400，Kafka 投递失败返回 500，**不吞异常**。

---

## 6. ClickHouse 聚合表必须用 AggregatingMergeTree + State/Merge

`docker/clickhouse/init.sql` 中 `model_stats_daily` 与 `tool_stats`：
- avg / max 等**非加性聚合**必须用 `avgState` / `maxState` 存储，查询时 `avgMerge` / `maxMerge` 还原。
- **禁止用 SummingMergeTree** 存 avg/max（合并时会错误累加）。
- 查询模板见 `backend/app/clickhouse/client.py` 的 `_LEADERBOARD_QUERIES`，已使用 `avgMerge(duration_ms_state)` 等。

**违反后果**：聚合数据在后台 merge 时被错误累加，排行榜/统计的 avg、max 数值随数据量增长而失真，且无法回滚。

---

## 7. SQL 必须全部参数化，禁止字符串拼接

`backend/app/clickhouse/client.py` 所有查询用 `%(name)s` 占位符 + params dict。`IN` 子句用 `%(m0)s, %(m1)s` 动态占位符（见 `query_metrics_compare`），不要用 f-string 拼 values。

**违反后果**：模型名等用户可控字符串引入 SQL 注入。

---

## 8. SDK 非侵入，不得阻塞用户业务代码

- `context.py` 用 `contextvars` 管理上下文，异步安全，不依赖全局可变状态。
- `AsyncBatchUploader` 用**有界队列（maxsize=10000）**：队列满时**丢弃 + 告警**，绝不阻塞 Agent 主流程。
- `LLMInterceptor.wrap(client)` / `@instrument` 装饰器不得在用户调用路径上同步执行网络 IO。

**违反后果**：观测系统反噬被观测系统，Agent 业务延迟被 SDK 拖大，违背"非侵入"承诺。

---

## 9. init.sql 仅首次启动生效，迁移走幂等 ALTER

`docker/clickhouse/init.sql` 只在 ClickHouse 数据卷**为空**（首次创建容器）时执行。已有数据的库升级表结构必须：
- 手动执行 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`（幂等，可重复执行）。
- 在 `README.md` / `ARCHITECTURE.md` 的"升级迁移"小节补充对应 ALTER 语句。

**违反后果**：改了 init.sql 却没提供迁移语句，已有用户升级后服务启动报 `Unknown column`，且无文档可循。

---

## 10. 后端表 Schema 扩展走 _SPECS 注册表，不复制粘贴模板

`backend/app/clickhouse/client.py` 通过 `_SPECS: Dict[str, TableSpec]` 描述每张表的写入列/默认值/查询列/时间列。新增表只需在 `_SPECS` 加一项，复用 `_bulk_insert` / `_select_by_filter_or_recent` 通用路径，**不要为新表复制一份 insert/query 模板代码**。

**违反后果**：代码重复，后续改写入/重试逻辑时漏改某张表。

---

## 11. SDK Provider Adapter 模式不可破坏

新增 LLM 厂商必须继承 `sdk/agent_insight_sdk/providers/base.py` 的 `BaseProviderAdapter`，实现 `supports()` / `_wrap_call()` / `_unwrap_client()`（`extract()` 有默认实现，OpenAI 兼容格式可复用）。`LLMInterceptor` 通过扫描已注册 Adapter 自动匹配，**不要在拦截器里写 if-else 厂商分支**。

**违反后果**：新增厂商需要在多处改动，失去 Adapter 模式的可扩展性。

---

## 12. 依赖方向单向，禁止反向 import

- 后端不得 `import` SDK 代码（后端只通过 HTTP 契约接收 SDK 数据）。
- 前端不得假设后端存储细节，只依赖查询 API 的 JSON 响应。
- SDK 不得 import 后端内部模块，只通过 `AsyncBatchUploader` 的 HTTP POST 上报。

**违反后果**：层间耦合，无法独立部署/测试，打包体积膨胀。
