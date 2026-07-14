"""
SessionSDK 单元测试

验证 Session 生命周期、自动聚合、成本估算。
"""

import asyncio

import pytest

from agent_insight_sdk import SessionSDK, TraceAPI, clear_current_context, get_current_context
from agent_insight_sdk.uploader import SpanData


@pytest.mark.asyncio
async def test_start_session_sets_context(fake_uploader):
    session_sdk = SessionSDK(fake_uploader)
    sess = session_sdk.start_session(name="test", agent_name="a", user_input="hi")

    assert sess.session_id is not None
    assert sess.session_id == sess.trace_context.trace_id
    assert get_current_context().trace_id == sess.session_id

    session_sdk.end_session(sess)
    clear_current_context()


@pytest.mark.asyncio
async def test_session_aggregation(fake_uploader):
    trace = TraceAPI(fake_uploader)
    session_sdk = SessionSDK(fake_uploader)
    sess = session_sdk.start_session(name="test", agent_name="a", user_input="hi")

    # tool span
    await fake_uploader.submit(
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
    await fake_uploader.submit(
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

    session_spans = [s for s in fake_uploader.spans if s["span_type"] == "session"]
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
async def test_session_context_manager(fake_uploader):
    session_sdk = SessionSDK(fake_uploader)

    with session_sdk.session(name="cm", agent_name="agent") as sess:
        assert get_current_context().trace_id == sess.session_id

    await asyncio.sleep(0.05)

    session_spans = [s for s in fake_uploader.spans if s["span_type"] == "session"]
    assert len(session_spans) == 1
    assert session_spans[0]["total_spans"] == 0

    session_sdk.close()
    clear_current_context()


@pytest.mark.asyncio
async def test_custom_pricing(fake_uploader):
    session_sdk = SessionSDK(
        fake_uploader,
        pricing={"my-model": {"input": 1.0, "output": 2.0}},
    )
    sess = session_sdk.start_session(name="test")

    await fake_uploader.submit(
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

    s = [s for s in fake_uploader.spans if s["span_type"] == "session"][0]
    assert abs(s["total_cost_usd"] - (1.0 + 1.0)) < 1e-9

    session_sdk.close()
    clear_current_context()
