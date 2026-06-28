"""
链路查询 API
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from ..clickhouse.client import query_traces

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/traces")
async def get_traces(
    trace_id: Optional[str] = Query(None, description="指定 trace_id 查询单条链路"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
):
    """
    查询链路追踪数据

    - 不传 trace_id: 返回最近的链路列表
    - 传 trace_id: 返回该链路的完整 span 树
    """
    try:
        traces = await query_traces(trace_id=trace_id, limit=limit)
        return {
            "status": "success",
            "count": len(traces),
            "data": traces,
        }
    except Exception as e:
        logger.error(f"Failed to query traces: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }
