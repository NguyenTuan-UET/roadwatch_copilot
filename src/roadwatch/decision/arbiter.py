"""Pure audio arbiter (spec §3.6): one phrase playing plus one pending slot, driven by session time."""

from collections.abc import Callable
from dataclasses import dataclass

from ..contracts.config import Audio
from ..contracts.streams import AlertDecision

MS = 1_000_000
PRIORITY = {
    "emergency": 1,
    "warning": 2,
    "system_off": 3,
    "cap_distance_off": 4,
    "cap_ttc_off": 4,
    "info": 5,
    "recovery": 6,
    "reminder": 7,
}


@dataclass(frozen=True)
class Outcome:
    alert_id: str
    outcome: str  # started | preempted | cancelled | expired
    t_ns: int
    preempted_by: str | None = None
    reasons: tuple[str, ...] = ()


class AudioArbiter:
    def __init__(self, cfg: Audio):
        self.dur_ns = {k: v * MS for k, v in cfg.phrases.items()}
        self.max_age_ns = cfg.max_cmd_age_ms * MS
        self.playing: tuple[AlertDecision, int] | None = None  # (alert, until_ns)
        self.pending: AlertDecision | None = None

    def _start(self, a: AlertDecision, t: int) -> Outcome:
        self.playing = (a, t + self.dur_ns[a.phrase_id])
        return Outcome(a.alert_id, "started", t)

    def advance(self, t: int, epoch: int) -> list[Outcome]:
        """Finish whatever ended by `t`; the pending command starts exactly when the previous one ends."""
        out = []
        while self.playing and self.playing[1] <= t:
            end = self.playing[1]
            self.playing = None
            p, self.pending = self.pending, None
            if p is None:
                break
            if p.cls == "status" and p.capability_epoch != epoch:
                out.append(Outcome(p.alert_id, "cancelled", end, reasons=("epoch_changed",)))
            elif end - p.t_trigger_ns > self.max_age_ns:
                out.append(Outcome(p.alert_id, "expired", end, reasons=("max_cmd_age",)))
            else:
                out.append(self._start(p, end))
        return out

    def submit(self, a: AlertDecision, t: int, epoch: int) -> list[Outcome]:
        out = self.advance(t, epoch)
        if self.playing is None:
            return out + [self._start(a, t)]
        current = self.playing[0]
        if a.cls == "hazard" and PRIORITY[a.kind] < PRIORITY[current.kind]:  # status never preempts
            out.append(Outcome(current.alert_id, "preempted", t, preempted_by=a.alert_id))
            return out + [self._start(a, t)]
        if self.pending is None or PRIORITY[a.kind] <= PRIORITY[self.pending.kind]:
            if self.pending is not None:
                out.append(Outcome(self.pending.alert_id, "cancelled", t, reasons=("superseded",)))
            self.pending = a
        else:
            out.append(Outcome(a.alert_id, "cancelled", t, reasons=("lower_priority_than_pending",)))
        return out

    def cancel_pending(self, pred: Callable[[AlertDecision], bool], t: int, reason: str) -> list[Outcome]:
        if self.pending is not None and pred(self.pending):
            p, self.pending = self.pending, None
            return [Outcome(p.alert_id, "cancelled", t, reasons=(reason,))]
        return []
