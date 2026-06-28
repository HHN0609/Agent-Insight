"""
ClickHouse 客户端 - 负责数据写入和查询
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from clickhouse_driver import Client as SyncClient
from clickhouse_driver import errors as ch_errors

from ..config import settings

logger = logging.getLogger(__name__)

# 使用线程池执行同步 ClickHouse 操作
_client: Optional[SyncClient] = None


def get_client() -> SyncClient:
    """获取 ClickHouse 客户端（单例）"""
    global _client
    if _client is None:
        _client = SyncClient(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            user=settings.clickhouse_user,
            password=settings.clickhouse_password,
        )
    return _client


async def insert_traces(data: List[Dict[str, Any]]) -> None:
    """批量插入 trace 数据"""
    if not data:
        return

    loop = asyncio.get_event_loop()

    def _insert():
        client = get_client()
        columns = [
            "trace_id",
            "span_id",
            "parent_span_id",
            "name",
            "start_time",
            "end_time",
            "attributes",
        ]
        values = [
            (
                d["trace_id"],
                d["span_id"],
                d["parent_span_id"],
                d["name"],
                d["start_time"],
                d["end_time"],
                d["attributes"],
            )
            for d in data
        ]
        client.execute(
            f"INSERT INTO agent_traces ({', '.join(columns)}) VALUES",
            values,
        )

    try:
        await loop.run_in_executor(None, _insert)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse insert traces error: {e}")
        raise


async def insert_metrics(data: List[Dict[str, Any]]) -> None:
    """批量插入 metrics 数据"""
    if not data:
        return

    loop = asyncio.get_event_loop()

    def _insert():
        client = get_client()
        columns = [
            "trace_id",
            "span_id",
            "model_name",
            "prefill_ms",
            "decode_ms",
            "input_tokens",
            "output_tokens",
            "tps",
            "cost_usd",
        ]
        values = [
            (
                d["trace_id"],
                d["span_id"],
                d["model_name"],
                d["prefill_ms"],
                d["decode_ms"],
                d["input_tokens"],
                d["output_tokens"],
                d["tps"],
                d["cost_usd"],
            )
            for d in data
        ]
        client.execute(
            f"INSERT INTO llm_metrics ({', '.join(columns)}) VALUES",
            values,
        )

    try:
        await loop.run_in_executor(None, _insert)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse insert metrics error: {e}")
        raise


async def insert_prompts(data: List[Dict[str, Any]]) -> None:
    """批量插入 prompt 日志数据"""
    if not data:
        return

    loop = asyncio.get_event_loop()

    def _insert():
        client = get_client()
        columns = [
            "trace_id",
            "span_id",
            "model_name",
            "prompt",
            "response",
            "input_tokens",
            "output_tokens",
            "latency_ms",
            "stream",
            "status",
            "error",
        ]
        values = [
            (
                d["trace_id"],
                d["span_id"],
                d.get("model_name", "unknown"),
                d.get("prompt", ""),
                d.get("response", ""),
                d.get("input_tokens", 0),
                d.get("output_tokens", 0),
                d.get("latency_ms", 0),
                d.get("stream", False),
                d.get("status", "success"),
                d.get("error", ""),
            )
            for d in data
        ]
        client.execute(
            f"INSERT INTO prompt_logs ({', '.join(columns)}) VALUES",
            values,
        )

    try:
        await loop.run_in_executor(None, _insert)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse insert prompts error: {e}")
        raise


async def insert_tool_calls(data: List[Dict[str, Any]]) -> None:
    """批量插入 tool 调用数据"""
    if not data:
        return

    loop = asyncio.get_event_loop()

    def _insert():
        client = get_client()
        columns = [
            "trace_id",
            "span_id",
            "tool_name",
            "tool_type",
            "input_data",
            "output_data",
            "duration_ms",
            "status",
            "error",
        ]
        values = [
            (
                d["trace_id"],
                d["span_id"],
                d.get("tool_name", "unknown"),
                d.get("tool_type", "generic"),
                d.get("input_data", "{}"),
                d.get("output_data", "{}"),
                d.get("duration_ms", 0),
                d.get("status", "success"),
                d.get("error", ""),
            )
            for d in data
        ]
        client.execute(
            f"INSERT INTO tool_calls ({', '.join(columns)}) VALUES",
            values,
        )

    try:
        await loop.run_in_executor(None, _insert)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse insert tool calls error: {e}")
        raise


async def insert_sessions(data: List[Dict[str, Any]]) -> None:
    """批量插入 session 数据"""
    if not data:
        return

    loop = asyncio.get_event_loop()

    def _insert():
        client = get_client()
        columns = [
            "session_id",
            "trace_id",
            "agent_name",
            "user_input",
            "final_response",
            "total_spans",
            "total_tokens",
            "total_cost_usd",
            "duration_ms",
            "status",
        ]
        values = [
            (
                d["session_id"],
                d["trace_id"],
                d.get("agent_name", ""),
                d.get("user_input", ""),
                d.get("final_response", ""),
                d.get("total_spans", 0),
                d.get("total_tokens", 0),
                d.get("total_cost_usd", 0),
                d.get("duration_ms", 0),
                d.get("status", "completed"),
            )
            for d in data
        ]
        client.execute(
            f"INSERT INTO sessions ({', '.join(columns)}) VALUES",
            values,
        )

    try:
        await loop.run_in_executor(None, _insert)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse insert sessions error: {e}")
        raise


async def query_traces(trace_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """查询 trace 数据"""
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()
        if trace_id:
            query = f"SELECT * FROM agent_traces WHERE trace_id = '{trace_id}' ORDER BY start_time"
        else:
            query = f"SELECT * FROM agent_traces ORDER BY start_time DESC LIMIT {limit}"
        result = client.execute(query)
        columns = [
            "trace_id",
            "span_id",
            "parent_span_id",
            "name",
            "start_time",
            "end_time",
            "duration_ms",
            "attributes",
            "created_at",
        ]
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query traces error: {e}")
        return []


async def query_prompts(trace_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """查询 prompt 日志"""
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()
        if trace_id:
            query = f"SELECT * FROM prompt_logs WHERE trace_id = '{trace_id}' ORDER BY created_at"
        else:
            query = f"SELECT * FROM prompt_logs ORDER BY created_at DESC LIMIT {limit}"
        result = client.execute(query)
        columns = [
            "trace_id",
            "span_id",
            "model_name",
            "prompt",
            "response",
            "input_tokens",
            "output_tokens",
            "latency_ms",
            "stream",
            "status",
            "error",
            "created_at",
        ]
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query prompts error: {e}")
        return []


async def query_tool_calls(trace_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """查询 tool 调用记录"""
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()
        if trace_id:
            query = f"SELECT * FROM tool_calls WHERE trace_id = '{trace_id}' ORDER BY created_at"
        else:
            query = f"SELECT * FROM tool_calls ORDER BY created_at DESC LIMIT {limit}"
        result = client.execute(query)
        columns = [
            "trace_id",
            "span_id",
            "tool_name",
            "tool_type",
            "input_data",
            "output_data",
            "duration_ms",
            "status",
            "error",
            "created_at",
        ]
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query tool calls error: {e}")
        return []


async def query_sessions(limit: int = 100, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询 session 列表"""
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()
        if agent_name:
            query = f"SELECT * FROM sessions WHERE agent_name = '{agent_name}' ORDER BY created_at DESC LIMIT {limit}"
        else:
            query = f"SELECT * FROM sessions ORDER BY created_at DESC LIMIT {limit}"
        result = client.execute(query)
        columns = [
            "session_id",
            "trace_id",
            "agent_name",
            "user_input",
            "final_response",
            "total_spans",
            "total_tokens",
            "total_cost_usd",
            "duration_ms",
            "status",
            "created_at",
        ]
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query sessions error: {e}")
        return []


async def query_metrics_compare(
    model_names: Optional[List[str]] = None,
    hours: int = 24,
) -> List[Dict[str, Any]]:
    """查询多模型效能对比数据"""
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()

        if model_names:
            model_filter = " OR ".join([f"model_name = '{m}'" for m in model_names])
            where_clause = f"WHERE ({model_filter})"
        else:
            where_clause = ""

        query = f"""
            SELECT
                model_name,
                count() as total_requests,
                avg(prefill_ms) as avg_prefill_ms,
                avg(decode_ms) as avg_decode_ms,
                avg(tps) as avg_tps,
                sum(input_tokens) as total_input_tokens,
                sum(output_tokens) as total_output_tokens,
                sum(cost_usd) as total_cost_usd
            FROM llm_metrics
            {where_clause}
            GROUP BY model_name
            ORDER BY total_requests DESC
        """
        result = client.execute(query)
        columns = [
            "model_name",
            "total_requests",
            "avg_prefill_ms",
            "avg_decode_ms",
            "avg_tps",
            "total_input_tokens",
            "total_output_tokens",
            "total_cost_usd",
        ]
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query metrics error: {e}")
        return []


async def query_leaderboard(
    metric: str = "slowest_tool",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    查询排行榜

    metric: slowest_tool | most_tokens | most_failed
    """
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()

        if metric == "slowest_tool":
            query = f"""
                SELECT tool_name, tool_type, total_calls,
                       avg_duration_ms, max_duration_ms, error_count, error_rate
                FROM tool_stats
                ORDER BY avg_duration_ms DESC
                LIMIT {limit}
            """
            columns = [
                "tool_name", "tool_type", "total_calls",
                "avg_duration_ms", "max_duration_ms", "error_count", "error_rate",
            ]
        elif metric == "most_tokens":
            query = f"""
                SELECT model_name,
                       sum(input_tokens) as total_input,
                       sum(output_tokens) as total_output,
                       sum(input_tokens) + sum(output_tokens) as total_tokens,
                       count() as request_count
                FROM llm_metrics
                GROUP BY model_name
                ORDER BY total_tokens DESC
                LIMIT {limit}
            """
            columns = [
                "model_name", "total_input", "total_output",
                "total_tokens", "request_count",
            ]
        elif metric == "most_failed":
            query = f"""
                SELECT tool_name, tool_type, total_calls, error_count,
                       error_rate, avg_duration_ms
                FROM tool_stats
                WHERE error_count > 0
                ORDER BY error_count DESC
                LIMIT {limit}
            """
            columns = [
                "tool_name", "tool_type", "total_calls",
                "error_count", "error_rate", "avg_duration_ms",
            ]
        else:
            return []

        result = client.execute(query)
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query leaderboard error: {e}")
        return []
