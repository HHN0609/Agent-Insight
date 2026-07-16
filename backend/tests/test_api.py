"""
后端 API 测试脚本

测试 FastAPI 后端各接口是否正常工作。
"""

import asyncio
import httpx

API_BASE = "http://localhost:8000"


async def test_health():
    """测试健康检查"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        print("[PASS] /health - 健康检查正常")


async def test_collect():
    """测试数据收集接口"""
    test_data = [
        {
            "trace_id": "test-trace-001",
            "span_id": "test-span-001",
            "parent_span_id": "",
            "name": "test_agent",
            "start_time": "2026-06-28T10:00:00.000",
            "end_time": "2026-06-28T10:00:01.000",
            "span_type": "trace",
            "attributes": {"model": "gpt-5.4", "test": True},
        },
        {
            "trace_id": "test-trace-001",
            "span_id": "test-span-002",
            "parent_span_id": "test-span-001",
            "name": "llm_metrics",
            "start_time": "2026-06-28T10:00:00.100",
            "end_time": "2026-06-28T10:00:00.900",
            "span_type": "llm_metrics",
            "attributes": {
                "model_name": "gpt-5.4",
                "prefill_ms": 200,
                "decode_ms": 600,
                "input_tokens": 1000,
                "output_tokens": 500,
                "tps": 833.3,
            },
        },
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_BASE}/api/v1/collect", json=test_data)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["count"] == 2
        print(f"[PASS] /api/v1/collect - 接收 {data['count']} 条数据，返回 202")


async def test_traces():
    """测试链路查询接口"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/api/v1/traces")
        assert resp.status_code == 200
        data = resp.json()
        print(f"[PASS] /api/v1/traces - 查询到 {data.get('count', 0)} 条链路数据")


async def test_metrics_compare():
    """测试模型对比接口"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/api/v1/metrics/compare")
        assert resp.status_code == 200
        data = resp.json()
        print(f"[PASS] /api/v1/metrics/compare - 查询到 {data.get('count', 0)} 个模型数据")


async def main():
    """运行所有测试"""
    print("=== Agent-Insight 后端 API 测试 ===")
    print(f"后端地址: {API_BASE}")
    print()

    try:
        await test_health()
        await test_collect()
        await test_traces()
        await test_metrics_compare()
        print()
        print("=== 所有测试通过 ===")
    except httpx.ConnectError:
        print(f"[FAIL] 无法连接到后端服务 {API_BASE}")
        print("请确保后端服务已启动: cd backend && uvicorn app.main:app --reload")
    except AssertionError as e:
        print(f"[FAIL] 断言失败: {e}")
    except Exception as e:
        print(f"[FAIL] 测试出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())
