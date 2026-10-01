import os
from pathlib import Path

import numpy as np
import pytest

from roadwatch.config import ObjectDetectorConfig
from roadwatch.perception.yolo import check_output_shape, decode_yolo, preprocess

NC = 80


def fake_output(anchors, n=100):
    """Build a (1, 84, n) YOLO output; anchors = [(cx, cy, w, h, class_id, score), ...]."""
    out = np.zeros((1, 4 + NC, n), dtype=np.float32)
    for i, (cx, cy, w, h, cid, score) in enumerate(anchors):
        out[0, :4, i] = (cx, cy, w, h)
        out[0, 4 + cid, i] = score
    return out


def test_decode_filters_conf_class_and_converts_xyxy():
    out = fake_output(
        [
            (100, 100, 40, 20, 2, 0.9),  # car, kept
            (200, 200, 10, 10, 0, 0.30),  # person below conf -> dropped
            (50, 50, 10, 10, 9, 0.95),  # traffic light, not in keep set -> dropped
        ]
    )
    boxes, scores, cids = decode_yolo(out, NC, 0.35, 0.5, {0, 1, 2, 3, 5, 7})
    assert cids.tolist() == [2]
    np.testing.assert_allclose(boxes[0], [80, 90, 120, 110])
    assert scores[0] == pytest.approx(0.9)


def test_decode_nms_is_per_class():
    out = fake_output(
        [
            (100, 100, 50, 50, 2, 0.9),  # car
            (102, 101, 50, 50, 2, 0.8),  # duplicate car -> suppressed
            (101, 100, 50, 50, 0, 0.7),  # person on same spot -> kept (different class)
        ]
    )
    _, scores, cids = decode_yolo(out, NC, 0.35, 0.5, None)
    assert sorted(cids.tolist()) == [0, 2]
    assert sorted(scores.tolist()) == pytest.approx([0.7, 0.9])


def test_decode_empty():
    boxes, scores, cids = decode_yolo(fake_output([]), NC, 0.35, 0.5, None)
    assert boxes.shape == (0, 4) and scores.size == 0 and cids.size == 0


@pytest.mark.parametrize(
    "shape, ok",
    [
        ([1, 84, 2100], True),
        (["batch", 84, "anchors"], True),
        ([1, 2100, 84], False),  # transposed
        ([1, 85, 2100], False),  # YOLOv5-style with objectness
        ([1, 84], False),
        ([2, 84, 2100], False),
    ],
)
def test_check_output_shape(shape, ok):
    if ok:
        check_output_shape(shape, NC)
    else:
        with pytest.raises(ValueError):
            check_output_shape(shape, NC)


def test_preprocess_layout_and_rgb():
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    img[:, :, 0] = 255  # blue channel in BGR
    tensor, ratio, pad = preprocess(img, (320, 320))
    assert tensor.shape == (1, 3, 320, 320) and tensor.dtype == np.float32
    center = tensor[0, :, 160, 160]
    np.testing.assert_allclose(center, [0.0, 0.0, 1.0])  # RGB order: blue is last
    assert ratio == pytest.approx(1.6) and pad == (0.0, 80.0)


def test_postprocess_maps_to_original_image(tmp_path, monkeypatch):
    """Postprocess without a real model: bypass __init__ and reuse the method."""
    from roadwatch.perception.objects import ObjectDetector

    det = ObjectDetector.__new__(ObjectDetector)
    det.det_config = ObjectDetectorConfig()
    det._keep_ids = set(det.det_config.keep_classes)
    det._nms_group_of = ObjectDetector.nms_group_map(det.det_config)

    # Original 720x1280 -> letterbox 320: ratio 0.25, pad (0, 70).
    out = fake_output([(160, 160, 40, 20, 2, 0.8)])
    dets = det.postprocess(out, 0.25, (0.0, 70.0), (720, 1280))
    assert len(dets) == 1
    d = dets[0]
    assert d.cls == "car" and d.conf == pytest.approx(0.8)
    np.testing.assert_allclose(d.xyxy, [560, 320, 720, 400], atol=1e-3)


# ---------------------------------------------------------------- integration

MODEL = ObjectDetectorConfig().model_path
VIDEO = Path(
    os.environ.get("ROADWATCH_TEST_VIDEO", Path(__file__).parents[1] / "video/segment_000.mp4")
)


@pytest.mark.models
@pytest.mark.skipif(not MODEL.exists(), reason=f"model missing: {MODEL}")
@pytest.mark.skipif(not VIDEO.exists(), reason=f"sample video missing: {VIDEO}")
def test_detects_vehicle_on_sample_video():
    from roadwatch.perception.objects import ObjectDetector

    from roadwatch.video_io import open_video

    det = ObjectDetector()
    vehicles = frames = 0
    with open_video(VIDEO) as reader:
        for frame in reader:
            frames += 1
            vehicles += sum(d.cls in {"car", "bus", "truck", "motorcycle"} for d in det.detect(frame))
            if frames == 30:
                break
    if frames == 0:
        pytest.skip(f"cannot decode {VIDEO}")
    assert vehicles >= 1


GROUP_OF = {1: 100, 3: 100, 2: 101, 5: 101, 7: 101}  # two-wheelers, four-wheelers; person ungrouped


def test_decode_nms_by_group_merges_car_and_truck_on_one_vehicle():
    out = fake_output(
        [
            (100, 100, 50, 40, 2, 0.62),  # car
            (101, 101, 50, 42, 7, 0.48),  # truck, same vehicle
            (101, 98, 20, 45, 0, 0.70),  # person on the same spot (e.g. rider) -> kept
        ]
    )
    _, _, per_class = decode_yolo(out, NC, 0.1, 0.5, None)
    assert sorted(per_class.tolist()) == [0, 2, 7]  # the duplicate this option removes
    _, scores, cids = decode_yolo(out, NC, 0.1, 0.5, None, GROUP_OF)
    assert sorted(cids.tolist()) == [0, 2]
    assert sorted(scores.tolist()) == pytest.approx([0.62, 0.70])


def test_decode_nms_by_group_keeps_separate_vehicles():
    out = fake_output([(100, 100, 50, 40, 2, 0.9), (300, 100, 50, 40, 7, 0.8)])
    _, _, cids = decode_yolo(out, NC, 0.1, 0.5, None, GROUP_OF)
    assert sorted(cids.tolist()) == [2, 7]


def e2e_output(rows, n=300):
    """Build a (1, n, 6) NMS-free output; rows = [(x1, y1, x2, y2, score, class_id), ...]."""
    out = np.zeros((1, n, 6), dtype=np.float32)
    for i, r in enumerate(rows):
        out[0, i] = r
    return out


def test_decode_end2end_filters_and_sorts():
    from roadwatch.perception.yolo import decode_end2end, is_end2end_output

    out = e2e_output([
        (10, 10, 50, 40, 0.5, 2),  # car
        (60, 60, 90, 99, 0.9, 0),  # person
        (5, 5, 9, 9, 0.2, 2),  # below conf
        (0, 0, 20, 20, 0.95, 9),  # traffic light, not kept
    ])
    assert is_end2end_output(out.shape) and not is_end2end_output((1, 84, 2100))
    boxes, scores, cids = decode_end2end(out, 0.35, {0, 1, 2, 3, 5, 7})
    assert cids.tolist() == [0, 2]
    assert scores.tolist() == pytest.approx([0.9, 0.5])
    np.testing.assert_allclose(boxes[1], [10, 10, 50, 40])


def test_decode_end2end_group_nms_merges_car_and_truck():
    from roadwatch.perception.yolo import decode_end2end

    out = e2e_output([(100, 100, 150, 140, 0.6, 2), (101, 99, 151, 142, 0.5, 7),
                      (110, 90, 130, 140, 0.7, 0)])
    _, _, cids = decode_end2end(out, 0.1, None, GROUP_OF)
    assert sorted(cids.tolist()) == [0, 2]


def test_postprocess_end2end_maps_to_original_image():
    from roadwatch.perception.objects import ObjectDetector

    det = ObjectDetector.__new__(ObjectDetector)
    det.det_config = ObjectDetectorConfig()
    det._keep_ids = set(det.det_config.keep_classes)
    det._nms_group_of = ObjectDetector.nms_group_map(det.det_config)
    det.end2end = True
    # Original 720x1280 -> letterbox 320: ratio 0.25, pad (0, 70).
    dets = det.postprocess(e2e_output([(140, 150, 180, 170, 0.8, 2)]), 0.25, (0.0, 70.0),
                           (720, 1280))
    assert len(dets) == 1 and dets[0].cls == "car"
    np.testing.assert_allclose(dets[0].xyxy, [560, 320, 720, 400], atol=1e-3)
