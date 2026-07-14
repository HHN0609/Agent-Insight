"""
Provider Adapter / LLMInterceptor 单元测试
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from agent_insight_sdk import LLMInterceptor, clear_current_context, set_current_context
from agent_insight_sdk.context import TraceContext


class _FakeOpenAIClient:
    """模拟 OpenAI 兼容客户端"""

    def __init__(self, response):
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock(return_value=response)


class _FakeAnthropicClient:
    """模拟 Anthropic 客户端"""

    def __init__(self, response):
        self.messages = MagicMock()
        self.messages.create = MagicMock(return_value=response)


@pytest.mark.asyncio
async def test_openai_compatible_interceptor_non_stream(fake_uploader):
    response = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 20
    response.choices = [MagicMock(message=MagicMock(content="hello"))]

    client = _FakeOpenAIClient(response)
    interceptor = LLMInterceptor(fake_uploader)
    wrapped = interceptor.wrap(client)

    root = TraceContext(name="agent_task")
    set_current_context(root)

    result = wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )

    await asyncio.sleep(0.05)

    assert result is response

    trace_spans = [s for s in fake_uploader.spans if s["span_type"] == "trace"]
    metrics_spans = [s for s in fake_uploader.spans if s["span_type"] == "llm_metrics"]
    prompt_spans = [s for s in fake_uploader.spans if s["span_type"] == "prompt"]

    assert len(trace_spans) == 1
    assert trace_spans[0]["attributes"]["model"] == "gpt-4o-mini"

    assert len(metrics_spans) == 1
    attrs = metrics_spans[0]["attributes"]
    assert attrs["input_tokens"] == 10
    assert attrs["output_tokens"] == 20
    assert attrs["model_name"] == "gpt-4o-mini"

    assert len(prompt_spans) == 1
    assert prompt_spans[0]["prompt"] == "hi"

    interceptor.unwrap()
    clear_current_context()


@pytest.mark.asyncio
async def test_anthropic_interceptor_non_stream(fake_uploader):
    response = MagicMock()
    response.usage.input_tokens = 5
    response.usage.output_tokens = 15
    response.content = [MagicMock(text="hello from claude")]

    client = _FakeAnthropicClient(response)
    interceptor = LLMInterceptor(fake_uploader)
    wrapped = interceptor.wrap(client)

    root = TraceContext(name="agent_task")
    set_current_context(root)

    result = wrapped.messages.create(
        model="claude-3-haiku",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
    )

    await asyncio.sleep(0.05)

    assert result is response

    metrics_spans = [s for s in fake_uploader.spans if s["span_type"] == "llm_metrics"]
    assert len(metrics_spans) == 1
    attrs = metrics_spans[0]["attributes"]
    assert attrs["input_tokens"] == 5
    assert attrs["output_tokens"] == 15
    assert attrs["model_name"] == "claude-3-haiku"

    interceptor.unwrap()
    clear_current_context()


@pytest.mark.asyncio
async def test_openai_stream_interceptor(fake_uploader):
    chunks = [
        MagicMock(
            choices=[MagicMock(delta=MagicMock(content="hello"))],
            usage=None,
        ),
        MagicMock(
            choices=[MagicMock(delta=MagicMock(content=" world"))],
            usage=None,
        ),
    ]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = MagicMock(return_value=iter(chunks))

    interceptor = LLMInterceptor(fake_uploader)
    wrapped = interceptor.wrap(client)

    root = TraceContext(name="agent_task")
    set_current_context(root)

    stream = wrapped.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "say hi"}],
        stream=True,
    )

    # 消费流
    content = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content

    await asyncio.sleep(0.05)

    assert content == "hello world"

    trace_spans = [s for s in fake_uploader.spans if s["span_type"] == "trace"]
    assert len(trace_spans) == 1
    assert trace_spans[0]["attributes"]["stream"] is True

    metrics_spans = [s for s in fake_uploader.spans if s["span_type"] == "llm_metrics"]
    assert len(metrics_spans) == 1
    attrs = metrics_spans[0]["attributes"]
    assert attrs["model_name"] == "gpt-4"
    assert attrs["output_tokens"] > 0

    interceptor.unwrap()
    clear_current_context()


def test_unsupported_client(fake_uploader):
    interceptor = LLMInterceptor(fake_uploader)
    with pytest.raises(ValueError):
        interceptor.wrap(object())
