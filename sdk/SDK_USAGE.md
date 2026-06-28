# Agent Insight SDK 使用指南

## 概述

Agent Insight SDK 是一个轻量级的 Python 探针库，用于自动采集 AI Agent 的调用链路和性能指标。SDK 采用非侵入式设计，能够自动拦截 OpenAI 客户端调用，支持同步和异步场景。

## 核心架构

```
┌─────────────────────────────────────────────────────────┐
│                    你的 Agent 应用                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  OpenAI Client (chat.completions.create)         │  │
│  └────────────┬─────────────────────────────────────┘  │
│               │                                         │
│  ┌────────────▼─────────────────────────────────────┐  │
│  │  OpenAIInterceptor (自动拦截)                     │  │
│  │  - 捕获调用参数 (model, stream, tokens)          │  │
│  │  - 记录时间戳 (start_time, end_time)             │  │
│  │  - 监控流式响应 (prefill_ms, decode_ms)          │  │
│  └────────────┬─────────────────────────────────────┘  │
│               │                                         │
│  ┌────────────▼─────────────────────────────────────┐  │
│  │  AsyncBatchUploader (异步批量上报)                │  │
│  │  - asyncio.Queue 内存队列                        │  │
│  │  - 每 500ms 或满 20 条触发上报                   │  │
│  │  - httpx 异步 POST 到后端                        │  │
│  └────────────┬─────────────────────────────────────┘  │
└───────────────┼─────────────────────────────────────────┘
                │
                ▼
        FastAPI Backend → Kafka → ClickHouse
```

## 安装

```bash
cd sdk
pip install -e .
```

## 快速开始

### 1. 基础用法（同步场景）

```python
import asyncio
from openai import OpenAI
from agent_insight_sdk import AsyncBatchUploader, OpenAIInterceptor

async def main():
    # 1. 初始化上报器
    uploader = AsyncBatchUploader(
        backend_url="http://localhost:8000",
        batch_size=20,        # 每 20 条触发上报
        flush_interval=0.5,   # 每 500ms 触发上报
    )
    await uploader.start()

    # 2. 创建 OpenAI 客户端并打桩
    client = OpenAI(api_key="your-api-key")
    interceptor = OpenAIInterceptor(uploader)
    interceptor.patch(client)

    # 3. 正常调用 OpenAI API（自动采集）
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.choices[0].message.content)

    # 4. 流式调用（自动采集 prefill/decode 时间）
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Tell me a story"}],
        stream=True,
    )
    for chunk in stream:
        print(chunk.choices[0].delta.content, end="")

    # 5. 清理
    await asyncio.sleep(1)  # 等待上报完成
    await uploader.stop()
    interceptor.unpatch(client)

asyncio.run(main())
```

### 2. 异步场景（推荐）

```python
import asyncio
from openai import AsyncOpenAI
from agent_insight_sdk import AsyncBatchUploader, OpenAIInterceptor

async def main():
    uploader = AsyncBatchUploader(backend_url="http://localhost:8000")
    await uploader.start()

    client = AsyncOpenAI(api_key="your-api-key")
    interceptor = OpenAIInterceptor(uploader)
    interceptor.patch(client)

    # 并发调用多个 LLM
    tasks = [
        client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": f"Question {i}"}],
        )
        for i in range(5)
    ]
    responses = await asyncio.gather(*tasks)

    await asyncio.sleep(1)
    await uploader.stop()

asyncio.run(main())
```

### 3. Agent 工具调用场景

```python
import asyncio
import time
from datetime import datetime
from agent_insight_sdk import (
    AsyncBatchUploader,
    TraceContext,
    get_current_context,
    set_current_context,
)
from agent_insight_sdk.uploader import SpanData

async def simulate_tool_call(name: str, duration_ms: float, uploader: AsyncBatchUploader):
    """模拟工具调用并上报 span"""
    ctx = get_current_context()
    tool_ctx = ctx.create_child(name)
    set_current_context(tool_ctx)

    start_time = datetime.utcnow()
    await asyncio.sleep(duration_ms / 1000.0)
    end_time = datetime.utcnow()

    span = SpanData(
        trace_id=tool_ctx.trace_id,
        span_id=tool_ctx.span_id,
        parent_span_id=tool_ctx.parent_span_id,
        name=name,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        span_type="trace",
        attributes={"tool": name, "status": "success"},
    )
    await uploader.submit(span)

async def main():
    uploader = AsyncBatchUploader(backend_url="http://localhost:8000")
    await uploader.start()

    # 创建根上下文
    root_ctx = TraceContext(name="agent_task")
    set_current_context(root_ctx)

    # 模拟 Agent 执行流程
    # 1. 向量检索
    await simulate_tool_call("vector_search", 120, uploader)

    # 2. 调用 LLM（通过拦截器自动采集）
    # ... OpenAI 调用代码 ...

    # 3. 代码执行
    await simulate_tool_call("code_executor", 350, uploader)

    # 4. 结果汇总
    await simulate_tool_call("result_aggregator", 80, uploader)

    await asyncio.sleep(1)
    await uploader.stop()

asyncio.run(main())
```

## 核心模块说明

### 1. TraceContext（上下文管理）

基于 Python `contextvars` 实现，保证异步环境下的上下文隔离。

```python
from agent_insight_sdk import TraceContext, get_current_context, set_current_context

# 创建根上下文
root_ctx = TraceContext(name="my_agent")
set_current_context(root_ctx)

# 创建子上下文（自动继承 trace_id）
child_ctx = root_ctx.create_child("tool_call")
set_current_context(child_ctx)

# 获取当前上下文
current = get_current_context()
print(f"trace_id: {current.trace_id}")
print(f"span_id: {current.span_id}")
print(f"parent_span_id: {current.parent_span_id}")
```

**关键特性**：
- `trace_id`：整个链路的唯一标识，所有子 span 共享
- `span_id`：当前 span 的唯一标识
- `parent_span_id`：父 span 的标识，用于构建调用树

### 2. OpenAIInterceptor（LLM 拦截器）

通过猴子补丁（Monkey Patch）拦截 OpenAI 客户端调用。

```python
from agent_insight_sdk import OpenAIInterceptor

# 打桩
interceptor = OpenAIInterceptor(uploader)
interceptor.patch(client)

# 恢复原始方法
interceptor.unpatch(client)
```

**自动采集的数据**：
- 模型名称（model）
- 是否流式（stream）
- 输入/输出 token 数
- 调用耗时（duration_ms）
- 流式场景：prefill_ms、decode_ms、TPS

### 3. StreamMonitor（流式监控）

专门用于监控流式响应的性能指标。

**计算公式**：
```
prefill_ms = first_chunk_time - start_time
decode_ms = last_chunk_time - first_chunk_time
TPS = output_tokens / (decode_ms / 1000)
```

**工作原理**：
1. 记录请求开始时间
2. 收到第一个 chunk 时计算 prefill_ms
3. 持续记录每个 chunk 的时间
4. 流结束时计算 decode_ms 和 TPS

### 4. AsyncBatchUploader（异步批量上报）

使用 `asyncio.Queue` 和后台任务实现高效上报。

```python
uploader = AsyncBatchUploader(
    backend_url="http://localhost:8000",
    batch_size=20,        # 批量阈值
    flush_interval=0.5,   # 时间阈值（秒）
)

# 启动后台上报任务
await uploader.start()

# 提交数据
await uploader.submit(span_data)

# 停止并刷新剩余数据
await uploader.stop()
```

**上报策略**：
- 每 500ms 检查一次队列
- 队列满 20 条时立即上报
- 调用 `stop()` 时刷新所有剩余数据

## 数据结构

### SpanData

```python
@dataclass
class SpanData:
    trace_id: str              # 链路 ID
    span_id: str               # 当前 span ID
    parent_span_id: str        # 父 span ID
    name: str                  # span 名称
    start_time: str            # ISO 格式时间戳
    end_time: str              # ISO 格式时间戳
    span_type: str             # "trace" 或 "llm_metrics"
    attributes: Dict[str, Any] # 附加属性
```

### Trace Span（链路追踪）

```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "parent_span_id": "",
  "name": "llm_call",
  "start_time": "2026-06-28T10:00:00.000",
  "end_time": "2026-06-28T10:00:02.500",
  "span_type": "trace",
  "attributes": {
    "model": "gpt-4",
    "stream": false
  }
}
```

### LLM Metrics Span（性能指标）

```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "parent_span_id": "",
  "name": "llm_metrics",
  "start_time": "2026-06-28T10:00:00.000",
  "end_time": "2026-06-28T10:00:02.500",
  "span_type": "llm_metrics",
  "attributes": {
    "model_name": "gpt-4",
    "prefill_ms": 500.0,
    "decode_ms": 2000.0,
    "input_tokens": 1500,
    "output_tokens": 800,
    "tps": 400.0
  }
}
```

## 高级用法

### 自定义 Span 属性

```python
from agent_insight_sdk.uploader import SpanData
from datetime import datetime

span = SpanData(
    trace_id="custom-trace-id",
    span_id="custom-span-id",
    parent_span_id="",
    name="custom_tool",
    start_time=datetime.utcnow().isoformat(),
    end_time=datetime.utcnow().isoformat(),
    span_type="trace",
    attributes={
        "tool": "vector_search",
        "query": "machine learning",
        "results_count": 10,
        "latency_ms": 120,
    },
)
await uploader.submit(span)
```

### 多模型对比测试

```python
async def compare_models(models: list[str], prompt: str):
    uploader = AsyncBatchUploader(backend_url="http://localhost:8000")
    await uploader.start()

    for model in models:
        ctx = TraceContext(name=f"test_{model}")
        set_current_context(ctx)

        client = OpenAI(api_key="your-key")
        interceptor = OpenAIInterceptor(uploader)
        interceptor.patch(client)

        # 流式调用
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            pass  # 消费流式响应

        interceptor.unpatch(client)

    await asyncio.sleep(2)
    await uploader.stop()

asyncio.run(compare_models(["gpt-4", "gpt-3.5-turbo", "claude-3-opus"], "Explain quantum computing"))
```

### 错误处理

```python
try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}],
    )
except Exception as e:
    # SDK 会自动记录错误 span
    print(f"Error: {e}")
    raise
```

错误 span 会自动包含错误信息：
```json
{
  "attributes": {
    "model": "gpt-4",
    "error": "Rate limit exceeded"
  }
}
```

## 性能优化建议

### 1. 批量大小调优

```python
# 高并发场景：增大批量
uploader = AsyncBatchUploader(batch_size=50, flush_interval=1.0)

# 低延迟场景：减小批量
uploader = AsyncBatchUploader(batch_size=5, flush_interval=0.2)
```

### 2. 异步上下文管理

```python
# ✅ 推荐：使用 async context manager
async with AsyncBatchUploader() as uploader:
    # 自动启动和停止
    pass

# ❌ 避免：忘记停止
uploader = AsyncBatchUploader()
await uploader.start()
# ... 使用 ...
# 忘记调用 await uploader.stop()
```

### 3. 避免阻塞事件循环

```python
# ✅ 推荐：异步提交
await uploader.submit(span)

# ❌ 避免：同步提交（会阻塞）
loop = asyncio.get_event_loop()
loop.run_until_complete(uploader.submit(span))
```

## 故障排查

### 问题 1：数据未上报

**检查点**：
1. 后端服务是否运行：`curl http://localhost:8000/health`
2. Kafka 是否运行：`docker ps | grep kafka`
3. 查看 SDK 日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 问题 2：流式指标不准确

**原因**：网络延迟或 chunk 大小不均

**解决**：
- 确保使用 `stream=True`
- 检查 OpenAI API 响应是否包含 usage 字段

### 问题 3：上下文丢失

**原因**：异步任务未正确传递上下文

**解决**：
```python
# ✅ 推荐：显式传递上下文
async def task(ctx: TraceContext):
    set_current_context(ctx)
    # ...

# ❌ 避免：依赖隐式传递
async def task():
    ctx = get_current_context()  # 可能为 None
```

## 完整示例

参考 `sdk/tests/test_agent_simulation.py`，该脚本模拟了一个完整的 Agent 执行流程：

1. 创建根上下文
2. 向量检索（工具调用）
3. GPT-4 非流式调用
4. 代码执行（工具调用）
5. Claude-3 流式调用
6. GPT-3.5 流式调用
7. 结果汇总（工具调用）

运行测试：
```bash
cd sdk
python tests/test_agent_simulation.py
```

## API 参考

### AsyncBatchUploader

| 方法 | 说明 |
|------|------|
| `__init__(backend_url, batch_size, flush_interval)` | 初始化上报器 |
| `start()` | 启动后台上报任务 |
| `stop()` | 停止并刷新剩余数据 |
| `submit(span: SpanData)` | 提交 span 到队列 |

### OpenAIInterceptor

| 方法 | 说明 |
|------|------|
| `__init__(uploader)` | 初始化拦截器 |
| `patch(client)` | 对 OpenAI 客户端打桩 |
| `unpatch(client)` | 恢复原始方法 |

### TraceContext

| 方法 | 说明 |
|------|------|
| `__init__(trace_id, span_id, parent_span_id, name)` | 创建上下文 |
| `create_child(name)` | 创建子上下文 |

### 全局函数

| 函数 | 说明 |
|------|------|
| `get_current_context()` | 获取当前上下文 |
| `set_current_context(ctx)` | 设置当前上下文 |
| `clear_current_context()` | 清除当前上下文 |

## 许可证

MIT
