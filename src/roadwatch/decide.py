"""Demo BT-B: decide whether to speak, at which level, and why. Pure: time comes from the frame clock.

Plan: docs/warning_to_do.md. Distance only, no TTC: it never claims a collision or the seconds left. An early reminder,
short sounds when it is urgent, and repeats that follow how the gap evolves, within one episode per lead vehicle.
Every number below is a test value, not a tuned or validated one.
ponytail: demo subset of spec 3.3-3.7 (no capability debounce, no audio arbiter); restore the full engine for MVP.
"""
from dataclasses import dataclass, field

LEGAL = [(60.0, 60.0, 35.0), (60.0, 80.0, 55.0), (80.0, 100.0, 70.0), (100.0, 120.0, 100.0)]  # v0.yaml legal_table
V_STOP_KMH, V_CRAWL_KMH = 5.0, 20.0     # standing still below 5; crawling up to 20: silent until near range is validated
NOTICE_S, WARN_S, SHORT_FRAC = 3.0, 2.0, 0.5   # own travel in 3 s / 2 s below 60 km/h; "far too close" = half the warning
BUFFER_FRAC, LATENCY_S = 0.15, 0.3      # 60-100 km/h early zone: legal gap + 15 % (field error) + 0.3 s of latency
MAX_RANGE_M = 100.0                     # what gr14VinAI measures: an early zone beyond it becomes a chime on sight
T_LEAD_OK, T_CONFIRM, T_CONFIRM_E = 0.5, 0.5, 0.2
REPEAT_FIRST, REPEAT_NEXT = 3.0, 10.0
IMPROVE_MPS, CLOSE_FAST_MPS, T_CLOSE_FAST = 0.5, -5.0, 0.5
T_CLEAR, CLEAR_HYST_M, T_LOST = 3.0, 3.0, 3.0
SLOPE_TAU_S = 0.5    # time constant of the gap rate (frame-rate independent)
MAX_AGE_S = 0.5      # runtime.max_measurement_age_ms: an older previous sample starts the rate over
JUMP_M = 10.0        # gap jump between two samples = another vehicle: start the rate over, same episode
PHRASES = {'chime': '(tiếng chuông)', 'info': 'Xe phía trước đang gần lại',
           'warning': 'Chú ý giữ khoảng cách xe phía trước', 'emergency': '(ba tiếng bíp)'}
RANK = {'chime': 1, 'info': 2, 'warning': 3, 'emergency': 4}


def legal_gap(kmh):
    """Minimum gap (m) of TT 38/2024 art. 11.1, or None below 60 km/h where the law gives no value."""
    for lo, hi, d in LEGAL:
        if lo <= kmh <= hi:
            return d
    return LEGAL[-1][2] if kmh > LEGAL[-1][1] else None


def thresholds(kmh):
    """(early reminder, warning, far too close) gaps in m at this speed, or None below V_CRAWL_KMH. The early one is
    None when it would lie beyond MAX_RANGE_M: then a chime on the first confirmed sight replaces it."""
    if kmh < V_CRAWL_KMH:
        return None
    v, d = kmh / 3.6, legal_gap(kmh)
    if d is None:
        early, warn = v * NOTICE_S, v * WARN_S
    else:
        early, warn = d * (1 + BUFFER_FRAC) + v * LATENCY_S, d if d < MAX_RANGE_M else v * WARN_S
    return (early if early <= MAX_RANGE_M else None), warn, warn * SHORT_FRAC


@dataclass
class Decision:
    level: str | None        # level shown, None = nothing to show
    say: str | None          # kind spoken on this frame, None = silent
    reason: str
    threshold_m: float | None   # warning gap at this speed
    raw: set = field(default_factory=set)   # levels whose raw condition holds (no confirmation, no repeat rules)


class Decider:
    def __init__(self):
        self.prev_gap = self.prev_t = None
        self.slope = 0.0
        self.seen = self.lost = self.fast = self.clear = None   # since when: lead seen, lost, closing fast, clear
        self.since = {}          # level -> since when its raw condition holds
        self._end()

    def _end(self):
        self.episode, self.top, self.count, self.last_t = False, 0, 0, None

    def step(self, t, gap, ego_mps, calibrated, ok=True):
        kmh = ego_mps * 3.6
        th = thresholds(kmh)
        warn = th[1] if th else None
        if gap is None or not ok:
            self.prev_gap, self.seen, self.fast, self.clear, self.since = None, None, None, None, {}
            self.lost = t if self.lost is None else self.lost
            if self.episode and t - self.lost > T_LOST:
                self._end()
            return Decision(None, None, 'Không có xe trước đủ tin cậy', warn)
        self.lost = None
        self._rate(t, gap)
        self.seen = t if self.seen is None else self.seen
        if not calibrated or th is None:
            self.fast, self.since = None, {}
            return Decision(None, None, 'Đang hiệu chuẩn: chưa cảnh báo khoảng cách' if not calibrated else
                            f'Đứng yên ({kmh:.0f} km/h): không nhắc' if kmh < V_STOP_KMH else
                            f'Bò chậm ({kmh:.0f} km/h): chưa nhắc khoảng cách', warn)
        early, warn, short = th
        zone = MAX_RANGE_M if early is None else early
        self.fast = (t if self.fast is None else self.fast) if self.slope <= CLOSE_FAST_MPS and gap < zone else None
        raw = {k for k, on in (('info', early is not None and gap < early), ('warning', gap < warn),
                               ('emergency', gap < short or (self.fast is not None and t - self.fast >= T_CLOSE_FAST)))
               if on}
        self.since = {k: self.since.get(k, t) for k in raw}
        level = max((k for k in raw if t - self.since[k] >= (T_CONFIRM_E if k == 'emergency' else T_CONFIRM)),
                    key=RANK.get, default=None)
        self.clear = (t if self.clear is None else self.clear) if gap >= zone + CLEAR_HYST_M else None
        if self.clear is not None and t - self.clear >= T_CLEAR:
            self._end()
        if t - self.seen < T_LEAD_OK:
            return Decision(None, None, 'Đang xác nhận xe dẫn đầu', warn, raw)
        if level and RANK[level] > self.top:   # first sound of the episode or a higher level: at once
            self.episode, self.top, self.count = True, RANK[level], 0
            return self._say(t, level, self._why(level, gap, early, warn, short), warn, raw)
        if early is None and not self.episode:
            self.episode, self.top, self.count = True, RANK['chime'], 0
            return self._say(t, 'chime', f'Xe dẫn đầu {gap:.0f} m ở {kmh:.0f} km/h: chuông nhắc phòng ngừa', warn, raw,
                             'info')
        if level:
            if self.slope > IMPROVE_MPS:
                return Decision(level, None, f'{gap:.0f} m: đang giãn ra, không nhắc lặp', warn, raw)
            if t - self.last_t >= (REPEAT_FIRST if self.count == 1 else REPEAT_NEXT):
                return self._say(t, level, 'Nhắc lại: ' + self._why(level, gap, early, warn, short), warn, raw)
            return Decision(level, None, f'{gap:.0f} m: đang theo dõi', warn, raw)
        if self.episode:   # above the levels but not clear for T_CLEAR yet; a chime episode stays shown
            return Decision('info' if early is None else None, None, f'{gap:.0f} m: đang theo dõi', warn, raw)
        return Decision(None, None, f'An toàn: {gap:.0f} m ≥ {early:.0f} m', warn, raw)

    def _rate(self, t, gap):
        """Gap rate (m/s, < 0 closing): exponential average by the frame clock, restarted after a stale or jumping sample."""
        dt = None if self.prev_gap is None else t - self.prev_t
        if dt is None or dt > MAX_AGE_S or abs(gap - self.prev_gap) > JUMP_M:
            self.slope, self.fast = 0.0, None
        elif dt > 0:
            self.slope += min(1.0, dt / SLOPE_TAU_S) * ((gap - self.prev_gap) / dt - self.slope)
        self.prev_gap, self.prev_t = gap, t

    def _why(self, level, gap, early, warn, short):
        if level == 'emergency':
            return f'{gap:.0f} m < {short:.0f} m: thiếu nhiều' if gap < short else \
                f'Khoảng cách giảm nhanh ({self.slope:.1f} m/s)'
        if level == 'warning':
            return f'{gap:.0f} m < {warn:.0f} m: dưới khoảng cách cơ sở'
        return f'{gap:.0f} m < {early:.0f} m: vào vùng nhắc sớm'

    def _say(self, t, kind, reason, warn, raw, level=None):
        self.last_t, self.count = t, self.count + 1
        return Decision(level or kind, kind, reason, warn, raw)
