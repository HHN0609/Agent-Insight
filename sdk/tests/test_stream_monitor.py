"""
StreamMonitor / MonitoredStream 单元测试
"""

from unittest.mock import MagicMock

from agent_insight_sdk import MonitoredStream, StreamMonitor


class _MockChunk:
    """模拟 OpenAI 流式 chunk"""

    def __init__(self, content: str):
        self.choices = [MagicMock(delta=MagicMock(content=content))]


def test_stream_monitor_metrics():
    monitor = StreamMonitor()
    monitor.record_start()

    # 模拟第一个 chunk
    monitor.record_first_chunk()
    monitor.record_chunk(_MockChunk("hello"))
    monitor.record_chunk(_MockChunk(" world"))

    metrics = monitor.get_metrics()

    assert metrics.prefill_ms >= 0
    assert metrics.decode_ms >= 0
    assert metrics.output_tokens > 0
    assert metrics.tps >= 0


def test_stream_monitor_with_usage():
    monitor = StreamMonitor()
    monitor.record_start()
    monitor.record_first_chunk()

    usage = MagicMock(completion_tokens=42)
    monitor.record_stream_usage(usage)

    metrics = monitor.get_metrics()
    assert metrics.output_tokens == 42


def test_monitored_stream_iteration():
    raw_stream = iter([_MockChunk("a"), _MockChunk("b"), _MockChunk("c")])
    monitor = StreamMonitor()
    monitor.record_start()

    monitored = MonitoredStream(raw_stream, monitor)
    chunks = list(monitored)

    assert len(chunks) == 3
    metrics = monitor.get_metrics()
    assert metrics.output_tokens > 0
    assert metrics.prefill_ms >= 0


def test_monitored_stream_empty():
    raw_stream = iter([])
    monitor = StreamMonitor()
    monitor.record_start()

    monitored = MonitoredStream(raw_stream, monitor)
    chunks = list(monitored)

    assert chunks == []
    metrics = monitor.get_metrics()
    assert metrics.output_tokens == 0
