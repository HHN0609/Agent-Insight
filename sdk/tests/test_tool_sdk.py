"""
ToolSDK 单元测试
"""

import asyncio
import json

import pytest

from agent_insight_sdk import ToolSDK, clear_current_context, set_current_context
from agent_insight_sdk.context import TraceContext


@pytest.mark.asyncio
async def test_tool_sdk_sync(fake_uploader):
    tool_sdk = ToolSDK(fake_uploader)

    @tool_sdk.instrument(name="calculator", tool_type="math")
    def calculator(expression: str) -> float:
        return eval(expression)

    root = TraceContext(name="agent_task")
    set_current_context(root)

    result = calculator("2 + 3")
    await asyncio.sleep(0.05)

    assert result == 5
    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["tool_name"] == "calculator"
    assert tool_spans[0]["tool_type"] == "math"
    assert tool_spans[0]["status"] == "success"

    # 解析 input_data JSON 后验证结构，避免依赖序列化空格格式
    input_data = json.loads(tool_spans[0]["input_data"])
    assert input_data["args"] == ["2 + 3"]
    assert input_data["kwargs"] == {}

    clear_current_context()


@pytest.mark.asyncio
async def test_tool_sdk_async(fake_uploader):
    tool_sdk = ToolSDK(fake_uploader)

    @tool_sdk.instrument(name="weather", tool_type="api")
    async def weather(city: str) -> dict:
        return {"city": city, "temp": 25}

    root = TraceContext(name="agent_task")
    set_current_context(root)

    result = await weather("Beijing")
    await asyncio.sleep(0.05)

    assert result == {"city": "Beijing", "temp": 25}
    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["tool_name"] == "weather"
    assert tool_spans[0]["status"] == "success"

    clear_current_context()


@pytest.mark.asyncio
async def test_tool_sdk_error(fake_uploader):
    tool_sdk = ToolSDK(fake_uploader)

    @tool_sdk.instrument(name="fail", tool_type="generic")
    def fail_tool():
        raise ValueError("boom")

    root = TraceContext(name="agent_task")
    set_current_context(root)

    with pytest.raises(ValueError):
        fail_tool()

    await asyncio.sleep(0.05)

    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["status"] == "error"
    assert "boom" in tool_spans[0]["error"]

    clear_current_context()


def test_tool_sdk_default_name(fake_uploader):
    tool_sdk = ToolSDK(fake_uploader)

    @tool_sdk.instrument()
    def my_tool():
        return 1

    root = TraceContext(name="agent_task")
    set_current_context(root)

    my_tool()
    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert tool_spans[0]["tool_name"] == "my_tool"

    clear_current_context()


@pytest.mark.asyncio
async def test_tool_sdk_no_parent_context(fake_uploader):
    """无父上下文时 ToolSDK 应独立创建 trace，不抛异常"""
    tool_sdk = ToolSDK(fake_uploader)

    @tool_sdk.instrument(name="standalone", tool_type="util")
    def standalone_tool(x: int) -> int:
        return x * 2

    clear_current_context()
    result = standalone_tool(21)
    await asyncio.sleep(0.05)

    assert result == 42
    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["tool_name"] == "standalone"
    assert tool_spans[0]["parent_span_id"] == ""  # None → 空字符串

    clear_current_context()


@pytest.mark.asyncio
async def test_tool_sdk_kwargs_in_input(fake_uploader):
    """kwargs 应正确出现在 input_data 中"""
    tool_sdk = ToolSDK(fake_uploader)

    @tool_sdk.instrument(name="search")
    def search(query: str, limit: int = 10, filter: str = "all") -> dict:
        return {"query": query, "limit": limit}

    root = TraceContext(name="agent_task")
    set_current_context(root)

    search("python", limit=5, filter="recent")
    await asyncio.sleep(0.05)

    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert len(tool_spans) == 1
    input_data = json.loads(tool_spans[0]["input_data"])
    assert input_data["args"] == ["python"]
    assert input_data["kwargs"] == {"limit": 5, "filter": "recent"}

    # output_data 也应正确序列化
    output_data = json.loads(tool_spans[0]["output_data"])
    assert output_data == {"query": "python", "limit": 5}

    clear_current_context()


@pytest.mark.asyncio
async def test_tool_sdk_output_serialization_fallback(fake_uploader):
    """无法 JSON 序列化的对象应 fallback 到 str"""
    tool_sdk = ToolSDK(fake_uploader)

    class NonSerializable:
        def __str__(self):
            return "<non-serializable>"

    @tool_sdk.instrument(name="weird")
    def weird_tool():
        return NonSerializable()

    root = TraceContext(name="agent_task")
    set_current_context(root)

    result = weird_tool()
    await asyncio.sleep(0.05)

    assert isinstance(result, NonSerializable)
    tool_spans = [s for s in fake_uploader.spans if s["span_type"] == "tool_call"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["status"] == "success"
    # output_data 应该是 str fallback
    assert "<non-serializable>" in tool_spans[0]["output_data"]

    clear_current_context()
