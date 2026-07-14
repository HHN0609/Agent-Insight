"""
SessionSDK 单元测试

验证 Session 生命周期、自动聚合、成本估算。
"""

import asyncio
from typing import Any, Dict, List

import pytest

from agent_insight_sdk import SessionSDK, TraceAPI, clear_current_context, get_current_context
from agent_insight_sdk.uploader import SpanData


class _FakeUploader:
    """模拟上报器，同步调用观察者"""

    def __init__(self):
        self.spans: List[Dict[str, Any]] = []
        self._observers: List[Any] = []

    async def submit(self, span: SpanData) -> None:
        d = span.to_dict()
        self.spans.append(d)
        for obs in self._observers:
            if obs:
                obs(d)

    def add_observer(self, callback):
        self._observers.append(callback)
        return len(self._observers) - 1

    def remove_observer(self, observer_id: int) -> None:
        if 0 <= observer_id < len(self._observers):
            self._observers[observer_id] = None


@pytest.fixture
def uploader():
    return _FakeUploader()


@pytest.fixture
def session_sdk(uploader):
    return SessionSDK(uploader)


@pytest.mark.asyncio
async def test_start_session_sets_context(uploader, session_sdk):
    sess = session_sdk.start_session(name="test", agent_name="a", user_input="hi")

    assert sess.session_id is not None
    assert sess.session_id == sess.trace_context.trace_id
    assert get_current_context().trace_id == sess.session_id

    session_sdk.end_session(sess)
    clear_current_context()


@pytest.mark.asyncio
async def test_session_aggregation(uploader, session_sdk):
    trace = TraceAPI(uploader)
    sess = session_sdk.start_session(name="test", agent_name="a", user_input="hi")

    # tool span
    await uploader.submit(
        SpanData(
            trace_id=sess.session_id,
            span_id="span-tool",
            name="tool_call",
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:01",
            span_type="tool_call",
        )
    )

    # llm metrics span
    await uploader.submit(
        SpanData(
            trace_id=sess.session_id,
            span_id="span-llm",
            name="llm_metrics",
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:01",
            span_type="llm_metrics",
            attributes={
                "model_name": "gpt-4o-mini",
                "input_tokens": 1000,
                "output_tokens": 500,
            },
        )
    )

    session_sdk.end_session(sess, final_response="done", status="completed")
    await asyncio.sleep(0.05)

    session_spans = [s for s in uploader.spans if s["span_type"] == "session"]
    assert len(session_spans) == 1
    s = session_spans[0]

    assert s["trace_id"] == sess.session_id
    assert s["session_id"] == sess.session_id
    assert s["agent_name"] == "a"
    assert s["user_input"] == "hi"
    assert s["final_response"] == "done"
    assert s["status"] == "completed"
    assert s["total_spans"] == 2
    assert s["total_tokens"] == 1500
    # gpt-4o-mini: 1000 * 0.15/1M + 500 * 0.60/1M = 0.00045
    assert abs(s["total_cost_usd"] - 0.00045) < 1e-9
    assert s["duration_ms"] >= 0

    session_sdk.close()
    clear_current_context()


@pytest.mark.asyncio
async def test_session_context_manager(uploader):
    session_sdk = SessionSDK(uploader)

    with session_sdk.session(name="cm", agent_name="agent") as sess:
        assert get_current_context().trace_id == sess.session_id

    await asyncio.sleep(0.05)

    session_spans = [s for s in uploader.spans if s["span_type"] == "session"]
    assert len(session_spans) == 1
    assert session_spans[0]["total_spans"] == 0

    session_sdk.close()
    clear_current_context()


@pytest.mark.asyncio
async def test_custom_pricing(uploader):
    session_sdk = SessionSDK(
        uploader,
        pricing={"my-model": {"input": 1.0, "output": 2.0}},
    )
    sess = session_sdk.start_session(name="test")

    await uploader.submit(
        SpanData(
            trace_id=sess.session_id,
            span_id="span-llm",
            name="llm_metrics",
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:01",
            span_type="llm_metrics",
            attributes={
                "model_name": "my-model",
                "input_tokens": 1_000_000,
                "output_tokens": 500_000,
            },
        )
    )

    session_sdk.end_session(sess)
    await asyncio.sleep(0.05)

    s = [s for s in uploader.spans if s["span_type"] == "session"][0]
    assert abs(s["total_cost_usd"] - (1.0 + 1.0)) < 1e-9

    session_sdk.close()
    clear_current_context()
