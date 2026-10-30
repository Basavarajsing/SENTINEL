"""Synthetic traffic detection using transparent, explainable thresholds."""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from config import (
    DETECTION_WINDOW_SECONDS,
    GLOBAL_REQUEST_THRESHOLD,
    SOURCE_REQUEST_THRESHOLD,
)


@dataclass(frozen=True)
class DetectionResult:
    event: dict
    suspicious: bool
    reason: str


class TrafficDetector:
    """Detects bursts by source and across the simulated server."""

    def __init__(
        self,
        source_threshold: int = SOURCE_REQUEST_THRESHOLD,
        global_threshold: int = GLOBAL_REQUEST_THRESHOLD,
        window_seconds: float = DETECTION_WINDOW_SECONDS,
    ) -> None:
        self.source_threshold = source_threshold
        self.global_threshold = global_threshold
        self.window_seconds = window_seconds
        self._source_times: dict[str, deque[float]] = defaultdict(deque)
        self._global_times: deque[float] = deque()

    @staticmethod
    def _trim(times: deque[float], now: float, window: float) -> None:
        while times and now - times[0] > window:
            times.popleft()

    def inspect(self, event: dict) -> DetectionResult:
        timestamp = float(event["timestamp"])
        source_id = str(event["source_id"])
        source_times = self._source_times[source_id]
        source_times.append(timestamp)
        self._global_times.append(timestamp)
        self._trim(source_times, timestamp, self.window_seconds)
        self._trim(self._global_times, timestamp, 1.0)

        source_count = len(source_times)
        global_count = len(self._global_times)
        reasons: list[str] = []
        if source_count >= self.source_threshold:
            reasons.append(
                f"source rate {source_count} requests/{self.window_seconds:g}s "
                f">= {self.source_threshold}"
            )
        if global_count >= self.global_threshold:
            reasons.append(
                f"global rate {global_count} requests/1s >= {self.global_threshold}"
            )
        if reasons:
            return DetectionResult(event, True, "; ".join(reasons))
        return DetectionResult(event, False, "within configured synthetic thresholds")

    def inspect_many(self, events: Iterable[dict]) -> list[DetectionResult]:
        return [self.inspect(event) for event in events]

    def reset(self) -> None:
        self._source_times.clear()
        self._global_times.clear()

