"""Deterministic risk engine: rules over tracks, lanes and signs, then temporal
confirmation (EvidenceGate) per (rule, target).

Rules (thresholds in RiskConfig; every time/geometry value is an uncalibrated
image-space estimate):

  FCW    lead four-wheeler in the ego corridor; level from its scale-expansion
         time-to-contact tau (warning <= fcw_warning_tau_s, caution <= fcw_caution_tau_s).
  VRU    person (riders excluded) / bicycle / motorcycle in the corridor widened by
         vru_path_margin: warning/caution by tau; caution if in path and near,
         or predicted to enter the widened corridor within vru_enter_horizon_s.
  CUT_IN four-wheeler beside the corridor moving toward it at a lateral speed in
         [cut_in_min_speed, cross_min_speed) lane widths/s, predicted to enter
         within cut_in_horizon_s (warning within cut_in_warning_s).
  CROSS  four-wheeler with lateral speed >= cross_min_speed lane widths/s that is
         in path or predicted to enter it within cross_horizon_s.
  LDW    good, fresh lane: offset drifting outward past ldw_line_offset (warning),
         or predicted to reach it within ldw_tlc_s (caution). Lane quality gate:
         quality >= LaneConfig.good_quality and coverage >= ldw_min_coverage.
  SIGN   confirmed relevant signs and the arbitrated speed limit (info only: the
         ego speed is unknown, so no over-speed warning).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from roadwatch.config import RiskConfig
from roadwatch.risk.evidence import CAUTION, NONE, WARNING, EvidenceGate
from roadwatch.risk.geometry import Corridor, CorridorEstimator
from roadwatch.risk.signs import ConfirmedSign, SignArbiter, SpeedLimit
from roadwatch.tracking.kinematics import slope
from roadwatch.tracking.tracker import TrackedObject

LEVEL_NAMES = {CAUTION: "caution", WARNING: "warning"}
KIND_LABELS = {"fcw": "FCW", "vru": "VRU", "cut_in": "CUT-IN", "cross": "CROSS", "ldw": "LDW"}


@dataclass
class RiskEvent:
    kind: str  # fcw | vru | cut_in | cross | ldw
    level: str  # caution | warning
    track_id: int | None
    since_ts: float
    evidence: dict = field(default_factory=dict)  # estimated, uncalibrated values

    @property
    def label(self) -> str:
        """Short ASCII text for the HUD."""
        e = self.evidence
        parts = [KIND_LABELS[self.kind]]
        if self.track_id is not None:
            parts.append(f"#{self.track_id}")
        if e.get("tau_s") is not None:
            parts.append(f"tau~{e['tau_s']:.1f}s")
        if e.get("enter_s"):  # 0 = already in the (widened) corridor: nothing to add
            parts.append(f"enter~{e['enter_s']:.1f}s")
        if "side" in e:
            parts.append(e["side"])
        return " ".join(parts) + " (est.)"


@dataclass
class RiskResult:
    events: list[RiskEvent]  # active alerts, most severe first
    corridor: Corridor
    speed_limit: SpeedLimit | None
    recent_signs: list[ConfirmedSign]
    new_signs: list[ConfirmedSign]
    track_levels: dict[int, str]  # track id -> most severe active level involving it
    lane_used: bool  # corridor/LDW came from a fresh, good lane result

    @property
    def level(self) -> str | None:
        return self.events[0].level if self.events else None


@dataclass
class _Geo:
    """Per-track geometry relative to the corridor in the current frame."""

    track: TrackedObject
    depth: float
    in_path: bool  # bottom centre inside the corridor and enough of the box overlapping it
    u_center: float  # lateral position of the bottom centre (lane widths, 0 = corridor centre)
    u_near: float  # signed lateral position of the box edge nearest the corridor centre
    speed_toward: float | None  # lane widths / s toward the corridor centre
    lateral_speed: float | None  # |du/dt|, lane widths / s

    def enter_s(self, half_width: float) -> float | None:
        """Predicted time until the near edge enters |u| <= half_width (0 if inside)."""
        gap = abs(self.u_near) - half_width
        if gap <= 0:
            return 0.0
        if not self.speed_toward or self.speed_toward <= 0:
            return None
        return gap / self.speed_toward


class RiskEngine:
    def __init__(self, cfg: RiskConfig | None = None, good_lane_quality: float = 0.6):
        self.cfg = cfg or RiskConfig()
        self.good_lane_quality = good_lane_quality
        self.corridors = CorridorEstimator(self.cfg)
        self.signs = SignArbiter(self.cfg)
        self.reset()

    def reset(self) -> None:
        """New session: no gates, no lane history, no sign votes, default horizon."""
        self._gates: dict[tuple, EvidenceGate] = {}
        self._evidence: dict[tuple, dict] = {}
        self._offsets: deque[tuple[float, float]] = deque()
        self._last_lane_seq: int | None = None
        self.corridors.reset()
        self.signs.reset()

    # -- geometry --------------------------------------------------------
    def _geo(self, t: TrackedObject, cor: Corridor) -> _Geo | None:
        x1, _, x2, y2 = t.xyxy
        b = cor.bounds(y2)
        if b is None:
            return None
        xl, xr = b
        cw = xr - xl
        c = (xl + xr) / 2
        overlap = max(0.0, min(x2, xr) - max(x1, xl)) / max(1.0, min(x2 - x1, cw))
        ul, ur = (x1 - c) / cw, (x2 - c) / cw
        u_near = 0.0 if ul <= 0 <= ur else (ul if ul > 0 else ur)
        u_center = (ul + ur) / 2
        # The centre test matters: a car in the next lane that we are passing shows its
        # side, so its box reaches well into our corridor while its centre does not.
        in_path = abs(u_center) <= 0.5 and overlap >= self.cfg.in_path_overlap

        # Lateral speed of the edge facing the corridor centre: the far edge may be cut
        # by the image border, which moves the box centre without any real motion.
        # With the bottom cut the ground-contact row is unknown: no estimate at all.
        speed = None
        img_h = cor.image_hw[0]
        h = t.history
        h = h[h[:, 0] >= h[-1, 0] - self.cfg.lateral_window_s]
        if len(h) >= self.cfg.lateral_min_points and y2 < img_h - self.cfg.bottom_margin_px:
            col = 1 if u_center > 0 else 3  # x1 for objects right of centre, else x2
            us = [cor.lateral(r[col], r[4]) for r in h]
            ok = [i for i, u in enumerate(us) if u is not None]
            if len(ok) >= self.cfg.lateral_min_points:
                speed = slope(h[ok, 0], np.array([us[i] for i in ok]))
        toward = None
        if speed is not None:
            toward = -np.sign(u_center) * speed if u_center != 0 else abs(speed)
        return _Geo(t, cor.depth(y2), in_path, u_center, u_near,
                    None if toward is None else float(toward),
                    None if speed is None else abs(speed))

    @staticmethod
    def _riders(tracks: list[TrackedObject], min_overlap: float) -> set[int]:
        """Person tracks that sit on a two-wheeler (drawn as one road user)."""
        wheels = [t.xyxy for t in tracks if t.group == "two_wheeler"]
        out = set()
        for p in tracks:
            if p.group != "person" or not wheels:
                continue
            px1, py1, px2, py2 = p.xyxy
            area = max(1.0, (px2 - px1) * (py2 - py1))
            pcx = (px1 + px2) / 2
            for mx1, my1, mx2, my2 in wheels:
                inter = max(0.0, min(px2, mx2) - max(px1, mx1)) * max(0.0, min(py2, my2) - max(py1, my1))
                if inter / area >= min_overlap and mx1 <= pcx <= mx2:
                    out.add(p.track_id)
                    break
        return out

    # -- rules -----------------------------------------------------------
    def _fcw(self, geos: list[_Geo]) -> dict[tuple, tuple[int, dict]]:
        cfg = self.cfg
        cands = [g for g in geos if g.track.group == "four_wheeler" and g.in_path
                 and g.depth >= cfg.fcw_min_depth]
        if not cands:
            return {}
        lead = max(cands, key=lambda g: g.depth)
        kin = lead.track.kinematics
        tau = kin.tau_s if kin is not None else None
        level = NONE
        if tau is not None:
            level = WARNING if tau <= cfg.fcw_warning_tau_s else \
                CAUTION if tau <= cfg.fcw_caution_tau_s else NONE
        return {("fcw",): (level, {"track": lead.track.track_id, "tau_s": tau,
                                   "depth": lead.depth,
                                   "scale_rate": kin.scale_rate if kin else None})}

    def _vru(self, geos: list[_Geo], riders: set[int]) -> dict[tuple, tuple[int, dict]]:
        cfg = self.cfg
        out = {}
        for g in geos:
            t = g.track
            if t.group not in ("person", "two_wheeler") or t.track_id in riders:
                continue
            if g.depth < cfg.min_depth:
                continue
            kin = t.kinematics
            tau = kin.tau_s if kin is not None else None
            half = 0.5 + cfg.vru_path_margin
            enter = g.enter_s(half)
            near_path = abs(g.u_center) <= half
            level = NONE
            if near_path and tau is not None:
                level = WARNING if tau <= cfg.vru_warning_tau_s else \
                    CAUTION if tau <= cfg.vru_caution_tau_s else NONE
            if level == NONE and g.in_path and g.depth >= cfg.vru_near_depth \
                    and (kin is None or kin.scale_rate >= -0.05):
                level = CAUTION
            if level == NONE and not near_path and enter is not None \
                    and enter <= cfg.vru_enter_horizon_s and g.depth >= cfg.cut_in_min_depth \
                    and (g.speed_toward or 0.0) >= cfg.cut_in_min_speed:
                level = CAUTION
            if level:
                out[("vru", t.track_id)] = (level, {"tau_s": tau, "enter_s": enter,
                                                    "depth": g.depth, "cls": t.cls})
        return out

    def _lateral(self, geos: list[_Geo]) -> dict[tuple, tuple[int, dict]]:
        cfg = self.cfg
        out = {}
        for g in geos:
            t = g.track
            if t.group != "four_wheeler" or g.lateral_speed is None or g.depth < cfg.min_depth:
                continue
            toward = g.speed_toward or 0.0
            enter = g.enter_s(0.5)
            ev = {"enter_s": enter, "lat_speed": g.lateral_speed, "depth": g.depth}
            if g.lateral_speed >= cfg.cross_min_speed and (g.in_path or toward > 0):
                if enter is not None and enter <= cfg.cross_horizon_s:
                    near = enter <= cfg.cross_warning_s and g.depth >= cfg.cut_in_min_depth
                    out[("cross", t.track_id)] = (WARNING if near else CAUTION, ev)
                continue
            if g.in_path or toward < cfg.cut_in_min_speed or g.depth < cfg.cut_in_min_depth:
                continue
            if abs(g.u_near) - 0.5 > cfg.cut_in_max_gap:
                continue
            kin = t.kinematics
            if kin is not None and kin.scale_rate < -0.1:  # pulling away ahead of us
                continue
            if enter is not None and enter <= cfg.cut_in_horizon_s:
                out[("cut_in", t.track_id)] = (
                    WARNING if enter <= cfg.cut_in_warning_s else CAUTION, ev)
        return out

    def _ldw(self, ts: float, lane, lane_seq: int | None, lane_age_s: float | None,
             lane_ok: bool) -> dict[tuple, tuple[int, dict]]:
        cfg = self.cfg
        if not lane_ok or lane.offset is None:
            return {}
        if lane_seq != self._last_lane_seq:
            self._last_lane_seq = lane_seq
            if self._offsets and abs(lane.offset - self._offsets[-1][1]) > cfg.ldw_jump:
                self._offsets.clear()  # lane change completed: new reference lane
            # Time of the frame the lane was computed on, not of this frame.
            self._offsets.append((ts - (lane_age_s or 0.0), lane.offset))
        while self._offsets and self._offsets[0][0] < ts - cfg.ldw_window_s:
            self._offsets.popleft()
        if len(self._offsets) < cfg.ldw_min_points:
            return {}
        t, off = np.array(self._offsets).T
        rate = slope(t, off)
        o = float(off[-1])
        side = "right" if o > 0 else "left"
        outward = rate * np.sign(o)
        level = NONE
        if abs(o) >= cfg.ldw_line_offset and outward >= cfg.ldw_min_rate:
            level = WARNING
        elif abs(o) >= cfg.ldw_caution_offset and outward >= cfg.ldw_min_rate \
                and (cfg.ldw_line_offset - abs(o)) / outward <= cfg.ldw_tlc_s:
            level = CAUTION
        return {("ldw", side): (level, {"offset": o, "rate": float(rate), "side": side})}

    # -- main entry ------------------------------------------------------
    def update(self, ts: float, image_hw: tuple[int, int], tracks: list[TrackedObject],
               lane=None, lane_seq: int | None = None, lane_age_s: float | None = None,
               signs=None, signs_seq: int | None = None) -> RiskResult:
        cfg = self.cfg
        lane_ok = (lane is not None and lane_age_s is not None and lane_age_s <= cfg.lane_max_age_s
                   and lane.quality >= self.good_lane_quality
                   and lane.coverage >= cfg.ldw_min_coverage)
        corridor = (self.corridors.from_lane(lane, image_hw) if lane_ok else None) \
            or self.corridors.default(image_hw)

        geos = [g for t in tracks if (g := self._geo(t, corridor)) is not None]
        riders = self._riders(tracks, cfg.rider_overlap)
        cands: dict[tuple, tuple[int, dict]] = {}
        cands.update(self._fcw(geos))
        cands.update(self._vru(geos, riders))
        cands.update(self._lateral(geos))
        cands.update(self._ldw(ts, lane, lane_seq, lane_age_s, lane_ok))

        events: list[RiskEvent] = []
        for key in set(self._gates) | set(cands):
            level, ev = cands.get(key, (NONE, None))
            gate = self._gates.get(key)
            if gate is None:
                if level == NONE:
                    continue
                gate = self._gates[key] = EvidenceGate(cfg.evidence)
            # Keep the evidence of the last frame that met the condition, so a held
            # alert keeps showing why it fired.
            if ev is not None and (level > NONE or key not in self._evidence):
                self._evidence[key] = ev
            active = gate.update(ts, level)
            if active:
                ev = self._evidence.get(key, {})
                tid = key[1] if len(key) > 1 and isinstance(key[1], int) else ev.get("track")
                events.append(RiskEvent(key[0], LEVEL_NAMES[active], tid, gate.since, dict(ev)))
            elif gate.idle:
                del self._gates[key]
                self._evidence.pop(key, None)
        events.sort(key=lambda e: (e.level != "warning", e.since_ts))

        track_levels: dict[int, str] = {}
        for e in events:
            if e.track_id is not None and track_levels.get(e.track_id) != "warning":
                track_levels[e.track_id] = e.level

        sign_state = self.signs.update(ts, signs, signs_seq, image_hw)
        return RiskResult(events, corridor, sign_state.speed_limit, sign_state.recent,
                          sign_state.new, track_levels, lane_ok)
