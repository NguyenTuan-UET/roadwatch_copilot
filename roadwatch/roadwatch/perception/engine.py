"""PerceptionEngine: objects every frame + signs and lanes on a schedule.

mode "replay" (default): signs/lanes run synchronously every sign_every_n /
lane_every_n frames and their last result is reused in between.
mode "live": signs/lanes run in latest-frame workers; stale results are dropped.
"""

from __future__ import annotations

import inspect
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from roadwatch.config import ObjectDetectorConfig, PerceptionConfig
from roadwatch.perception.lanes import LaneFrame, LaneModel, LanePipeline, LaneState
from roadwatch.perception.onnx_base import ModelNotAvailable
from roadwatch.perception.speed_digits import (
    SignReading,
    SpeedDigitClassifier,
    read_speed_sign,
)
from roadwatch.cpu import call_in_thread, pin_current_thread, placement
from roadwatch.perception.workers import LatestFrameWorker
from roadwatch.risk import RiskEngine, RiskResult
from roadwatch.tracking import ByteTracker, TrackedObject
from roadwatch.types import Detection, Frame

log = logging.getLogger(__name__)


class _Detector(Protocol):
    def detect(self, img_bgr: np.ndarray) -> list[Any]: ...


@dataclass
class PerceptionResult:
    seq: int
    session_id: str
    detections: list[Detection]
    signs: list[SignReading] | None  # None = no valid (fresh, same-session) result yet
    lane: LaneState | None
    timings_ms: dict[str, float]
    modules_enabled: dict[str, bool]
    lane_frame: LaneFrame | None = None  # masks for drawing; same result as `lane`
    result_age: dict[str, int] = field(default_factory=dict)  # frames since worker input
    tracks: list[TrackedObject] | None = None  # confirmed tracks; None if tracking is off
    risk: RiskResult | None = None  # None if the risk engine is off


class PerceptionEngine:
    """Owns the per-session workers. Models are passed in so they can be reused
    across sessions (loading them is the slow part); see `load_models`."""

    def __init__(
        self,
        object_detector: _Detector | None,
        lane_model: LaneModel | None = None,
        sign_detector: _Detector | None = None,
        config: PerceptionConfig | None = None,
    ):
        self.config = config or PerceptionConfig()
        if self.config.mode not in ("replay", "live"):
            raise ValueError(f"unknown mode {self.config.mode!r}")
        self.live = self.config.mode == "live"
        wcfg = self.config.workers
        self.foreground_cpus, self.background_cpus = placement(wcfg.place_on_hybrid_cores)
        self.object_detector = object_detector
        self.sign_detector = sign_detector
        self.lane_pipeline = LanePipeline(lane_model) if lane_model is not None else None
        cfg = self.config
        self.tracker = (ByteTracker(cfg.tracking)
                        if cfg.enable_tracking and object_detector is not None else None)
        self.risk_engine = (RiskEngine(cfg.risk, cfg.lanes.good_quality)
                            if cfg.enable_risk and self.tracker is not None else None)
        # The tracker wants low-confidence detections too (ByteTrack stage 2);
        # detectors without a conf_thr argument just return what they have.
        self._low_conf_kw = {}
        if self.tracker is not None and "conf_thr" in inspect.signature(
                object_detector.detect).parameters:
            self._low_conf_kw = {"conf_thr": cfg.tracking.low_conf_thr}
        self._seq_ts: deque[tuple[int, float]] = deque(maxlen=300)
        self.modules_enabled = {
            "objects": object_detector is not None,
            "signs": sign_detector is not None,
            "lanes": lane_model is not None,
            "tracking": self.tracker is not None,
            "risk": self.risk_engine is not None,
        }
        self.sign_worker = (
            LatestFrameWorker(self._read_signs, every_n=wcfg.sign_every_n,
                              max_staleness_frames=wcfg.max_staleness_frames, name="signs",
                              nice=wcfg.worker_nice, cpus=self.background_cpus)
            if sign_detector is not None and self.live else None
        )
        self.lane_worker = (
            LatestFrameWorker(self.lane_pipeline, every_n=wcfg.lane_every_n,
                              max_staleness_frames=wcfg.lane_max_staleness_frames, name="lanes",
                              nice=wcfg.worker_nice, cpus=self.background_cpus)
            if self.lane_pipeline is not None and self.live else None
        )
        # Replay mode: last synchronous result per module as (seq, value, latency_ms).
        self._last: dict[str, tuple[int, Any, float]] = {}
        self._session: str | None = None

    @classmethod
    def from_config(cls, config: PerceptionConfig | None = None) -> "PerceptionEngine":
        config = config or PerceptionConfig()
        return cls(*load_models(config), config=config)

    # -- worker functions ------------------------------------------------
    def _read_signs(self, img: np.ndarray) -> list[SignReading]:
        dets = self.sign_detector.detect(img)
        classifier = getattr(self.sign_detector, "speed_classifier", None)
        if classifier is None:
            return [read_speed_sign(d) for d in dets]
        limits = [d for d in dets if d.is_speed_limit]
        readings = dict(zip(map(id, limits), classifier.classify(img, [d.xyxy for d in limits])))
        return [read_speed_sign(d, readings.get(id(d))) for d in dets]

    # -- API -------------------------------------------------------------
    def pin_caller_to_foreground(self) -> None:
        """Call once from the thread that runs process() (P-cores on hybrid CPUs)."""
        pin_current_thread(self.foreground_cpus)

    def open_video(self, path, max_width: int = 1280):
        """Open a video whose decoding runs ahead in a background thread
        (on the background cores in live mode)."""
        from roadwatch.video_io import open_video

        w = self.config.workers
        return open_video(path, max_width=max_width, prefetch=w.decode_prefetch,
                          cpus=self.background_cpus, nice=w.worker_nice if self.live else 0)

    def reset(self, session_id: str) -> None:
        """New source or seek: forget all worker results and lane smoothing."""
        self._session = session_id
        self._last.clear()
        for w in (self.sign_worker, self.lane_worker):
            if w is not None:
                w.reset(session_id)
        if self.lane_pipeline is not None:
            self.lane_pipeline.reset()
        if self.tracker is not None:
            self.tracker.reset()
        if self.risk_engine is not None:
            self.risk_engine.reset()
        self._seq_ts.clear()

    def process(self, frame: Frame) -> PerceptionResult:
        if frame.session_id != self._session:
            self.reset(frame.session_id)
        if not self.live:
            return self._process_replay(frame)
        t0 = time.perf_counter()
        timings: dict[str, float] = {}

        if self.sign_worker is not None or self.lane_worker is not None:
            # One private copy shared (read-only) by both workers, so the caller
            # may draw on frame.image right away.
            shared = frame.image.copy()
            for w in (self.sign_worker, self.lane_worker):
                if w is not None:
                    w.submit(shared, frame.session_id, frame.seq)
        timings["submit"] = (time.perf_counter() - t0) * 1000

        detections: list[Detection] = []
        if self.object_detector is not None:
            t = time.perf_counter()
            detections = self.object_detector.detect(frame.image, **self._low_conf_kw)
            timings["objects"] = (time.perf_counter() - t) * 1000

        ages: dict[str, int] = {}
        signs = None
        if self.sign_worker is not None:
            r = self.sign_worker.get_latest_result(frame.session_id, frame.seq)
            if r is not None:
                signs = r.value
                timings["signs"] = r.latency_ms
                ages["signs"] = frame.seq - r.seq
        lane_frame = None
        if self.lane_worker is not None:
            r = self.lane_worker.get_latest_result(frame.session_id, frame.seq)
            if r is not None:
                lane_frame = r.value
                timings["lanes"] = r.latency_ms
                ages["lanes"] = frame.seq - r.seq

        return self._finish(frame, t0, detections, signs, lane_frame, timings, ages)

    def _process_replay(self, frame: Frame) -> PerceptionResult:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        wcfg = self.config.workers
        detections: list[Detection] = []
        if self.object_detector is not None:
            t = time.perf_counter()
            detections = self.object_detector.detect(frame.image, **self._low_conf_kw)
            timings["objects"] = (time.perf_counter() - t) * 1000

        scheduled = (("signs", self.sign_detector, self._read_signs, wcfg.sign_every_n),
                     ("lanes", self.lane_pipeline, self.lane_pipeline, wcfg.lane_every_n))
        ages: dict[str, int] = {}
        values: dict[str, Any] = {}
        for name, model, fn, every_n in scheduled:
            if model is None:
                continue
            if frame.seq % every_n == 0 or name not in self._last:
                t = time.perf_counter()
                value = fn(frame.image)
                self._last[name] = (frame.seq, value, (time.perf_counter() - t) * 1000)
            seq, values[name], timings[name] = self._last[name]
            ages[name] = frame.seq - seq

        return self._finish(frame, t0, detections, values.get("signs"), values.get("lanes"),
                            timings, ages)

    def _age_s(self, frame: Frame, age: int | None) -> float | None:
        """Seconds between this frame and the frame `age` frames earlier."""
        if age is None:
            return None
        want = frame.seq - age
        for seq, ts in self._seq_ts:
            if seq == want:
                return frame.ts - ts
        return None  # older than the kept history: treat as unknown (= stale)

    def _finish(self, frame: Frame, t0: float, detections: list[Detection], signs,
                lane_frame: LaneFrame | None, timings: dict[str, float],
                ages: dict[str, int]) -> PerceptionResult:
        """Tracking + risk on top of this frame's perception, then the result."""
        self._seq_ts.append((frame.seq, frame.ts))
        tracks = risk = None
        if self.tracker is not None:
            t = time.perf_counter()
            tracks = self.tracker.update(detections, frame.ts, frame.image)
            timings["tracking"] = (time.perf_counter() - t) * 1000
            thr = self.config.objects.conf_thr
            detections = [d for d in detections if d.conf >= thr]
        lane = lane_frame.state if lane_frame is not None else None
        if self.risk_engine is not None:
            t = time.perf_counter()
            risk = self.risk_engine.update(
                frame.ts, frame.image.shape[:2], tracks,
                lane=lane,
                lane_seq=frame.seq - ages["lanes"] if "lanes" in ages else None,
                lane_age_s=self._age_s(frame, ages.get("lanes")),
                signs=signs,
                signs_seq=frame.seq - ages["signs"] if "signs" in ages else None,
            )
            timings["risk"] = (time.perf_counter() - t) * 1000
        timings["total"] = (time.perf_counter() - t0) * 1000
        return PerceptionResult(
            seq=frame.seq,
            session_id=frame.session_id,
            detections=detections,
            signs=signs,
            lane=lane,
            timings_ms=timings,
            modules_enabled=dict(self.modules_enabled),
            lane_frame=lane_frame,
            result_age=ages,
            tracks=tracks,
            risk=risk,
        )

    def worker_stats(self) -> dict[str, Any]:
        return {
            name: w.stats for name, w in (("signs", self.sign_worker), ("lanes", self.lane_worker))
            if w is not None
        }

    def close(self) -> None:
        for w in (self.sign_worker, self.lane_worker):
            if w is not None:
                w.stop(self.config.workers.stop_timeout_s)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def gpu_available() -> bool:
    try:
        import openvino as ov
    except ImportError:
        return False
    return any(d.startswith("GPU") for d in ov.Core().available_devices)


def apply_gpu(config: PerceptionConfig) -> bool:
    """If config.use_gpu and an OpenVINO GPU exists, move the models to it (in place).
    Returns whether the GPU is used."""
    if not config.use_gpu or not gpu_available():
        return False
    for c in (config.objects, config.lanes, config.signs):
        c.device = "GPU"
    model = config.gpu_object_model_live if config.mode == "live" else \
        config.gpu_object_model_replay
    if config.objects.model_path != ObjectDetectorConfig().model_path:
        pass  # an explicitly chosen object model is kept, just run on the GPU
    elif model.exists():
        config.objects.model_path = model
    else:
        log.warning("GPU object model %s not exported; keeping %s", model.name,
                    config.objects.model_path.name)
    log.info("Using the iGPU: objects=%s", config.objects.model_path.name)
    return True


def load_models(config: PerceptionConfig | None = None):
    """Load (objects, lanes, signs) models; a missing model disables its module.

    Each missing model is logged once, here, at load time. Models are created
    in threads that already have their CPU placement so the inference thread
    pools inherit it: in live mode P-cores for objects and E-cores +
    WorkerConfig.worker_nice for lanes/signs; in replay mode everything runs
    one after another on the P-cores with the object detector's thread count.
    """
    from roadwatch.perception.objects import ObjectDetector
    from roadwatch.perception.signs import SignDetector

    config = config or PerceptionConfig()
    apply_gpu(config)

    def try_load(name: str, enabled: bool, factory):
        if not enabled:
            return None
        try:
            return factory()
        except ModelNotAvailable as e:
            log.warning("%s module disabled: %s", name, e)
            return None

    fg, bg = placement(config.workers.place_on_hybrid_cores)
    if config.mode == "live":
        nice, bg_cpus, bg_threads = config.workers.worker_nice, bg, {}
    else:
        nice, bg_cpus, bg_threads = 0, fg, {"num_threads": config.objects.num_threads}
    objects = try_load("objects", config.enable_objects, lambda: call_in_thread(
        lambda: ObjectDetector(config.objects), 0, fg))
    lanes = try_load("lanes", config.enable_lanes, lambda: call_in_thread(
        lambda: LaneModel(config.lanes, **bg_threads), nice, bg_cpus))
    signs = try_load("signs", config.enable_signs, lambda: call_in_thread(
        lambda: SignDetector(config.signs, **bg_threads), nice, bg_cpus))
    if signs is not None:
        # Runs inside the sign worker/step, so it shares the sign placement.
        signs.speed_classifier = try_load("speed_digits", True, lambda: call_in_thread(
            lambda: SpeedDigitClassifier(config.speed_digits), nice, bg_cpus))
    return objects, lanes, signs
