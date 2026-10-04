from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class ChannelSnapshot:
    id: int
    title: str
    username: str | None
    description: str
    recent_messages: list[str]
    is_broadcast: bool
    is_megagroup: bool
    verified: bool


@dataclass(slots=True)
class AIClassification:
    adult_score: float
    spam_score: float
    junk_score: float
    category: str
    reason: str

    @property
    def max_score(self) -> float:
        return max(self.adult_score, self.spam_score, self.junk_score)


@dataclass(slots=True)
class ScanResult:
    channel_id: int
    title: str
    username: str | None
    classification: AIClassification | None
    action: str
    reason: str
    protected: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload
