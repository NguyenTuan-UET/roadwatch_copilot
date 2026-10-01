# Tracking + risk engine (P9)

The risk layer has no model of its own. It is deterministic logic over the output of
perception (objects, lanes, signs) and tracking. Everything is in image space: there is
no camera calibration, so there are no metres and no absolute TTC. Every time or
geometry value is an **estimate** and is labelled `(est.)` on the HUD.

```
frame ─► objects (every frame) ─► ByteTracker (+GMC) ─► tracks + kinematics ─┐
      ─► lanes  (every n / worker) ───────────────────► LaneState ────────────┼─► RiskEngine ─► RiskResult
      ─► signs  (every n / worker) ───────────────────► SignReadings ─────────┘      (events, speed limit,
                                                                                       corridor, signs)
```

Code: `roadwatch/tracking/`, `roadwatch/risk/`. Thresholds: `TrackerConfig`, `RiskConfig`
and `EvidenceConfig` in `roadwatch/config.py`. `PerceptionEngine` owns the tracker and the
risk engine and resets both on every new session (new video or seek). `PerceptionResult`
gains `tracks` and `risk`.

## Tracking (`roadwatch/tracking`)

ByteTrack with camera-motion compensation (as in BoT-SORT):

1. Kalman-predict every track (constant velocity on `cx, cy, w, h`, size-proportional noise).
2. **GMC**: sparse optical flow on background corners (detected objects masked out), then a
   RANSAC similarity transform from the previous frame. Tracks and their box histories are
   warped by it, so ego rotation does not look like object motion (~3–5 ms at 640 px wide).
3. High-confidence detections (>= 0.3) vs confirmed and lost tracks, cost `1 - IoU*score`.
4. Low-confidence detections (0.1–0.3) vs tracks still unmatched. This recovers partly
   occluded objects instead of dropping them. For this the detector runs at
   `conf_thr=0.1` when tracking is on. `PerceptionResult.detections` stays filtered at
   `ObjectDetectorConfig.conf_thr`.
5. Tentative tracks vs the remaining high detections. New tracks start at >= 0.35.

Matches across class groups are forbidden: person, two-wheeler, four-wheeler. Within a
group the class is a confidence-weighted vote, because motorcycle/bicycle and car/truck
flicker. A track gets its id when confirmed (2 matches), coasts on its prediction for up
to 5 frames, and is deleted after 1 s without a match.

**Kinematics** (per track, from the observed boxes of the last 0.6 s, at least 5 points
over at least 0.25 s; otherwise `None`, meaning not enough temporal evidence):

| value | meaning |
|---|---|
| `vx_px_s`, `vy_px_s` | box centre / bottom velocity in compensated image pixels per second |
| `scale_rate` | d ln(size)/dt at the latest frame (> 0 = closing in) |
| `tau_s` | time-to-contact from scale expansion, **estimated, uncalibrated**. A line fit of 1/size (linear in time under constant closing speed) gives it at the latest frame rather than half a window late. `None` when not closing. Size is `sqrt(w*h)`; the width alone when the box is cut at the top/bottom (a close lead vehicle), the height alone when cut at a side, none when cut on both |

## Geometry: ego corridor

The corridor is where the car will be if it keeps its lane. Its borders are straight
lines converging at the horizon:

- From the lane result when it is **fresh** (<= 0.5 s old), **good** (quality >=
  `LaneConfig.good_quality`) and covers >= 2 of 3 scan rows. Borders are fitted to the lane
  borders. The horizon is learned (EMA) from their vanishing point. Shown green on the HUD.
- Otherwise a default corridor around the image centre (half width 0.3 W at the bottom).
  Shown grey.

Per track, at its ground-contact row (box bottom):

- `u`: lateral position in lane widths (0 = corridor centre, ±0.5 = borders). Normalising by
  the corridor width at that row removes perspective, so `du/dt` is a lateral speed in lane
  widths per second, without calibration.
- `depth = (y_bottom - horizon) / (H - horizon)`: 0 at the horizon, 1 at the bottom edge
  (inverse distance on a flat road).
- **in path**: the bottom centre is inside the corridor and >= 30% of the box overlaps it.
  The centre test matters: a car being passed in the next lane shows its side, so its box
  reaches well into the corridor.
- Lateral speed is measured on the box edge facing the corridor (the far edge may be cut by
  the image border). It is not estimated when the box bottom touches the image edge,
  because the ground-contact row is then unknown.

## Rules

| rule | targets | caution | warning |
|---|---|---|---|
| **FCW** | lead four-wheeler in path, depth >= 0.2 | tau <= 3.0 s | tau <= 1.8 s |
| **VRU** | person (riders excluded), bicycle, motorcycle; depth >= 0.15 | centre within the corridor + 0.15 and tau <= 3.5 s; or in path, depth >= 0.55 and not receding; or predicted to enter within 1.5 s (lateral speed >= 0.15) | centre within the corridor + 0.15 and tau <= 2.0 s |
| **Cut-in** | four-wheeler beside the corridor (gap <= 0.6 lane widths), depth >= 0.3, moving toward it at 0.15–0.8 lane widths/s, not pulling away | predicted entry <= 1.2 s | entry <= 0.6 s |
| **Cross-traffic** | four-wheeler with lateral speed >= 0.8 lane widths/s, in path or moving toward it | predicted entry <= 1.5 s | entry <= 0.8 s and depth >= 0.3 |
| **LDW** | lane offset (camera centre vs lane centre, lane widths), lane quality gate as above | drifting outward, predicted to reach 0.3 within 1.0 s | \|offset\| >= 0.3 and drifting outward >= 0.05/s |

Notes:

- A person box that overlaps a two-wheeler box by >= 30% of its area, with its centre
  within the two-wheeler's horizontal extent, is a **rider**. Riders are not treated as pedestrians; the two-wheeler track covers them.
- Rules are split by target type, so one road user never triggers two rules: FCW,
  cut-in and cross-traffic take four-wheelers; VRU takes the others.
- A jump of the lane offset by more than 0.5 means a completed lane change. The LDW
  history restarts.

## Temporal evidence (`EvidenceGate`)

Each rule reports a level per key every frame. The key is `(rule, track id)`; for FCW it
is the rule alone, so a lead-vehicle switch does not restart confirmation; for LDW it is
the side. A level becomes an alert when frames at that level span >= 0.3 s and make up
>= 60% of the frames in the last 0.5 s. Escalation happens as soon as it is confirmed. An
alert stays on screen for at least 1 s and ends only after 0.5 s without the condition.
A single-frame blip never alerts.

## Sign relevance and arbitration (`SignArbiter`)

- **Relevant**: box height >= 14 px, and centre right of 0.35 W (right-hand traffic) or
  bottom above 0.35 H (overhead gantry).
- **Confirmed**: the same sign (class; for speed limits, the read value) appears in >= 3
  distinct sign results within 2 s. A sign result reused across frames (live-mode worker,
  replay schedule) counts once.
- **Speed-limit arbitration**: each reading votes with `det_conf × (cls_conf` if read by the
  digit classifier, else `0.7) × (0.5` if classifier and class disagree`)`. The highest
  confirmed value wins only with >= 1.5× the runner-up's votes. Otherwise the limit is kept
  and flagged ambiguous (`50?` on the HUD). The limit persists after the sign passes, until
  a new confirmed limit or an end sign (134 end of speed limit, 135 end of all
  prohibitions).
- Output is informational. The ego speed is unknown, so there is no over-speed warning.

## Session isolation and staleness

- A new `session_id` (new video, seek) resets workers, lane smoothing, the tracker (ids
  restart at 1), all evidence gates, the LDW history, sign votes and the learned horizon.
- Risk rules use a lane result only if it is <= `RiskConfig.lane_max_age_s` (0.5 s) old.
  This is stricter than the display cap (`lane_max_staleness_frames`), because a stale
  lane must not drive LDW.
- Live mode keeps the latest-frame workers for signs and lanes. Tracking and risk run
  synchronously on every frame after the object detector.

## HUD

- Tracks are drawn as `#id class`: thick orange for a caution, thick red for a warning,
  thin while coasting.
- The ego corridor outline is green (from the lane) or grey (default).
- Up to 3 alerts in a banner at the top centre, e.g. `WARNING: FCW #25 tau~1.2s (est.)`.
- Speed-limit badge top right, with recent confirmed signs below it.

## Known limits

- No calibration: tau assumes constant closing speed; depth and lateral units assume a
  flat road and a roughly centred, forward-looking camera.
- The default corridor (no good lane) is a guess; in-path decisions are weaker then.
- Everything depends on detector recall. Tracks cannot exist for objects the detector
  never finds, which is why the object model moved to the iGPU (see
  `docs/perception_benchmark.md`).
- Thresholds were tuned by eye on the two development clips, with no labelled events.
  Retune on your own footage via `RiskConfig`.
