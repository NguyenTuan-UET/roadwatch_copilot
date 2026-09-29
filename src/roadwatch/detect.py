"""Vehicle detector (ONNX Runtime, CPU) and a ByteTrack-style two-stage IoU tracker."""

from collections import deque
from dataclasses import dataclass, field

import cv2
import numpy as np


def postprocess(
    out: np.ndarray, scale: float, pad: tuple[float, float], score_thr: float, nms_iou: float, class_ids: list[int]
) -> np.ndarray:
    """Model output -> [N, 6] (x1, y1, x2, y2, score, cls) in source pixels.

    Accepts YOLO raw heads (1, 4+nc, N: cx, cy, w, h, class scores) and end-to-end heads (1, N, 6: x1, y1, x2,
    y2, score, cls; e.g. NMS-free YOLO26 exports).
    """
    out = np.asarray(out)[0]
    if out.shape[-1] == 6 and out.shape[0] != 6:
        boxes, scores, cls = out[:, :4].astype(np.float32), out[:, 4], out[:, 5].astype(int)
        nms = False
    else:
        out = out.T  # (N, 4+nc)
        cxcywh, cls_scores = out[:, :4], out[:, 4:]
        cls = cls_scores.argmax(axis=1)
        scores = cls_scores[np.arange(len(out)), cls]
        boxes = np.concatenate([cxcywh[:, :2] - cxcywh[:, 2:] / 2, cxcywh[:, :2] + cxcywh[:, 2:] / 2], axis=1)
        nms = True
    keep = (scores >= score_thr) & np.isin(cls, class_ids)
    boxes, scores, cls = boxes[keep], scores[keep], cls[keep]
    if nms and len(boxes):
        xywh = np.concatenate([boxes[:, :2], boxes[:, 2:] - boxes[:, :2]], axis=1)
        idx = np.array(cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), score_thr, nms_iou)).reshape(-1)
        boxes, scores, cls = boxes[idx], scores[idx], cls[idx]  # class-agnostic: car/truck duplicates collapse
    boxes = (boxes - np.array([pad[0], pad[1], pad[0], pad[1]], np.float32)) / scale
    return np.concatenate([boxes, scores[:, None], cls[:, None].astype(np.float32)], axis=1).reshape(-1, 6)


class OnnxDetector:
    """Letterbox -> ONNX Runtime FP32 (intra_op=4, inter_op=1, the reporting standard) -> postprocess."""

    def __init__(
        self, model_path: str, imgsz: int, score_thr: float, nms_iou: float, class_ids: list[int], threads: int = 4
    ):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads, opts.inter_op_num_threads = threads, 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.sess = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.input = self.sess.get_inputs()[0].name
        self.imgsz, self.score_thr, self.nms_iou, self.class_ids = imgsz, score_thr, nms_iou, class_ids

    def __call__(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        s = self.imgsz / max(h, w)
        nh, nw = round(h * s), round(w * s)
        px, py = (self.imgsz - nw) / 2, (self.imgsz - nh) / 2
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, np.uint8)
        top, left = int(round(py - 0.1)), int(round(px - 0.1))
        canvas[top : top + nh, left : left + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        out = self.sess.run(None, {self.input: np.ascontiguousarray(blob)})[0]
        return postprocess(out, s, (left, top), self.score_thr, self.nms_iou, self.class_ids)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    track_id: int
    bbox: np.ndarray
    score: float
    lost: int = 0
    hits: int = 1
    history: deque = field(default_factory=lambda: deque(maxlen=32))  # (t_ns, bbox)


class Tracker:
    """Two-stage association like ByteTrack: high-score detections first, then low-score ones keep tracks alive.

    ponytail: greedy IoU matching without a motion model; ID switches under occlusion are handled downstream as
    likely_id_switch. Upgrade to full ByteTrack (Kalman + Hungarian) if switches dominate the error budget.
    """

    def __init__(self, high_thr: float = 0.5, match_iou: float = 0.3, max_lost: int = 5):
        self.high_thr, self.match_iou, self.max_lost = high_thr, match_iou, max_lost
        self.tracks: list[Track] = []
        self.next_id = 1

    def _match(self, tracks: list[Track], dets: np.ndarray) -> tuple[list, list[Track], list[int]]:
        pairs = sorted(
            ((iou(t.bbox, d[:4]), ti, di) for ti, t in enumerate(tracks) for di, d in enumerate(dets)), reverse=True
        )
        used_t, used_d, matches = set(), set(), []
        for score, ti, di in pairs:
            if score < self.match_iou or ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            matches.append((tracks[ti], dets[di]))
        return (
            matches,
            [t for i, t in enumerate(tracks) if i not in used_t],
            [i for i in range(len(dets)) if i not in used_d],
        )

    def step(self, dets: np.ndarray, t_ns: int) -> list[Track]:
        dets = np.asarray(dets, dtype=np.float32).reshape(-1, 6)
        high, low = dets[dets[:, 4] >= self.high_thr], dets[dets[:, 4] < self.high_thr]
        matched, rest, new_high = self._match(self.tracks, high)
        more, rest, _ = self._match(rest, low)
        for trk, d in matched + more:
            trk.bbox, trk.score, trk.lost, trk.hits = d[:4].copy(), float(d[4]), 0, trk.hits + 1
            trk.history.append((t_ns, trk.bbox.copy()))
        for trk in rest:
            trk.lost += 1
        for i in new_high:
            trk = Track(self.next_id, high[i, :4].copy(), float(high[i, 4]))
            trk.history.append((t_ns, trk.bbox.copy()))
            self.tracks.append(trk)
            self.next_id += 1
        self.tracks = [t for t in self.tracks if t.lost <= self.max_lost]
        return [t for t in self.tracks if t.lost == 0]
