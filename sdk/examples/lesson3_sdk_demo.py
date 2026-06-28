"""
第3课 - SDK 自动埋点 完整示例

展示三种使用方式：
1. OpenAIInterceptor 自动拦截（非侵入式）
2. ToolSDK 装饰器自动埋点（Tool 调用）
3. TraceAPI 显式 API（手动控制 Trace 生命周期）
"""

import asyncio
from datetime import datetime

from agent_insight_sdk import (
    AsyncBatchUploader,
    OpenAIInterceptor,
    ToolSDK,
    TraceAPI,
    TraceContext,
    set_current_context,
    get_current_context,
)


async def demo_interceptor():
    """演示1：OpenAIInterceptor 自动拦截 LLM 调用"""
    print("=" * 60)
    print("演示1：OpenAIInterceptor 自动拦截")
    print("=" * 60)

    uploader = AsyncBatchUploader(backend_url="http://localhost:8000")
    await uploader.start()

    # 注意：实际运行需要 OpenAI API Key
    # from openai import OpenAI
    # client = OpenAI(api_key="your-key")
    # interceptor = OpenAIInterceptor(uploader)
    # interceptor.patch(client)
    #
    # response = client.chat.completions.create(
    #     model="gpt-4",
    #     messages=[{"role": "user", "content": "Hello"}],
    # )
    # print(response.choices[0].message.content)
    #
    # interceptor.unpatch(client)

    print("（需要 OpenAI API Key 才能实际运行）")
    print("拦截器会自动记录：model, stream, tokens, latency, prefill_ms, decode_ms, TPS")

    await uploader.stop()


async def demo_tool_sdk():
    """演示2：ToolSDK 装饰器自动埋点 Tool 调用"""
    print("\n" + "=" * 60)
    print("演示2：ToolSDK 装饰器自动埋点")
    print("=" * 60)

    uploader = AsyncBatchUploader(backend_url="http://localhost:8000")
    await uploader.start()

    tool_sdk = ToolSDK(uploader)

    # 同步 Tool
    @tool_sdk.instrument(name="calculator", tool_type="calculator")
    def calculator(expression: str) -> float:
        """计算器 Tool"""
        return eval(expression)

    # 异步 Tool
    @tool_sdk.instrument(name="weather_query", tool_type="api")
    async def weather_query(city: str) -> dict:
        """天气查询 Tool"""
        await asyncio.sleep(0.3)  # 模拟 API 调用
        return {"city": city, "temperature": 25, "weather": "sunny"}

    # 创建根上下文
    root_ctx = TraceContext(name="agent_task")
    set_current_context(root_ctx)

    # 调用 Tool（自动记录输入、输出、耗时、异常）
    result1 = calculator("2 + 3 * 4")
    print(f"计算器结果: {result1}")

    result2 = await weather_query("Beijing")
    print(f"天气结果: {result2}")

    # 模拟 Tool 异常
    try:
        @tool_sdk.instrument(name="bad_tool", tool_type="generic")
        def bad_tool():
            raise ValueError("Tool 执行失败")

        bad_tool()
    except ValueError:
        print("Tool 异常已自动记录")

    await asyncio.sleep(1)  # 等待上报
    await uploader.stop()


async def demo_trace_api():
    """演示3：TraceAPI 显式 API 手动控制"""
    print("\n" + "=" * 60)
    print("演示3：TraceAPI 显式 API")
    print("=" * 60)

    uploader = AsyncBatchUploader(backend_url="http://localhost:8000")
    await uploader.start()

    api = TraceAPI(uploader)

    # 开始 Trace
    api.start_trace("user_query_123")

    # 开始 Span
    api.start_span("vector_search", attributes={"query": "machine learning"})
    await asyncio.sleep(0.12)  # 模拟向量检索
    api.end_span(attributes={"results_count": 10, "status": "success"})

    # 开始 Span
    api.start_span("llm_call", attributes={"model": "gpt-4"})
    await asyncio.sleep(0.5)  # 模拟 LLM 调用
    api.end_span(attributes={"input_tokens": 1500, "output_tokens": 800, "status": "success"})

    # 开始 Span
    api.start_span("code_executor", attributes={"language": "python"})
    await asyncio.sleep(0.35)  # 模拟代码执行
    api.end_span(attributes={"status": "success"})

    # 结束 Trace
    api.end_trace(attributes={"status": "completed", "total_steps": 3})

    await asyncio.sleep(1)  # 等待上报
    await uploader.stop()


async def main():
    """运行所有演示"""
    await demo_interceptor()
    await demo_tool_sdk()
    await demo_trace_api()

    print("\n" + "=" * 60)
    print("所有演示完成！")
    print("访问 http://localhost:3000 查看 Dashboard")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
