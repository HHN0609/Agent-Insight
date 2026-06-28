"""
异步批量上报器 - 使用 asyncio.Queue 和后台任务实现高效上报
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class SpanData:
    """Span 数据结构"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: str
    end_time: str
    span_type: str  # "trace" or "llm_metrics"
    attributes: Dict[str, Any] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id or "",
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "span_type": self.span_type,
            "attributes": self.attributes,
        }


class AsyncBatchUploader:
    """异步批量上报器"""

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        batch_size: int = 20,
        flush_interval: float = 0.5,
    ):
        self._backend_url = backend_url
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """启动后台上报任务"""
        if self._running:
            return

        self._running = True
        self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._upload_loop())
        self._logger.info("AsyncBatchUploader started")

    async def stop(self) -> None:
        """停止后台上报任务"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # 刷新剩余数据
        await self._flush()

        if self._client:
            await self._client.aclose()

        self._logger.info("AsyncBatchUploader stopped")

    async def submit(self, span: SpanData) -> None:
        """提交 span 数据到队列"""
        await self._queue.put(span.to_dict())

    async def _upload_loop(self) -> None:
        """后台上报循环"""
        batch: List[Dict[str, Any]] = []

        while self._running:
            try:
                # 尝试从队列获取数据
                try:
                    item = await asyncio.wait_for(
                        self._queue.get(), timeout=self._flush_interval
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass

                # 达到批量阈值或超时时刷新
                if len(batch) >= self._batch_size:
                    await self._flush_batch(batch)
                    batch = []

            except Exception as e:
                self._logger.error(f"Error in upload loop: {e}")
                await asyncio.sleep(0.1)

        # 处理剩余的 batch
        if batch:
            await self._flush_batch(batch)

    async def _flush_batch(self, batch: List[Dict[str, Any]]) -> None:
        """刷新一批数据到后端"""
        if not batch or not self._client:
            return

        try:
            url = f"{self._backend_url}/api/v1/collect"
            response = await self._client.post(url, json=batch)
            if response.status_code == 202:
                self._logger.debug(f"Successfully uploaded {len(batch)} spans")
            else:
                self._logger.warning(
                    f"Upload failed with status {response.status_code}: {response.text}"
                )
        except Exception as e:
            self._logger.error(f"Failed to upload batch: {e}")

    async def _flush(self) -> None:
        """刷新队列中所有剩余数据"""
        batch = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                batch.append(item)
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._flush_batch(batch)
