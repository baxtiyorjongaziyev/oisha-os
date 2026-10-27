"""Redis Streams Worker Infrastructure — BullMQ-style patterns for Python."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

import redis.asyncio as redis
from pydantic import BaseModel, Field

from src.settings import settings

logger = logging.getLogger(__name__)


class JobPayload(BaseModel):
    """Base job payload structure."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: str
    payload: dict[str, Any]
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None


class JobResult(BaseModel):
    """Job execution result."""
    success: bool
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class WorkerConfig:
    stream_name: str
    consumer_group: str
    consumer_name: str = field(default_factory=lambda: f"worker-{uuid.uuid4().hex[:8]}")
    block_ms: int = 5000
    count: int = 10
    prefetch: int = 10
    max_retries: int = 3
    retry_delay_ms: int = 5000
    dead_letter_stream: Optional[str] = None


class RedisWorker(ABC):
    """Base worker consuming from Redis Streams."""

    def __init__(self, config: WorkerConfig, redis_client: Optional[redis.Redis] = None):
        self.config = config
        self.redis = redis_client or self._create_redis()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._handlers: dict[str, Callable] = {}

    def _create_redis(self) -> redis.Redis:
        url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(url, decode_responses=True)

    def register(self, job_type: str):
        """Decorator to register job handler."""
        def decorator(func: Callable):
            self._handlers[job_type] = func
            return func
        return decorator

    async def _ensure_group(self):
        """Create consumer group if not exists."""
        try:
            await self.redis.xgroup_create(
                self.config.stream_name,
                self.config.consumer_group,
                id="0",
                mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def _process_message(self, message_id: str, data: dict) -> JobResult:
        """Process a single message."""
        start = time.perf_counter()
        try:
            job = JobPayload(**data)
            handler = self._handlers.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler for job_type: {job.job_type}")

            if asyncio.iscoroutinefunction(handler):
                result = await handler(job.payload)
            else:
                result = handler(job.payload)

            duration = int((time.perf_counter() - start) * 1000)
            return JobResult(success=True, result=result, duration_ms=duration)

        except Exception as e:
            duration = int((time.perf_counter() - start) * 1000)
            logger.exception("[Worker] Job failed: %s", e)
            return JobResult(success=False, error=str(e), duration_ms=duration)

    async def _handle_retry(self, message_id: str, job: JobPayload, error: str):
        """Handle retry logic with exponential backoff."""
        job.retries += 1
        if job.retries >= job.max_retries:
            await self._send_to_dlq(message_id, job, error)
            return

        delay = self.config.retry_delay_ms * (2 ** (job.retries - 1))
        job.scheduled_at = datetime.utcnow()

        await asyncio.sleep(delay / 1000)
        await self.redis.xadd(self.config.stream_name, job.model_dump(mode="json"))

    async def _send_to_dlq(self, message_id: str, job: JobPayload, error: str):
        """Send failed job to dead letter queue."""
        if self.config.dead_letter_stream:
            dlq_data = job.model_dump(mode="json")
            dlq_data["_dlq_error"] = error
            dlq_data["_dlq_original_stream"] = self.config.stream_name
            dlq_data["_dlq_failed_at"] = datetime.utcnow().isoformat()
            await self.redis.xadd(self.config.dead_letter_stream, dlq_data)
            logger.warning("[Worker] Job sent to DLQ: %s", job.job_id)

    async def _consume_loop(self):
        """Main consumption loop."""
        await self._ensure_group()
        logger.info("[Worker] Started consuming from %s", self.config.stream_name)

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    self.config.consumer_group,
                    self.config.consumer_name,
                    {self.config.stream_name: ">"},
                    count=self.config.count,
                    block=self.config.block_ms
                )

                if not messages:
                    continue

                for stream, entries in messages:
                    for message_id, data in entries:
                        job_result = await self._process_message(message_id, data)

                        if job_result.success:
                            await self.redis.xack(self.config.stream_name, self.config.consumer_group, message_id)
                        else:
                            job = JobPayload(**data)
                            await self._handle_retry(message_id, job, job_result.error or "Unknown error")
                            await self.redis.xack(self.config.stream_name, self.config.consumer_group, message_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("[Worker] Consume loop error: %s", e)
                await asyncio.sleep(1)

    async def start(self):
        """Start the worker."""
        self._running = True
        task = asyncio.create_task(self._consume_loop(), name=f"worker-{self.config.stream_name}")
        self._tasks.append(task)
        logger.info("[Worker] Started: %s", self.config.stream_name)

    async def stop(self):
        """Stop the worker gracefully."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.redis.close()
        logger.info("[Worker] Stopped: %s", self.config.stream_name)


class JobProducer:
    """Produce jobs to Redis Streams."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or redis.from_url(
            getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True
        )

    async def enqueue(
        self,
        stream_name: str,
        job_type: str,
        payload: dict[str, Any],
        priority: int = 0,
        max_retries: int = 3,
        idempotency_key: Optional[str] = None,
        scheduled_at: Optional[datetime] = None
    ) -> str:
        """Add job to stream."""
        job = JobPayload(
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            idempotency_key=idempotency_key,
            scheduled_at=scheduled_at
        )

        if idempotency_key:
            exists = await self.redis.exists(f"idempotency:{idempotency_key}")
            if exists:
                logger.info("[Producer] Idempotent skip: %s", idempotency_key)
                return ""

            await self.redis.setex(f"idempotency:{idempotency_key}", 86400, "1")

        if scheduled_at and scheduled_at > datetime.utcnow():
            delay_ms = int((scheduled_at - datetime.utcnow()).total_seconds() * 1000)
            await asyncio.sleep(delay_ms / 1000)

        message_id = await self.redis.xadd(stream_name, job.model_dump(mode="json"))
        logger.info("[Producer] Enqueued %s to %s: %s", job_type, stream_name, message_id)
        return message_id

    async def close(self):
        await self.redis.close()


async def get_redis() -> redis.Redis:
    """Get shared Redis client."""
    url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(url, decode_responses=True)