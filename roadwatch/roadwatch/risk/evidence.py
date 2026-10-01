"""Temporal confirmation with hysteresis for per-frame risk conditions.

Each frame a rule reports a level for a key (0 none, 1 caution, 2 warning).
A level L becomes active once frames with level >= L cover at least
`confirm_s` and make up at least `ratio` of the frames in the last `window_s`.
Escalation is immediate once confirmed; an active level is held for at least
`hold_s` and dropped only after `release_s` without any frame at that level.
"""

from __future__ import annotations

from collections import deque

from roadwatch.config import EvidenceConfig

NONE, CAUTION, WARNING = 0, 1, 2


class EvidenceGate:
    def __init__(self, cfg: EvidenceConfig):
        self.cfg = cfg
        self._samples: deque[tuple[float, int]] = deque()
        self._last_at: dict[int, float] = {}
        self.level = NONE
        self.since: float | None = None  # when the current active level started

    def _confirmed(self, level: int) -> bool:
        hits = [t for t, lv in self._samples if lv >= level]
        if not hits:
            return False
        return (hits[-1] - hits[0] >= self.cfg.confirm_s
                and len(hits) >= self.cfg.ratio * len(self._samples))

    def update(self, ts: float, level: int) -> int:
        cfg = self.cfg
        self._samples.append((ts, level))
        while self._samples and self._samples[0][0] < ts - cfg.window_s:
            self._samples.popleft()
        for lv in range(1, level + 1):
            self._last_at[lv] = ts

        confirmed = max((lv for lv in (WARNING, CAUTION) if self._confirmed(lv)), default=NONE)
        if confirmed > self.level:
            self.level, self.since = confirmed, ts
        elif self.level > confirmed:
            held = self.since is not None and ts - self.since >= cfg.hold_s
            absent = ts - self._last_at.get(self.level, -1e9) >= cfg.release_s
            if held and absent:
                self.level = confirmed
                self.since = ts if confirmed else None
        return self.level

    @property
    def idle(self) -> bool:
        """Inactive and nothing positive left in the window: safe to delete."""
        return self.level == NONE and all(lv == NONE for _, lv in self._samples)
