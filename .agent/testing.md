# 测试规范

> 核心原则：**测试不依赖真实中间件**。Kafka / ClickHouse 全部 mock 隔离，单测在无 Docker 环境下也能秒级跑完。

## 各层测试现状与栈

| 层 | 测试目录 | 框架 | 共享 fixture |
|----|---------|------|-------------|
| Backend | `backend/tests/` | pytest + pytest-asyncio + httpx | `backend/conftest.py`（ASGI 客户端） |
| SDK | `sdk/tests/` | pytest + pytest-asyncio | `sdk/tests/conftest.py`（`FakeUploader`） |
| Frontend | `frontend/` | （暂无单测）严格 `tsc` 作为类型防线 | - |

## 命名与组织

- 文件：`test_<被测模块>.py`，与被测模块一一对应。
- 函数：`test_<行为>`，用中文 docstring 说明覆盖的业务场景。
- 一个测试只验证一个行为，断言聚焦，避免"顺便测一堆"。

## Backend 测试规范

- **ASGI 直连，不启动服务**：用 `httpx.ASGITransport(app=app)` 直连 FastAPI，不触发 lifespan（从而不连真实 Kafka）。fixture 见 `backend/conftest.py` 的 `api_client`。
- **mock 外部依赖**：
  - `collect` 接口测试 patch `app.api.collect.send_batch`（`AsyncMock`）。
  - 查询接口测试 patch 对应的 `query_*` 函数。
  - ClickHouse 客户端测试 patch `get_client` 或 `_select`。
  - Kafka producer 测试 patch `AIOKafkaProducer`，直接赋值 `producer._producer = fake` 注入。
- **模块级单例必须复位**：用 `autouse=True` 的 fixture 在用例前后把 `producer._producer` / `ch._client` 置 None，避免用例间污染。
- **异步用例**加 `@pytest.mark.asyncio`，在 `backend/conftest.py` 中已配置。
- **边界与异常路径必测**：参数边界（422）、空输入（400）、依赖失败（500 或吞为 `status=error`）、重试耗尽丢弃。

## SDK 测试规范

- 用 `sdk/tests/conftest.py` 的 `FakeUploader` 替代真实 `AsyncBatchUploader`，`submit` 同步触发 observer，便于断言上报内容。
- 流式监控 / Provider Adapter 用 mock client，不发真实 LLM 请求。
- `example_*.py` 是可运行示例，不是单测；`test_agent_simulation.py` 上报模拟数据，属集成验证。

## 运行命令

```bash
# Backend（无需 Docker）
cd backend && python -m pytest -v

# SDK
cd sdk && python -m pytest -v

# Frontend 类型检查（零错误是硬指标）
cd frontend && npx tsc --noEmit
```

## 改动时

- **改业务逻辑必须同步更新或新增对应测试**，不让覆盖率回退。
- 修 bug 时优先补一个能复现该 bug 的用例（回归测试），再修。
- 不为未改动的代码补冗余测试；不为追求覆盖率写无意义断言。
- 测试数据用贴近真实的小数据集，明确字段含义，避免 magic number 无注释。
