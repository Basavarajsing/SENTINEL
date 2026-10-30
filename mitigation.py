"""In-memory mitigation primitives for synthetic events only."""

from dataclasses import dataclass

from config import (
    RATE_LIMIT_REFILL_PER_SECOND,
    RATE_LIMIT_TOKENS,
    TEMPORARY_BLOCK_SECONDS,
)
from detector import DetectionResult


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = float(capacity)
        self.refill_per_second = refill_per_second
        self.tokens = float(capacity)
        self.last_time = 0.0

    def allow(self, now: float) -> bool:
        elapsed = max(0.0, now - self.last_time)
        self.tokens = min(
            self.capacity, self.tokens + elapsed * self.refill_per_second
        )
        self.last_time = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


class TemporaryBlockList:
    def __init__(self, duration_seconds: float = TEMPORARY_BLOCK_SECONDS) -> None:
        self.duration_seconds = duration_seconds
        self._blocked_until: dict[str, float] = {}

    def block(self, source_id: str, now: float) -> None:
        self._blocked_until[source_id] = now + self.duration_seconds

    def is_blocked(self, source_id: str, now: float) -> bool:
        until = self._blocked_until.get(source_id, 0.0)
        if until <= now:
            self._blocked_until.pop(source_id, None)
            return False
        return True

    def reset(self) -> None:
        self._blocked_until.clear()


@dataclass(frozen=True)
class MitigationDecision:
    allowed: bool
    action: str


class MitigationEngine:
    """Blocks detected sources and rate-limits all remaining synthetic sources."""

    def __init__(
        self,
        bucket_capacity: int = RATE_LIMIT_TOKENS,
        refill_per_second: float = RATE_LIMIT_REFILL_PER_SECOND,
        block_seconds: float = TEMPORARY_BLOCK_SECONDS,
    ) -> None:
        self.bucket_capacity = bucket_capacity
        self.refill_per_second = refill_per_second
        self.blocks = TemporaryBlockList(block_seconds)
        self._buckets: dict[str, TokenBucket] = {}

    def apply(self, result: DetectionResult) -> MitigationDecision:
        event = result.event
        source_id = str(event["source_id"])
        now = float(event["timestamp"])
        if self.blocks.is_blocked(source_id, now):
            return MitigationDecision(False, "temporary block")
        if result.suspicious:
            self.blocks.block(source_id, now)
            return MitigationDecision(False, "temporary block triggered")
        bucket = self._buckets.setdefault(
            source_id,
            TokenBucket(self.bucket_capacity, self.refill_per_second),
        )
        if bucket.allow(now):
            return MitigationDecision(True, "allowed by token bucket")
        return MitigationDecision(False, "rate limited")

    def reset(self) -> None:
        self.blocks.reset()
        self._buckets.clear()

