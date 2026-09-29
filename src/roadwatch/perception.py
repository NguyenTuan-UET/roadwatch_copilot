"""BT-A (spec §4.2): one Measurement per frame from detections + fixed mount geometry. No speed, no thresholds."""

from collections.abc import Callable

import cv2
import numpy as np

from .contracts.base import Q
from .contracts.config import Perception as PerceptionCfg
from .contracts.config import RwConfig
from .contracts.streams import ChangeEvidence, Lead, LeadChange, Measurement, MountCheck, Observation
from .detect import Track, Tracker, iou

MS = 1_000_000


def distance_from_bottom(y_bottom: float, fy: float, h_cam: float, y_horizon: float, d_cam_bumper: float) -> Q:
    """Flat-road pinhole: horizontal camera->vehicle distance minus camera->bumper (file 3 §2). No sigma yet."""
    dy = y_bottom - y_horizon
    if dy < 1.0:
        return Q.missing("unreliable", "at_horizon")
    d = fy * h_cam / dy - d_cam_bumper
    if d <= 0:
        return Q.missing("unreliable", "inside_bumper_offset")
    return Q.ok(d)


def ttc_from_widths(ts_ns: list[int], widths: list[float], min_frames: int, min_w: float, max_resid: float) -> Q:
    """TTC from scale change: d ln(w)/dt = 1/TTC; the fit's slope refers to the window centre, so shift to now."""
    if len(widths) < min_frames:
        return Q.missing("unreliable", "too_few_frames")
    ts = np.array(ts_ns[-2 * min_frames :], dtype=np.float64) / 1e9
    lw = np.log(np.array(widths[-2 * min_frames :], dtype=np.float64))
    if np.exp(lw).min() < min_w:
        return Q.missing("unreliable", "too_small")
    slope, intercept = np.polyfit(ts, lw, 1)
    resid = float(np.sqrt(np.mean((lw - (slope * ts + intercept)) ** 2)))
    if resid > max_resid:
        return Q.missing("unreliable", "poor_fit")
    if slope <= 1e-3:
        return Q.missing("not_applicable", "not_closing")
    return Q.ok(max(0.0, 1.0 / slope - (ts[-1] - ts.mean())))


def observation_status(img: np.ndarray, cfg: PerceptionCfg) -> Observation:
    # nearest-neighbour sampling keeps pixel variance (area averaging would erase contrast)
    gray = cv2.cvtColor(cv2.resize(img, (160, 90), interpolation=cv2.INTER_NEAREST), cv2.COLOR_BGR2GRAY)
    mean, std = float(gray.mean()), float(gray.std())
    if mean < cfg.obs_min_luma:
        return Observation(status="unreliable", reasons=["too_dark"])
    if mean > cfg.obs_max_luma:
        return Observation(status="unreliable", reasons=["too_bright"])
    if std < cfg.obs_min_std:
        return Observation(status="unreliable", reasons=["low_contrast"])
    return Observation(status="ok")


class MountChecker:
    """ADR-05: phase correlation of the bottom strip (hood/dashboard) against the run's first strip.

    Only detects; never corrects the config. ponytail: reference = first textured strip of the run, so it
    detects shifts during a run; absolute alignment is the pre-drive checklist's job (method TBD after KS-4).
    """

    def __init__(self, cfg: PerceptionCfg):
        self.cfg = cfg
        self.ref: np.ndarray | None = None
        self.state, self.since, self.over_since = "unknown", 0, None
        self.window = None

    def _strip(self, img: np.ndarray) -> np.ndarray:
        h = img.shape[0]
        gray = cv2.cvtColor(img[int(h * (1 - self.cfg.mount_strip_frac)) :], cv2.COLOR_BGR2GRAY)
        return gray.astype(np.float32)

    def _set(self, state: str, t: int) -> MountCheck:
        if state != self.state:
            self.state, self.since = state, t
        return MountCheck(state=self.state, since_t_ns=self.since)

    def update(self, img: np.ndarray, t: int) -> MountCheck:
        strip = self._strip(img)
        if strip.std() < self.cfg.obs_min_std:
            return self._set("unknown", t)  # no texture: no evidence either way
        if self.ref is None:
            self.ref, self.window = strip, cv2.createHanningWindow(strip.shape[::-1], cv2.CV_32F)
            return self._set("ok", t)
        (dx, dy), response = cv2.phaseCorrelate(self.ref, strip, self.window)
        if not response >= self.cfg.mount_min_response:
            return self._set("unknown", t)
        dev = float(np.hypot(dx, dy))
        if dev > self.cfg.mount_suspect_px:
            self.over_since = t if self.over_since is None else self.over_since
            if t - self.over_since >= self.cfg.mount_t_suspect_ms * MS:
                return self._set("suspect", t)
        else:
            self.over_since = None
            if dev < self.cfg.mount_recover_px:
                return self._set("ok", t)
        return self._set(self.state, t)  # between thresholds or not yet persistent: keep the state


class Perception:
    def __init__(self, cfg: RwConfig, detector: Callable[[np.ndarray], np.ndarray] | None):
        self.cfg, self.p, self.detector = cfg, cfg.perception, detector
        self.tracker = Tracker()
        self.mount = MountChecker(cfg.perception)
        self.lead: dict | None = None  # identity, track_id, since, change, last_bbox, last_t
        self.roi_hits: dict[int, int] = {}  # track_id -> frames seen outside the ROI before entering

    # --- helpers -------------------------------------------------------------------------------
    def _in_roi(self, x: float, y: float, w: int, h: int) -> int:
        """0 inside the ego-lane trapezoid, -1 left of it, +1 right of it (or above its top)."""
        top = self.p.roi_top_y * h
        if y < top:
            return 1
        frac = (y - top) / max(h - top, 1.0)
        half = (self.p.roi_top_half_width + (self.p.roi_bottom_half_width - self.p.roi_top_half_width) * frac) * w
        dx = x - w / 2
        return 0 if abs(dx) <= half else (-1 if dx < 0 else 1)

    def _change(self, trk: Track, t: int, tracks: list[Track], w: int, h: int) -> tuple[int, LeadChange | None]:
        prev = self.lead
        if prev is None:
            return trk.track_id, None
        if prev["track_id"] == trk.track_id:
            return prev["identity"], prev["change"]
        prev_alive = [x for x in tracks if x.track_id == prev["track_id"]]
        if not prev_alive and iou(trk.bbox, prev["last_bbox"]) >= 0.5 and t - prev["last_t"] <= 1000 * MS:
            return prev["identity"], LeadChange(reason="likely_id_switch", t_ns=t)
        side = [self._in_roi((b[0] + b[2]) / 2, b[3], w, h) for _, b in list(trk.history)[:-1]]
        outside = [s for s in side if s != 0]
        if prev_alive:
            reason = "previous_lead_left"
        elif outside:
            reason = "entered_from_left" if outside[-1] < 0 else "entered_from_right"
        elif trk.hits <= 2:
            reason = "appeared_ahead"
        else:
            reason = "unknown"
        evidence = None
        if reason.startswith("entered"):
            ok = len(outside) >= 3 and self.mount.state == "ok"
            evidence = ChangeEvidence(
                observed_frames_before=len(outside),
                crossed_boundary=True,
                lane_ref="fixed_roi",
                status="ok" if ok else "unreliable",
                reasons=[] if ok else ["few_frames_or_mount_not_ok"],
            )
        return trk.track_id, LeadChange(reason=reason, t_ns=t, evidence=evidence)

    # --- entry points ---------------------------------------------------------------------------
    def placeholder(self, t_ns: int, sched_n: int, run_id: str, seq: int) -> Measurement:
        miss = Q.missing("unavailable", "no_frame")
        return Measurement(
            run_id=run_id,
            seq=seq,
            t_ns=t_ns,
            sched_n=sched_n,
            frame_idx=None,
            observation=Observation(status="unavailable", reasons=["no_frame"]),
            mount_check=MountCheck(state=self.mount.state, since_t_ns=self.mount.since),
            lead=Lead(status="unavailable", reasons=["no_frame"]),
            distance_m=miss,
            ttc_s=miss,
        )

    def process(self, img: np.ndarray, t_ns: int, sched_n: int, frame_idx: int, run_id: str, seq: int) -> Measurement:
        return self.process_detections(img, self.detector(img), t_ns, sched_n, frame_idx, run_id, seq)

    def process_detections(
        self, img: np.ndarray, dets: np.ndarray, t_ns: int, sched_n: int, frame_idx: int, run_id: str, seq: int
    ) -> Measurement:
        h, w = img.shape[:2]
        obs = observation_status(img, self.p)
        mount = self.mount.update(img, t_ns) if self.p.mount_enabled else MountCheck(state="unknown", since_t_ns=0)
        tracks = self.tracker.step(dets, t_ns)
        base = dict(
            run_id=run_id, seq=seq, t_ns=t_ns, sched_n=sched_n, frame_idx=frame_idx, observation=obs, mount_check=mount
        )
        if obs.status != "ok":
            miss = Q.missing("unavailable", "no_observation")
            return Measurement(
                **base, lead=Lead(status="unavailable", reasons=["no_observation"]), distance_m=miss, ttc_s=miss
            )
        inside = [t for t in tracks if self._in_roi((t.bbox[0] + t.bbox[2]) / 2, t.bbox[3], w, h) == 0]
        if not inside:
            self.lead = None
            na = Q.missing("not_applicable", "no_vehicle_in_lane")
            return Measurement(
                **base, lead=Lead(status="not_applicable", reasons=["no_vehicle_in_lane"]), distance_m=na, ttc_s=na
            )
        trk = max(inside, key=lambda t: t.bbox[3])  # closest = lowest bottom edge
        identity, change = self._change(trk, t_ns, tracks, w, h)
        since = self.lead["since"] if self.lead and self.lead["identity"] == identity else t_ns
        self.lead = dict(
            identity=identity, track_id=trk.track_id, since=since, change=change, last_bbox=trk.bbox.copy(), last_t=t_ns
        )
        m, c = self.cfg.mount, self.cfg.camera
        dist = distance_from_bottom(float(trk.bbox[3]), c.fy_px, m.h_cam_m, m.y_horizon_px, m.d_cam_bumper_m)
        x1, y1, x2, y2 = (float(v) for v in trk.bbox)
        if x1 <= 1 or y1 <= 1 or x2 >= w - 2 or y2 >= h - 2:
            ttc = Q.missing("unreliable", "at_image_edge")
        else:
            hist = list(trk.history)
            ttc = ttc_from_widths(
                [t for t, _ in hist],
                [float(b[2] - b[0]) for _, b in hist],
                self.p.ttc_min_frames,
                self.p.ttc_min_bbox_w_px,
                self.p.ttc_max_resid,
            )
        lead = Lead(
            status="ok",
            identity_id=identity,
            track_id=trk.track_id,
            since_t_ns=since,
            basis="fixed_roi",
            bbox_px=(x1, y1, x2, y2),
            det_score=min(1.0, max(0.0, trk.score)),
            change=change,
        )
        return Measurement(**base, lead=lead, distance_m=dist, ttc_s=ttc)
