# 改动流程与跨模块同步清单

> 任务执行节奏：先读后写、小步推进、跨模块改动必须过同步清单。

## 通用执行原则

1. **先读后改**：改动任何文件前先 Read 理解上下文，不在没读过的代码上提修改建议。
2. **最小改动**：只做被要求的改动，不顺便重构、不补无关 docstring、不加未被请求的容错。bug 修复不清理周边代码。
3. **不假设、要验证**：不确定的影响面用 Grep/Search 确认，不靠猜。
4. **受阻即停**：同一失败不反复重试，换思路或用 AskUserQuestion 对齐。
5. **不擅自提交/推送**：除非用户明确要求，不执行 git commit / push；不执行 `--force` / `reset --hard` 等破坏性操作。

## 跨模块同步检查清单（核心）

以下改动会触及多个模块，提交前必须逐项确认：

### 改动 Token 定价表
- [ ] `sdk/agent_insight_sdk/session_sdk.py` 的 `DEFAULT_PRICING`
- [ ] `backend/app/kafka/consumer.py` 的 `MODEL_PRICING` / `DEFAULT_PRICING`
- [ ] 两处 key 集合、单价、匹配策略（长 key 前缀优先）完全一致
- [ ] `backend/README.md` 定价表小节同步更新
- [ ] 对应测试：`backend/tests/test_consumer.py` 的定价矩阵用例

### 新增 / 修改 span_type
- [ ] `sdk/agent_insight_sdk/uploader.py`（`SpanData` 字段与序列化分支）
- [ ] `backend/app/api/collect.py`（`REQUIRED_FIELDS`）
- [ ] `backend/app/kafka/consumer.py`（`PARSE_MAP` + `consume_loop` 分流）
- [ ] `docker/clickhouse/init.sql`（`CREATE TABLE`）
- [ ] 未知 span_type 仍回退 `trace`（保持向前兼容）
- [ ] 对应测试：`test_collect.py` 校验用例 + `test_consumer.py` 分发用例

### 改动 ClickHouse 表结构（加列等）
- [ ] `docker/clickhouse/init.sql` 改 `CREATE TABLE`
- [ ] `backend/app/clickhouse/client.py` 的 `_SPECS`（`insert_columns` / `insert_defaults` / `query_columns`）
- [ ] `backend/app/kafka/consumer.py` 对应 `parse_*` 增加字段映射
- [ ] 提供**幂等** `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` 迁移语句
- [ ] `README.md` / `ARCHITECTURE.md` 的"升级迁移"小节补充 ALTER
- [ ] 聚合表改 avg/max 用 `avgState`/`maxState`（不用 SummingMergeTree）

### 改动查询接口
- [ ] `backend/app/api/<name>.py` 路由 + 参数校验（`Query(..., ge=, le=)`）
- [ ] `backend/app/clickhouse/client.py` 对应 `query_*` 函数（参数化 SQL）
- [ ] 异常路径返回 `{"status":"error","message":...,"data":[]}` + HTTP 200
- [ ] `frontend/src/types.ts` 响应类型 + 对应页面消费
- [ ] `backend/tests/test_query_apis.py` 用例

### 新增 LLM 厂商
- [ ] `sdk/agent_insight_sdk/providers/` 新增 Adapter，继承 `BaseProviderAdapter`
- [ ] 在 `LLMInterceptor` 注册（保持扫描匹配，不加 if-else）
- [ ] `sdk/agent_insight_sdk/__init__.py` 按需导出
- [ ] 定价表若涉及新模型，按"改动定价表"清单同步两端
- [ ] `sdk/tests/test_providers.py` 用例 + 可选 `examples/example_custom_provider.py`

## 提交前自检命令

```bash
# Backend 测试（无需 Docker，秒级）
cd backend && python -m pytest -q

# SDK 测试
cd sdk && python -m pytest -q

# Frontend 类型检查（零错误）
cd frontend && npx tsc --noEmit

# 基础设施 SQL 语法（若改了 init.sql）
docker compose up -d clickhouse && docker logs agent-insight-clickhouse 2>&1 | grep -i error
```

## 提交信息风格

- 跟随仓库既有 commit 风格；不确定时先 `git log --oneline -5`。
- 描述"为什么"而非仅"做了什么"，例如 `fix(consumer): 兜底未知 span_type 回退 trace 避免丢数据` 优于 `update consumer.py`。
- 跨模块改动在 commit body 列出同步的文件与原因。

## 何时需要与维护者确认

- 任何想绕过 [invariants.md](./invariants.md) 硬约束的需求。
- 新增运行时依赖（`requirements.txt` / `package.json`）。
- 改动对外 API 路径或响应结构（会破坏 SDK / 前端契约）。
- 改动 ClickHouse 表 Engine 或物化视图定义（影响已落库数据）。
- 不确定时，停下来问，不要替用户做产品决策。
