"""
Kafka 消费者 - 消费原始日志并写入 ClickHouse
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from aiokafka import AIOKafkaConsumer

from ..config import settings
from ..clickhouse.client import (
    insert_traces,
    insert_metrics,
    insert_prompts,
    insert_tool_calls,
    insert_sessions,
)

logger = logging.getLogger(__name__)

_consumer: AIOKafkaConsumer = None
_consumer_task: asyncio.Task = None


async def start_consumer() -> None:
    """启动 Kafka 消费者"""
    global _consumer, _consumer_task

    try:
        _consumer = AIOKafkaConsumer(
            settings.kafka_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            max_poll_records=100,
        )
        await _consumer.start()
        logger.info(f"Kafka consumer started, topic: {settings.kafka_topic}")

        # 启动消费循环
        _consumer_task = asyncio.create_task(consume_loop())

    except Exception as e:
        logger.error(f"Failed to start Kafka consumer: {e}")
        raise


async def stop_consumer() -> None:
    """停止 Kafka 消费者"""
    global _consumer, _consumer_task

    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass

    if _consumer:
        await _consumer.stop()
        _consumer = None
        logger.info("Kafka consumer stopped")


async def consume_loop() -> None:
    """消费循环"""
    trace_batch: List[Dict[str, Any]] = []
    metrics_batch: List[Dict[str, Any]] = []
    batch_size = 50

    try:
        async for msg in _consumer:
            data = msg.value

            # 数据可能是一个批次
            if isinstance(data, list):
                for item in data:
                    process_item(item, trace_batch, metrics_batch)
            else:
                process_item(data, trace_batch, metrics_batch)

            # 达到批量阈值时写入 ClickHouse
            if len(trace_batch) >= batch_size:
                await flush_traces(trace_batch)
                trace_batch = []

            if len(metrics_batch) >= batch_size:
                await flush_metrics(metrics_batch)
                metrics_batch = []

    except asyncio.CancelledError:
        logger.info("Consumer loop cancelled")
    except Exception as e:
        logger.error(f"Error in consumer loop: {e}")
        raise


def process_item(
    item: Dict[str, Any],
    trace_batch: List[Dict[str, Any]],
    metrics_batch: List[Dict[str, Any]],
) -> None:
    """处理单条数据，分类到对应的批次"""
    span_type = item.get("span_type", "trace")

    if span_type == "llm_metrics":
        # 提取 llm_metrics 字段
        attrs = item.get("attributes", {})
        metrics_batch.append({
            "trace_id": item["trace_id"],
            "span_id": item["span_id"],
            "model_name": attrs.get("model_name", "unknown"),
            "prefill_ms": attrs.get("prefill_ms", 0),
            "decode_ms": attrs.get("decode_ms", 0),
            "input_tokens": attrs.get("input_tokens", 0),
            "output_tokens": attrs.get("output_tokens", 0),
            "tps": attrs.get("tps", 0),
            "cost_usd": calculate_cost(attrs.get("model_name", ""), attrs.get("input_tokens", 0), attrs.get("output_tokens", 0)),
        })
    else:
        # trace 数据
        trace_batch.append({
            "trace_id": item["trace_id"],
            "span_id": item["span_id"],
            "parent_span_id": item.get("parent_span_id", ""),
            "name": item.get("name", ""),
            "start_time": item.get("start_time", ""),
            "end_time": item.get("end_time", ""),
            "attributes": json.dumps(item.get("attributes", {})),
        })


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """计算虚拟 Token 成本（美元）"""
    # 简化的成本计算模型
    cost_map = {
        "gpt-4": (0.03, 0.06),      # (input_cost_per_1k, output_cost_per_1k)
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "claude-3-opus": (0.015, 0.075),
        "claude-3-sonnet": (0.003, 0.015),
        "claude-3-haiku": (0.00025, 0.00125),
    }

    # 查找匹配的成本
    for key, (input_cost, output_cost) in cost_map.items():
        if key in model_name.lower():
            return (input_tokens / 1000 * input_cost) + (output_tokens / 1000 * output_cost)

    # 默认成本
    return (input_tokens / 1000 * 0.001) + (output_tokens / 1000 * 0.002)


async def flush_traces(batch: List[Dict[str, Any]]) -> None:
    """刷新 trace 数据到 ClickHouse"""
    if not batch:
        return
    try:
        await insert_traces(batch)
        logger.debug(f"Flushed {len(batch)} traces to ClickHouse")
    except Exception as e:
        logger.error(f"Failed to flush traces: {e}")


async def flush_metrics(batch: List[Dict[str, Any]]) -> None:
    """刷新 metrics 数据到 ClickHouse"""
    if not batch:
        return
    try:
        await insert_metrics(batch)
        logger.debug(f"Flushed {len(batch)} metrics to ClickHouse")
    except Exception as e:
        logger.error(f"Failed to flush metrics: {e}")
