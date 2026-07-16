# 代码规范与扩展范式

> 风格目标是"与周边代码一致"，而非引入新范式。本文件列出已落地的约定，改动时遵循既有风格。

## 通用

- **注释与 docstring 用中文**（仓库既有风格，README/ARCHITECTURE/各模块 docstring 均为中文）。代码注释解释"为什么"，不解释"是什么"。
- **不引入新依赖**前先确认 `requirements.txt` / `package.json` / `setup.py` 是否已包含同类能力。
- **不创建无用文件**：优先编辑现有文件，不主动新建 README/文档 unless 明确要求。

---

## Python（SDK + Backend 共用）

### 异步优先

- IO 操作（HTTP / Kafka / ClickHouse）一律 `async def`。
- **同步驱动**（如 `clickhouse-driver`）通过 `asyncio.to_thread` 包装为非阻塞调用，**不要**用 `run_in_executor` 包 async 函数（会产生未被 await 的 coroutine，见 `client.py` 的 `_retry_insert` docstring 警告）。
- SDK 上报路径严禁 `await` 阻塞用户业务循环。

### 类型与签名

- 公共函数加类型注解（`typing` 系列）。
- 函数默认参数语义清晰时用 `Optional[X] = None`，不要用可变默认值。

### 模块级单例模式

- Kafka producer / consumer / ClickHouse client 用模块级全局变量 + `init_*` / `close_*` 生命周期函数（见 `producer.py` / `consumer.py` / `client.py`）。
- 测试时通过直接赋值模块全局变量（如 `producer._producer = fake`）注入 mock，配合 fixture 在用例结束复位。

### 扩展范式（按场景）

| 场景 | 扩展方式 | 不要 |
|------|---------|------|
| 新增 ClickHouse 表 | 在 `_SPECS` 加一项 `TableSpec`，复用 `_bulk_insert` / `_select_by_filter_or_recent` | 复制粘贴 insert/query 模板 |
| 新增查询接口 | `api/<name>.py` 定义 router，在 `main.py` `include_router` | 在 main.py 里直接写路由 |
| 新增 LLM 厂商 | 继承 `BaseProviderAdapter`，实现 3 个方法 | 在 `LLMInterceptor` 加 if-else |
| 新增 Tool 装饰器 | 参考 `tool_sdk.py` 既有三种装饰器 | |
| 新增 span_type | 同步 4 处（见 invariants.md #1） | 只改一端 |

---

## Backend 特定

- **配置**走 `app/config.py` 的 `Settings`（pydantic-settings），从环境变量读取，不硬编码。
- **路由**统一 `prefix="/api/v1"`，在 `main.py` 注册。
- **校验**在 `api/collect.py` 的 `validate_item` 集中维护 `REQUIRED_FIELDS`，按 `span_type` 分发。
- **日志**用模块级 `logger = logging.getLogger(__name__)`，错误用 `logger.error`，警告 `logger.warning`，不裸 `print`。
- **HTTP 状态码**：校验失败 400，Kafka 投递失败 500，查询异常吞为 200 + `status=error`（见 invariants.md #5）。

---

## Frontend（TypeScript + React）

- **严格 TypeScript**：`tsconfig.json` strict 模式，**零 `tsc` 错误**是硬指标（README 阶段6 已声明）。
- **类型集中**在 `src/types.ts`，新增实体在此定义 `interface`，不在组件内散落。
- **字段命名 snake_case**：后端返回 snake_case（如 `trace_id`、`total_cost_usd`），前端类型与组件**直接用 snake_case 对接**，不做 camelCase 转换，避免映射层 bug。
- **API 响应**统一 `ApiResponse<T>` 结构（`status` / `count` / `data` / `message`），组件据此判空。
- **样式**：深色主题，集中在 `index.css`，组件内联样式仅用于局部微调。
- **图表**用 Recharts，配色与既有页面一致。
- **路由**用 React Router v6，路由表在 `App.tsx`。

---

## SQL（ClickHouse）

- **全部参数化**：`%(name)s` 占位符 + params dict，`IN` 子句用 `%(m0)s, %(m1)s` 动态占位（见 invariants.md #7）。
- **时间过滤**查询带 `created_at >= now() - INTERVAL %(hours)s HOUR`，避免全表扫描。
- **聚合表查询**用 `avgMerge(state_col)` / `maxMerge(state_col)` 还原，不用裸 `avg()`（见 invariants.md #6）。
- **建表**在 `init.sql`，`CREATE TABLE IF NOT EXISTS`；改表结构同步提供幂等 `ALTER ... IF NOT EXISTS` 迁移语句（invariants.md #9）。

---

## 命名

- Python：`snake_case` 函数/变量，`PascalCase` 类，`UPPER_SNAKE` 常量（如 `MODEL_PRICING`、`BATCH_SIZE`）。
- 前端：组件 `PascalCase.tsx`， hooks/工具 `camelCase.ts`，类型 `PascalCase` 接口。
- 测试文件：`test_<被测模块>.py`，见 [testing.md](./testing.md)。
