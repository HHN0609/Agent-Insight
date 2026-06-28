"""
Kafka 生产者 - 用于将 SDK 上报的数据投递到 Kafka
"""

import json
import logging
from typing import Any, Dict, List

from aiokafka import AIOKafkaProducer

from ..config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer = None


async def init_producer() -> None:
    """初始化 Kafka 生产者"""
    global _producer
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks=1,
            max_batch_size=16384,
            linger_ms=10,
        )
        await _producer.start()
        logger.info(f"Kafka producer started, servers: {settings.kafka_bootstrap_servers}")
    except Exception as e:
        logger.error(f"Failed to start Kafka producer: {e}")
        raise


async def close_producer() -> None:
    """关闭 Kafka 生产者"""
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")


async def send_batch(data: List[Dict[str, Any]]) -> None:
    """发送一批数据到 Kafka"""
    if not _producer:
        raise RuntimeError("Kafka producer not initialized")

    try:
        await _producer.send_and_wait(
            settings.kafka_topic,
            value=data,
        )
        logger.debug(f"Sent {len(data)} records to Kafka topic: {settings.kafka_topic}")
    except Exception as e:
        logger.error(f"Failed to send batch to Kafka: {e}")
        raise
