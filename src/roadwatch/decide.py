"""Demo BT-B: decide whether to speak, at which level, and why. Pure: time comes from the frame clock.

Rules of requirements file 2 (BT-B): early Info on a closing trend, Warning below the legal gap (TT 38/2024)
after a confirmation time with hysteresis, Emergency on low TTC at once, cut-in grace, congestion (< 60 km/h)
turns the distance alerts off but keeps the TTC one, per-kind cooldown, highest level first.
Parameters are provisional values of the proposed configuration (not tuned; changes go through HITL).
ponytail: demo subset of spec 3.3-3.7 (no capability debounce, no audio arbiter); restore the full engine for MVP.
"""
from dataclasses import dataclass, field

LEGAL = [(60.0, 60.0, 35.0), (60.0, 80.0, 55.0), (80.0, 100.0, 70.0), (100.0, 120.0, 100.0)]  # v0.yaml legal_table
TTC_EMERGENCY_S, H_TTC_S, T_CLEAR_E_S = 1.8, 0.5, 1.5
T_CONFIRM_S, H_M, T_CLEAR_S, COOLDOWN_S = 1.5, 5.0, 2.0, 10.0
INFO_HORIZON_S = 3.0     # requirements file 2 example: "dự báo 3 giây nữa sẽ xuống dưới ngưỡng"
GRACE_S = 4.0            # requirements file 2 example: cut-in grace of 4 s
CUT_IN_DROP_M = 10.0     # gap falling this much between frames = a new lead vehicle
PHRASES = {'emergency': 'Phanh! Xe trước', 'warning': 'Giãn thêm khoảng cách', 'info': 'Xe trước đang gần lại'}
RANK = {'emergency': 3, 'warning': 2, 'info': 1}


def legal_gap(kmh):
    """Minimum gap (m) of TT 38/2024 art. 11.1, or None below 60 km/h where the law gives no value."""
    for lo, hi, d in LEGAL:
        if lo <= kmh <= hi:
            return d
    return LEGAL[-1][2] if kmh > LEGAL[-1][1] else None


@dataclass
class Decision:
    level: str | None        # level of the active situation (shown), None = safe
    say: str | None          # kind spoken on this frame, None = silent
    reason: str
    threshold_m: float | None
    raw: set = field(default_factory=set)   # kinds whose raw condition holds (no dispatch rules)


class Decider:
    def __init__(self):
        self.prev_gap = None
        self.grace_until = -1.0
        self.below_since = self.above_since = self.e_clear_since = None
        self.warn_active = self.e_active = False
        self.last_said = {}
        self.slope = 0.0

    def step(self, t, gap, ego_mps, ttc, calibrated, ttc_ok=True):
        kmh = ego_mps * 3.6
        d = legal_gap(kmh)
        raw = set()
        # Emergency: TTC alone; independent of speed and of distance calibration.
        if ttc_ok and ttc is not None and ttc <= TTC_EMERGENCY_S:
            raw.add('emergency')
            self.e_clear_since = None
            if not self.e_active:
                self.e_active = True
                return self._say(t, 'emergency', f'TTC {ttc:.1f} s ≤ {TTC_EMERGENCY_S} s: phát ngay', d, raw)
        elif self.e_active:
            if ttc is None or ttc > TTC_EMERGENCY_S + H_TTC_S:
                self.e_clear_since = t if self.e_clear_since is None else self.e_clear_since
                if t - self.e_clear_since >= T_CLEAR_E_S:
                    self.e_active = False
        if self.e_active:
            return Decision('emergency', None, 'Khẩn cấp: đã phát trong đợt này', d, raw)

        if gap is None:
            self.prev_gap, self.below_since = None, None
            return Decision(None, None, 'Không có xe trước đủ tin cậy', d, raw)
        if self.prev_gap is None or self.prev_gap - gap > CUT_IN_DROP_M:
            self.grace_until, self.slope = t + GRACE_S, 0.0   # new lead vehicle
        else:
            self.slope = 0.9 * self.slope + 0.1 * (gap - self.prev_gap) * 20   # m/s, frames at 20 Hz
        self.prev_gap = gap
        if not calibrated:
            return Decision(None, None, 'Đang hiệu chuẩn: chưa cảnh báo khoảng cách', d, raw)
        if d is None:
            self.below_since = None
            return Decision(None, None, f'Ùn tắc ({kmh:.0f} km/h < 60): tắt nhắc khoảng cách, vẫn giữ cảnh báo va chạm',
                            d, raw)
        margin = d + (H_M if self.warn_active else 0.0)          # hysteresis around the threshold
        if gap < margin:
            raw.add('warning')
            self.above_since = None
            self.below_since = t if self.below_since is None else self.below_since
        else:
            self.below_since = None
            if self.warn_active:
                self.above_since = t if self.above_since is None else self.above_since
                if t - self.above_since >= T_CLEAR_S:
                    self.warn_active = False
        forecast = gap + self.slope * INFO_HORIZON_S
        if gap >= d and forecast < d:
            raw.add('info')
        if t < self.grace_until and raw - {'emergency'}:
            return Decision(None, None, f'Ân hạn xe mới chen vào: còn {self.grace_until - t:.1f} s', d, raw)
        if 'warning' in raw and t - self.below_since >= T_CONFIRM_S:
            self.warn_active = True
            if self._ready(t, 'warning'):
                return self._say(t, 'warning', f'{gap:.0f} m < ngưỡng {d:.0f} m quá {T_CONFIRM_S} s', d, raw)
            return Decision('warning', None, f'Dưới ngưỡng {d:.0f} m, đang trong thời gian chờ nhắc lại', d, raw)
        if 'warning' in raw:
            return Decision(None, None, f'Dưới ngưỡng, chờ xác nhận {T_CONFIRM_S} s', d, raw)
        if 'info' in raw:
            if self._ready(t, 'info'):
                return self._say(t, 'info', f'{gap:.0f} m, dự báo {forecast:.0f} m sau {INFO_HORIZON_S:.0f} s', d, raw)
            return Decision('info', None, 'Đang thu hẹp, trong thời gian chờ nhắc lại', d, raw)
        return Decision(None, None, f'An toàn: {gap:.0f} m ≥ ngưỡng {d:.0f} m', d, raw)

    def _ready(self, t, kind):
        return t - self.last_said.get(kind, -1e9) >= COOLDOWN_S

    def _say(self, t, kind, reason, d, raw):
        self.last_said[kind] = t
        return Decision(kind, kind, reason, d, raw)
