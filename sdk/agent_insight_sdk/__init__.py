"""
Agent Insight SDK - AI Agent 可观测性探针 SDK

提供非侵入式的 LLM 调用拦截、链路追踪和性能指标采集能力。

核心功能：
- TraceContext: 上下文管理 (contextvars)
- OpenAIInterceptor: LLM 调用自动拦截
- StreamMonitor: 流式响应监控 (prefill/decode/TPS)
- ToolSDK: Tool 调用自动埋点
- TraceAPI: startTrace/startSpan/endSpan 显式 API
- AsyncBatchUploader: 异步批量上报
"""

from .context import TraceContext, get_current_context, set_current_context, clear_current_context
from .interceptor import OpenAIInterceptor
from .stream_monitor import StreamMonitor, MonitoredStream
from .tool_sdk import ToolSDK
from .trace_api import TraceAPI, SpanContext
from .uploader import AsyncBatchUploader, SpanData

__version__ = "0.2.0"
__all__ = [
    # 上下文管理
    "TraceContext",
    "get_current_context",
    "set_current_context",
    "clear_current_context",
    # LLM 拦截
    "OpenAIInterceptor",
    # 流式监控
    "StreamMonitor",
    "MonitoredStream",
    # Tool SDK
    "ToolSDK",
    # Trace API
    "TraceAPI",
    "SpanContext",
    # 上报器
    "AsyncBatchUploader",
    "SpanData",
]
