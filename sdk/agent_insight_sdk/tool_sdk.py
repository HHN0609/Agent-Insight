"""
Tool SDK 模块 - 自动记录 Tool 调用

封装 Tool 调用，自动记录输入、输出、异常、耗时。
业务代码无需手动传递 TraceId/SpanId。
"""

import asyncio
import functools
import time
from datetime import datetime
from typing import Any, Callable, Optional

from .context import TraceContext, get_current_context, set_current_context
from .uploader import AsyncBatchUploader, SpanData


class ToolSDK:
    """Tool 调用自动埋点装饰器"""

    def __init__(self, uploader: AsyncBatchUploader):
        self._uploader = uploader

    def instrument(self, name: str = "", tool_type: str = "generic"):
        """
        装饰器：自动记录 Tool 调用

        用法：
            tool_sdk = ToolSDK(uploader)

            @tool_sdk.instrument(name="calculator", tool_type="calculator")
            def calculator(expression: str) -> float:
                return eval(expression)

            @tool_sdk.instrument(name="weather_query", tool_type="api")
            async def weather_query(city: str) -> dict:
                return await fetch_weather(city)
        """
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self._record_sync(func, tool_name, tool_type, args, kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._record_async(func, tool_name, tool_type, args, kwargs)

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def _record_sync(
        self,
        func: Callable,
        tool_name: str,
        tool_type: str,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        """记录同步 Tool 调用"""
        parent_ctx = get_current_context()
        if parent_ctx:
            ctx = parent_ctx.create_child(f"tool:{tool_name}")
        else:
            ctx = TraceContext(name=f"tool:{tool_name}")

        set_current_context(ctx)

        start_time = datetime.utcnow()
        perf_start = time.perf_counter()

        # 记录输入
        input_data = self._safe_serialize({"args": args, "kwargs": kwargs})

        try:
            result = func(*args, **kwargs)
            end_time = datetime.utcnow()
            duration_ms = (time.perf_counter() - perf_start) * 1000

            # 记录输出
            output_data = self._safe_serialize(result)

            self._report_tool_span(
                ctx, tool_name, tool_type,
                start_time, end_time, duration_ms,
                input_data, output_data, status="success",
            )

            return result

        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = (time.perf_counter() - perf_start) * 1000

            self._report_tool_span(
                ctx, tool_name, tool_type,
                start_time, end_time, duration_ms,
                input_data, str(e), status="error",
                error=str(e),
            )
            raise

    async def _record_async(
        self,
        func: Callable,
        tool_name: str,
        tool_type: str,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        """记录异步 Tool 调用"""
        parent_ctx = get_current_context()
        if parent_ctx:
            ctx = parent_ctx.create_child(f"tool:{tool_name}")
        else:
            ctx = TraceContext(name=f"tool:{tool_name}")

        set_current_context(ctx)

        start_time = datetime.utcnow()
        perf_start = time.perf_counter()

        input_data = self._safe_serialize({"args": args, "kwargs": kwargs})

        try:
            result = await func(*args, **kwargs)
            end_time = datetime.utcnow()
            duration_ms = (time.perf_counter() - perf_start) * 1000

            output_data = self._safe_serialize(result)

            self._report_tool_span(
                ctx, tool_name, tool_type,
                start_time, end_time, duration_ms,
                input_data, output_data, status="success",
            )

            return result

        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = (time.perf_counter() - perf_start) * 1000

            self._report_tool_span(
                ctx, tool_name, tool_type,
                start_time, end_time, duration_ms,
                input_data, str(e), status="error",
                error=str(e),
            )
            raise

    def _report_tool_span(
        self,
        ctx: TraceContext,
        tool_name: str,
        tool_type: str,
        start_time: datetime,
        end_time: datetime,
        duration_ms: float,
        input_data: str,
        output_data: str,
        status: str,
        error: str = "",
    ) -> None:
        """上报 Tool 调用 span"""
        attributes = {
            "tool_name": tool_name,
            "tool_type": tool_type,
            "input": input_data,
            "output": output_data,
            "status": status,
            "duration_ms": duration_ms,
        }
        if error:
            attributes["error"] = error

        span = SpanData(
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            parent_span_id=ctx.parent_span_id,
            name=f"tool:{tool_name}",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            span_type="trace",
            attributes=attributes,
        )

        if asyncio.get_event_loop().is_running():
            asyncio.create_task(self._uploader.submit(span))
        else:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._uploader.submit(span))
            loop.close()

    @staticmethod
    def _safe_serialize(data: Any) -> str:
        """安全序列化数据为 JSON 字符串"""
        try:
            import json
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return str(data)
