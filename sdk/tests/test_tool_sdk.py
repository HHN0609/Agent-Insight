"""
ToolSDK 单元测试
"""

import asyncio

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
    assert '"args": ["2 + 3"]' in tool_spans[0]["input_data"]

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
