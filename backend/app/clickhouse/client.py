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
