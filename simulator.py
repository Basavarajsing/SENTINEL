"""Bounded synthetic traffic generator and simulation state."""

from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass, field

import psutil

from config import (
    MAX_EVENTS,
    MAX_EVENTS_PER_SECOND,
    MAX_SIMULATION_SECONDS,
    SERVER_CAPACITY_RPS,
)
from detector import TrafficDetector
from mitigation import MitigationEngine


@dataclass
class SimulationState:
    running: bool = False
    scenario: str = "normal"
    elapsed: float = 0.0
    total: int = 0
    legitimate: int = 0
    suspicious: int = 0
    blocked: int = 0
    allowed_after_mitigation: int = 0
    history: list[dict] = field(default_factory=list)
    last_reasons: list[str] = field(default_factory=list)


class TrafficSimulator:
    def __init__(self) -> None:
        self.state = SimulationState()
        self.detector = TrafficDetector()
        self.mitigation = MitigationEngine()
        self._last_wall_time: float | None = None
        self._random = random.Random(7)
        self._before_load: list[int] = []
        self._after_load: list[int] = []

    def start(self, scenario: str = "normal") -> None:
        if scenario not in {"normal", "excessive"}:
            raise ValueError("scenario must be 'normal' or 'excessive'")
        if self.state.total >= MAX_EVENTS or self.state.elapsed >= MAX_SIMULATION_SECONDS:
            self.reset()
        self.state.scenario = scenario
        self.state.running = True
        self._last_wall_time = time.monotonic()

    def pause(self) -> None:
        self._advance()
        self.state.running = False
        self._last_wall_time = None

    def reset(self) -> None:
        self.state = SimulationState()
        self.detector.reset()
        self.mitigation.reset()
        self._last_wall_time = None
        self._before_load.clear()
        self._after_load.clear()

    def snapshot(self) -> dict:
        self._advance()
        capacity = max(1, SERVER_CAPACITY_RPS)
        current_before = self._before_load[-1] if self._before_load else 0
        current_after = self._after_load[-1] if self._after_load else 0
        availability = max(0.0, min(100.0, 100 * (1 - current_after / capacity)))
        if current_after >= capacity:
            status = "critical"
        elif current_after >= capacity * 0.7:
            status = "warning"
        else:
            status = "normal"
        return {
            "running": self.state.running,
            "scenario": self.state.scenario,
            "elapsed": round(self.state.elapsed, 2),
            "limits": {"seconds": MAX_SIMULATION_SECONDS, "events": MAX_EVENTS},
            "total": self.state.total,
            "legitimate": self.state.legitimate,
            "suspicious": self.state.suspicious,
            "blocked": self.state.blocked,
            "allowed_after_mitigation": self.state.allowed_after_mitigation,
            "before_load": current_before,
            "after_load": current_after,
            "availability": round(availability, 1),
            "capacity": capacity,
            "status": status,
            "history": self.state.history[-30:],
            "reasons": self.state.last_reasons[-5:],
            "system": {
                "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
                "memory_percent": round(psutil.virtual_memory().percent, 1),
            },
        }

    def _advance(self) -> None:
        if not self.state.running or self._last_wall_time is None:
            return
        now = time.monotonic()
        delta = min(max(0.0, now - self._last_wall_time), 0.5)
        self._last_wall_time = now
        remaining_time = MAX_SIMULATION_SECONDS - self.state.elapsed
        delta = min(delta, remaining_time)
        event_rate = 8 if self.state.scenario == "normal" else MAX_EVENTS_PER_SECOND
        count = min(int(delta * event_rate), MAX_EVENTS - self.state.total)
        if count:
            self._process_events(count, delta)
        self.state.elapsed += delta
        if (
            self.state.elapsed >= MAX_SIMULATION_SECONDS
            or self.state.total >= MAX_EVENTS
        ):
            self.state.running = False
            self._last_wall_time = None

    def _process_events(self, count: int, delta: float) -> None:
        count = min(max(0, count), MAX_EVENTS - self.state.total)
        if count == 0:
            return
        start = self.state.elapsed
        before_count = 0
        after_count = 0
        for index in range(count):
            timestamp = start + (index + 1) * (delta / max(1, count))
            if self.state.scenario == "normal":
                source_id = f"user-{self._random.randint(1, 8)}"
                legitimate = True
            else:
                if self._random.random() < 0.75:
                    source_id = f"synthetic-bot-{self._random.randint(1, 4)}"
                    legitimate = False
                else:
                    source_id = f"user-{self._random.randint(1, 8)}"
                    legitimate = True
            event = {
                "timestamp": timestamp,
                "source_id": source_id,
                "legitimate": legitimate,
            }
            result = self.detector.inspect(event)
            decision = self.mitigation.apply(result)
            self.state.total += 1
            self.state.legitimate += int(legitimate)
            self.state.suspicious += int(result.suspicious)
            self.state.blocked += int(not decision.allowed)
            self.state.allowed_after_mitigation += int(decision.allowed)
            self.state.last_reasons.append(f"{source_id}: {result.reason}")
            before_count += 1
            after_count += int(decision.allowed)
        self._before_load.append(before_count)
        self._after_load.append(after_count)
        self.state.history.append(
            {
                "time": round(self.state.elapsed, 1),
                "before": before_count,
                "after": after_count,
            }
        )
