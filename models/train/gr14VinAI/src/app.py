"""Upload a video and read gr14VinAI's answer next to the radar's, with the difference between the two.

    python src/app.py     # opens http://127.0.0.1:7860

A video file carries no radar. When the uploaded file is one of data/raw/scb*/video.hevc (recognised by its content), its
radar distances are the labels the model is judged on (common.labelled) and the log has one line per labelled frame. Any
other video still runs through the network, with no radar and no delta.

The result is also a 20 fps video with the model's answer drawn on every frame: the lane as it sees it, a bar at the
distance it reports, and a dot where the radar's target is. Below it: a few of the frames where the model reports no vehicle.
"""
import filecmp
import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import gradio as gr
import numpy as np

from common import DATA, H, RAW, ROOT, W, labelled, onnx_session, project, read_yuv_frames, vanishing_point

ONNX = ROOT / "model" / "gr14VinAI.onnx"
SPLIT_NOTE = {"train": "model đã học video này", "val": "dùng để chọn checkpoint và ngưỡng", "test": "model chưa thấy khi huấn luyện"}
PATH_AT, LANE = (20.0, 40.0, 60.0, 80.0, 100.0), 1.5  # as in model.py, repeated here so that the app does not load PyTorch
SCALE = 2  # the video is drawn at twice the size of the network's window
MODEL_COLOUR, RADAR_COLOUR, WHITE = (255, 220, 0), (255, 60, 60), (255, 255, 255)  # RGB
SHOW = 12  # how many of the frames where the model reports no vehicle are shown


def which_scb(video):
    """The dataset video with the same content as this file, or None."""
    size = Path(video).stat().st_size
    return next((v.parent.name for v in RAW.glob("*/video.hevc") if v.stat().st_size == size and filecmp.cmp(v, video, shallow=False)), None)


def radar_of(scb):
    """The split a dataset video is in, and frame_index -> the radar's target as (metres, yRel), None when it has no
    same-lane target within 100 m."""
    splits = json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))["splits"]
    split = next((s for s, scbs in splits.items() if scb in scbs), None)
    return split, {int(r["frame_index"]): (float(r["distance_m"]), float(r["y_rel_m"])) if r["has_target"] == "1" else None
                   for r in (labelled(split) if split else []) if r["scb_id"] == scb}


def picture(frame):
    """A network input frame (common.read_yuv_frames) back as the 512x256 RGB image it was cut from."""
    f = frame.astype(np.uint8)
    y = np.empty((H, W), np.uint8)
    y[0::2, 0::2], y[1::2, 0::2], y[0::2, 1::2], y[1::2, 1::2] = f[:4]
    return cv2.cvtColor(np.concatenate([y.ravel(), f[4:].ravel()]).reshape(H * 3 // 2, W), cv2.COLOR_YUV2RGB_I420)


def pixel(dist, left):
    """A point on the road (metres ahead, metres to the left of the straight axis) -> x, y in the enlarged picture."""
    return (np.stack(project(dist, left), -1) * SCALE).round().astype(np.int32)


def draw(img, lane, m, radar):
    """The picture at SCALE times its size with the model's answer on it: the lane as it sees it (LANE metres either side of
    the centre line it predicts), a bar across that lane at the distance it reports, and a dot at the radar's target.
    lane: the network's lane_left_m [5]; m: its distance, None without a target; radar: (metres, yRel) or None."""
    img = cv2.resize(img, None, fx=SCALE, fy=SCALE)
    centre = lambda d: np.interp(d, (0, *PATH_AT), (0, *lane))  # straight between the knots, as inside the network
    d = np.linspace(4, 100, 49)  # nearer than 4 m the road is below the window
    for side in (-LANE, LANE):
        cv2.polylines(img, [pixel(d, centre(d) + side)], False, MODEL_COLOUR, 1, cv2.LINE_AA)
    if m is not None:
        cv2.line(img, pixel(m, centre(m) + LANE).tolist(), pixel(m, centre(m) - LANE).tolist(), MODEL_COLOUR, 3)
    if radar is not None:
        cv2.circle(img, pixel(*radar).tolist(), 6, RADAR_COLOUR, -1)
    return img


def spread(items, n):
    """At most n of the items, evenly spaced from the first to the last."""
    return [items[k] for k in np.linspace(0, len(items) - 1, min(n, len(items))).round().astype(int)]


def shots(video, frames):
    """Those frames of a video file, as RGB pictures."""
    cap, out = cv2.VideoCapture(video), []
    for i in range(max(frames, default=-1) + 1):  # read in order: seeking to a frame number is not exact in every file
        cap.grab()
        if i in frames:
            out.append(cv2.cvtColor(cap.retrieve()[1], cv2.COLOR_BGR2RGB))
    return out


def metres(v, none="không có xe", sign=""):
    return none if v is None else f"{v:{sign}.2f} m"


def run(video):
    """Run the network over every frame; yields (the log so far, the frame it is on, None, None) at each logged frame and at
    the end (the whole log, the last frame, the 20 fps video with every frame drawn on, SHOW logged frames without a vehicle)."""
    if not video:
        yield "Chưa có video.", None, None, None
        return
    sess = onnx_session(ONNX)
    threshold = json.loads(ONNX.with_suffix(".json").read_text(encoding="utf-8"))["has_target_threshold"]
    scb = which_scb(video)
    split, radar = radar_of(scb) if scb else (None, {})
    if scb:
        vp, fps = vanishing_point(RAW / scb), None
        lines = [f"Video = {scb}, tập {split} ({SPLIT_NOTE[split]}); radar có ở {len(radar)} khung hình." if radar else
                 f"Video = {scb}: không có nhãn radar dùng được (video bị loại khỏi đánh giá), chỉ có số của model."]
    else:
        # ponytail: a video from outside the dataset is taken to come from the same kind of camera (focal 910 px) looking
        # straight ahead (vanishing point at the image centre); give read_yuv_frames its real focal and vanishing point if not
        cap = cv2.VideoCapture(video)
        vp, fps = (cap.get(cv2.CAP_PROP_FRAME_WIDTH) / 2, cap.get(cv2.CAP_PROP_FRAME_HEIGHT) / 2), 20
        lines = ["Video ngoài bộ dữ liệu: không có radar, chỉ có số của model."]
    lines.append("frame |    t    | model | radar | delta = model - radar")
    out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    encoder = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W * SCALE}x{H * SCALE}", "-r", "20",
                                "-i", "-", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    prev, img, pairs = None, None, []  # pairs: (model's metres, radar's target) at every frame that has a radar label
    seen = None  # the newest radar label: frame, target, delta
    logged_frames, empty = 0, []  # empty: the logged frames where the model reports no vehicle
    try:
        for i, frame in enumerate(read_yuv_frames(video, vp, fps=fps)):
            prob, dist, lane = sess.run(None, {"input_imgs": np.concatenate([frame if prev is None else prev, frame])[None]})
            prev = frame
            m = dist.item() if prob.item() > threshold else None
            logged = (i in radar) if radar else (i % 10 == 0)
            if i in radar:
                r = radar[i]
                seen = i, r, m - r[0] if m is not None and r is not None else None
                pairs.append((m, r))
            if logged:
                logged_frames += 1
                if m is None:
                    empty.append(i)
                lines.append(f"{i:5d} | {i / 20:6.2f}s | model {metres(m):>11} | " + (
                    f"radar {metres(seen[1] and seen[1][0]):>11} | delta {metres(seen[2], '—', '+')}" if radar else f"radar {'—':>11} | delta —"))
            # ponytail: the radar is known at the labelled frames only (2 per second), so the video keeps showing a label for
            # the 9 frames after it; a radar answer on every frame needs train.curve's frames_of moved out of that function
            fresh = seen is not None and i - seen[0] <= 9
            img = draw(picture(frame), lane[0], m, seen[1] if fresh else None)
            text = [(f"frame {i}  {i / 20:.2f} s", WHITE), (f"model {metres(m, '--')}  p {prob.item():.2f}", MODEL_COLOUR)]
            if fresh:
                text += [(f"radar {metres(seen[1] and seen[1][0], '--')}", RADAR_COLOUR), (f"delta {metres(seen[2], '--', '+')}", WHITE)]
            for n, (words, colour) in enumerate(text):
                for c, shift in (((0, 0, 0), 2), (colour, 0)):  # black shadow first: readable on a bright road
                    cv2.putText(img, words, (10 + shift, 28 + 26 * n + shift), cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2, cv2.LINE_AA)
            encoder.stdin.write(img.tobytes())
            if logged:
                yield "\n".join(lines), img, None, None
    finally:
        encoder.stdin.close()
        encoder.wait()
    if prev is None:
        lines.append("Không đọc được khung hình nào: ffmpeg không mở được file, hoặc khung hình nhỏ hơn vùng 512x256 quanh tâm ảnh.")
    if pairs:
        d = np.array([m - r[0] for m, r in pairs if m is not None and r is not None])
        lines.append(f"Tổng kết: cả hai cùng thấy xe ở {len(d)}/{len(pairs)} khung"
                     + (f", |delta| trung bình {np.abs(d).mean():.2f} m, delta trung bình {d.mean():+.2f} m" if len(d) else "")
                     + f"; chỉ model thấy xe {sum(m is not None and r is None for m, r in pairs)} khung"
                     + f", chỉ radar thấy xe {sum(m is None and r is not None for m, r in pairs)} khung.")
    shown = spread(empty, SHOW)
    if logged_frames:
        lines.append(f"Model cho là không có xe ở {len(empty)}/{logged_frames} khung trong log; {len(shown)} khung trong số đó ở phần ảnh bên dưới.")
    yield "\n".join(lines), img, out if prev is not None else None, shots(out, shown)


if __name__ == "__main__":
    with gr.Blocks(title="gr14VinAI") as demo:
        gr.Markdown("## gr14VinAI: khoảng cách tới xe phía trước, so với radar\n"
                    "Vàng: làn đường model nhìn thấy (±1,5 m quanh tâm làn) và vạch ngang ở khoảng cách model báo. "
                    "Đỏ: xe theo radar. `--` = không có xe.")
        with gr.Row():
            with gr.Column():
                video = gr.File(label="Video (.hevc, .mp4, ...)", file_types=["video", ".hevc"])
                log = gr.Textbox(label="Log", lines=22, max_lines=22, elem_classes="log")
            with gr.Column():
                live = gr.Image(label="Đang chạy")
                result = gr.Video(label="Kết quả, 20 fps")
        empty = gr.Gallery(label=f"Model cho là không có xe (tối đa {SHOW} khung, rải đều theo thời gian)", columns=4)
        video.upload(run, video, [log, live, result, empty])
    demo.launch(inbrowser=True, css=".log textarea {font-family: monospace}")
