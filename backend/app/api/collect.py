"""
数据收集 API - 接收 SDK 上报的数据
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from ..kafka.producer import send_batch

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
async def collect_data(data: List[Dict[str, Any]]):
    """
    接收 SDK 上报的链路和指标数据

    该接口不做任何数据库写操作，直接将数据投递到 Kafka 后立即返回 202 Accepted
    """
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty data array",
        )

    try:
        await send_batch(data)
        return {
            "status": "accepted",
            "count": len(data),
            "message": "Data queued for processing",
        }
    except Exception as e:
        logger.error(f"Failed to queue data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue data: {str(e)}",
        )
