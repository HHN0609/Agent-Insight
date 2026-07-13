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


async def _retry_insert(
    insert_fn, data: List[Dict[str, Any]], label: str, max_retries: int = 3
) -> None:
    """带指数退避重试的 ClickHouse 写入

    注意：insert_fn 必须是 async 函数（内部已通过 run_in_executor 执行同步 IO），
    不能再放进 run_in_executor，否则 async 函数只会在线程里产生一个
    未被 await 的 coroutine，数据实际不会写入。
    """
    if not data:
        return

    last_exc = None

    for attempt in range(max_retries):
        try:
            await insert_fn(data)
            return  # 成功
        except ch_errors.Error as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                logger.warning(
                    f"ClickHouse insert {label} attempt {attempt + 1} failed, "
                    f"retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)

    logger.error(
        f"ClickHouse insert {label} failed after {max_retries} attempts, "
        f"discarding {len(data)} records: {last_exc}"
    )


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
        col_sql = ", ".join(columns)
        if trace_id:
            result = client.execute(
                f"SELECT {col_sql} FROM agent_traces "
                "WHERE trace_id = %(tid)s ORDER BY start_time",
                {"tid": trace_id},
            )
        else:
            result = client.execute(
                f"SELECT {col_sql} FROM agent_traces "
                "ORDER BY start_time DESC LIMIT %(lim)s",
                {"lim": limit},
            )
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
        col_sql = ", ".join(columns)
        if trace_id:
            result = client.execute(
                f"SELECT {col_sql} FROM prompt_logs "
                "WHERE trace_id = %(tid)s ORDER BY created_at",
                {"tid": trace_id},
            )
        else:
            result = client.execute(
                f"SELECT {col_sql} FROM prompt_logs "
                "ORDER BY created_at DESC LIMIT %(lim)s",
                {"lim": limit},
            )
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
        col_sql = ", ".join(columns)
        if trace_id:
            result = client.execute(
                f"SELECT {col_sql} FROM tool_calls "
                "WHERE trace_id = %(tid)s ORDER BY created_at",
                {"tid": trace_id},
            )
        else:
            result = client.execute(
                f"SELECT {col_sql} FROM tool_calls "
                "ORDER BY created_at DESC LIMIT %(lim)s",
                {"lim": limit},
            )
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
        col_sql = ", ".join(columns)
        if agent_name:
            result = client.execute(
                f"SELECT {col_sql} FROM sessions "
                "WHERE agent_name = %(an)s ORDER BY created_at DESC LIMIT %(lim)s",
                {"an": agent_name, "lim": limit},
            )
        else:
            result = client.execute(
                f"SELECT {col_sql} FROM sessions "
                "ORDER BY created_at DESC LIMIT %(lim)s",
                {"lim": limit},
            )
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
    """查询多模型效能对比数据

    hours 参数用于限定查询时间范围（最近 N 小时），避免全表扫描。
    """
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()

        # 始终按 created_at 限定时间窗口，避免全表扫描
        conditions = ["created_at >= now() - INTERVAL %(hours)s HOUR"]
        params: Dict[str, Any] = {"hours": hours}

        if model_names:
            # 使用 IN + 参数化，避免 SQL 注入
            placeholders = ", ".join([f"%(m{i})s" for i in range(len(model_names))])
            conditions.append(f"model_name IN ({placeholders})")
            for i, m in enumerate(model_names):
                params[f"m{i}"] = m

        where_clause = "WHERE " + " AND ".join(conditions)

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
        result = client.execute(query, params)
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

    注意：tool_stats 使用 AggregatingMergeTree，avg/max 以 State 形式存储，
          查询时必须 GROUP BY 并用 avgMerge / maxMerge 还原。
    """
    loop = asyncio.get_event_loop()

    def _query():
        client = get_client()

        if metric == "slowest_tool":
            query = """
                SELECT
                    tool_name,
                    tool_type,
                    sum(total_calls) AS total_calls,
                    avgMerge(duration_ms_state) AS avg_duration_ms,
                    maxMerge(duration_ms_max_state) AS max_duration_ms,
                    sum(error_count) AS error_count,
                    sum(error_count) / sum(total_calls) AS error_rate
                FROM tool_stats
                GROUP BY tool_name, tool_type
                ORDER BY avg_duration_ms DESC
                LIMIT %(lim)s
            """
            params = {"lim": limit}
            columns = [
                "tool_name", "tool_type", "total_calls",
                "avg_duration_ms", "max_duration_ms", "error_count", "error_rate",
            ]
        elif metric == "most_tokens":
            query = """
                SELECT
                    model_name,
                    sum(input_tokens) AS total_input,
                    sum(output_tokens) AS total_output,
                    sum(input_tokens) + sum(output_tokens) AS total_tokens,
                    count() AS request_count
                FROM llm_metrics
                GROUP BY model_name
                ORDER BY total_tokens DESC
                LIMIT %(lim)s
            """
            params = {"lim": limit}
            columns = [
                "model_name", "total_input", "total_output",
                "total_tokens", "request_count",
            ]
        elif metric == "most_failed":
            query = """
                SELECT
                    tool_name,
                    tool_type,
                    sum(total_calls) AS total_calls,
                    sum(error_count) AS error_count,
                    sum(error_count) / sum(total_calls) AS error_rate,
                    avgMerge(duration_ms_state) AS avg_duration_ms
                FROM tool_stats
                GROUP BY tool_name, tool_type
                HAVING error_count > 0
                ORDER BY error_count DESC
                LIMIT %(lim)s
            """
            params = {"lim": limit}
            columns = [
                "tool_name", "tool_type", "total_calls",
                "error_count", "error_rate", "avg_duration_ms",
            ]
        else:
            return []

        result = client.execute(query, params)
        return [dict(zip(columns, row)) for row in result]

    try:
        return await loop.run_in_executor(None, _query)
    except ch_errors.Error as e:
        logger.error(f"ClickHouse query leaderboard error: {e}")
        return []
