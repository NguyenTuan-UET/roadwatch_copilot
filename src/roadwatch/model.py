"""gr14VinAI inference on CPU: video decode, warp into the model frame, YUV packing, state queues.

Ported from comma_ai/lead_distance (realtime_lead.py, lead_distance.py; copied, not imported): bilinear
cv2.warpPerspective of the Y, U, V planes, channels Y[0::2,0::2], Y[1::2,0::2], Y[0::2,1::2], Y[1::2,1::2], U, V;
the wide input is the same picture warped with the wide virtual camera when the lens is wider than 60 deg,
else the narrow input duplicated; letterbox/pillarbox bars are cropped; the model is fed every n-th frame
(a constant tick close to 20 Hz) and its velocities are rescaled to the true tick.
"""
import base64
import io
import pickle
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from g01T014VinAI.common.transformations.model import get_warp_matrix
from g01T014VinAI.selfdrive.modeld.parse_model_outputs import Parser

PRUNED_PATH = Path(__file__).resolve().parents[2] / 'models/gr14VinAI.onnx'  # the only model used; not committed
MODEL_HZ = 20   # gr14VinAI's training frame rate
MODEL_SHA256 = '65a08adc31d5c456219687d99b7bf5e44d61dae2d49ea67850e76105c7248cce'


MODEL_DT = 1 / MODEL_HZ
MODEL_W, MODEL_H = 512, 256
WIDE_HFOV_DEG = 60   # wider lens: warp the wide input with the wide virtual camera, else duplicate the narrow one


def tick(fps):
    """Feed the model every `stride`-th frame: (stride, tick_dt, vel_scale). The model assumes 50 ms between
    frames, so its velocities are multiplied by vel_scale = MODEL_DT / tick_dt."""
    stride = max(1, round(fps * MODEL_DT))
    tick_dt = stride / fps
    return stride, tick_dt, MODEL_DT / tick_dt


def _probe(path, entries, *extra):
    return subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', *extra, '-show_entries', entries,
                           '-of', 'csv=p=0', str(path)], capture_output=True, text=True).stdout.split()


def _gray(path, w, h, args):
    """Gray frames ffmpeg outputs for `args` (input options + -i path + output options)."""
    data = subprocess.run(['ffmpeg', '-v', 'error', *args, '-vf', 'format=gray', '-f', 'rawvideo', '-'],
                          capture_output=True).stdout
    return list(np.frombuffer(data[:len(data) // (w * h) * w * h], np.uint8).reshape(-1, h, w))


def video_fps(path):
    """Frame rate the file itself reports (average, else nominal), or None: unreadable, or a raw stream (.hevc, .h264)
    whose rate is a default, not a measurement. Used to flag a different `fps` the user entered."""
    if Path(path).suffix.lower() in ('.hevc', '.h265', '.h264', '.264', '.265'):
        return None
    for rate in _probe(path, 'stream=avg_frame_rate,r_frame_rate', '-select_streams', 'v:0')[:1]:
        for part in rate.split(','):
            num, _, den = part.partition('/')
            try:
                value = float(num) / float(den or 1)
            except (ValueError, ZeroDivisionError):
                continue
            if 1 <= value <= 240:
                return value
    return None


def video_size(path):
    """(width, height) of the video as shown, i.e. as ffmpeg decodes it: phone videos filmed upright store a
    landscape picture with a 90-degree display rotation, which ffmpeg applies; None when ffprobe cannot read it."""
    size = _probe(path, 'stream=width,height')
    if not size:
        return None
    w, h = (int(v) for v in size[0].split(',')[:2])
    rot = next((float(v) for v in _probe(path, 'stream_side_data=rotation') + _probe(path, 'stream_tags=rotate')
                if v.lstrip('-').replace('.', '', 1).isdigit()), 0.)
    return (h, w) if round(rot) % 180 == 90 else (w, h)


def sample_frames(path, samples=15):
    """Up to `samples` gray frames spread over the video, decoded at keyframes: a seek elsewhere decodes from the
    previous keyframe (43 s with OpenCV on a 4K upload with a keyframe every 12.5 s; ~3 s this way). Streams
    without timestamps (raw .hevc) fall back to every 20th of the first frames."""
    size = video_size(path)
    if size is None:
        return []
    w, h = size
    start = next((float(t) for t in _probe(path, 'format=start_time') if t != 'N/A'), 0.)
    keys = [float(t) for t, flag in (p.split(',')[:2] for p in _probe(path, 'packet=pts_time,flags') if p.count(','))
            if 'K' in flag and t != 'N/A']
    if not keys:
        return _gray(path, w, h, ['-i', str(path), '-frames:v', str(20 * samples)])[::20]
    picks = np.unique(np.linspace(0, len(keys) - 1, samples).astype(int))
    with ThreadPoolExecutor(4) as ex:
        parts = ex.map(lambda t: _gray(path, w, h, ['-ss', f'{t - start:.6f}', '-i', str(path), '-frames:v', '1']),
                       (keys[k] for k in picks))
        return [f for part in parts for f in part]


def detect_content_box(path, samples=15):
    """Bounding box (x, y, w, h) of the real camera picture inside letterbox / pillarbox bars.

    A bar row/column is near-black in the per-pixel temporal median frame, so logos or captions that come
    and go on the bar do not count. Bars are only cropped when they exist on both
    opposite sides with similar size, as an edited (letterboxed) video has; a dark hood or a night sky in a
    real dashcam frame is one-sided and is kept, so the principal point stays in the image centre.
    x and y are even so the half-size U, V planes crop on the same pixels."""
    frames = sample_frames(path, samples)
    if not frames:
        raise ValueError(f'không giải mã được {path} (codec không được hỗ trợ); hãy chuyển sang H.264')
    big_h, big_w = frames[0].shape
    med = np.median(np.stack(frames).astype(np.int16), axis=0)

    def bars(med_line, size):
        bar = med_line < 24
        lead = int(np.argmin(bar)) if not bar.all() else size
        trail = int(np.argmin(bar[::-1])) if not bar.all() else size
        if lead and trail and abs(lead - trail) <= 0.25 * max(lead, trail) + 16 and lead + trail < 0.8 * size:
            return lead, size - trail
        return 0, size

    y0, y1 = bars(np.median(med, axis=1), big_h)
    x0, x1 = bars(np.median(med[y0:y1], axis=0), big_w)
    x0, y0 = x0 + x0 % 2, y0 + y0 % 2
    return x0, y0, (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2


def decode(video, w, h, limit=0, fps=MODEL_HZ, box=None):
    """Yield (y, u, v) uint8 planes of every frame, decoded by ffmpeg without colour conversion.

    `fps` is the true capture rate; it overrides the container's, which is often wrong (raw .hevc has none).
    box = (x, y, w, h) crops the picture (detect_content_box); w, h are the output size: the crop size, or
    smaller to scale the cropped picture down (job.MAX_WIDTH).
    """
    vf = [f'crop={box[2]}:{box[3]}:{box[0]}:{box[1]}'] if box else []
    if box and (w, h) != tuple(box[2:]):
        vf.append(f'scale={w}:{h}:flags=area')
    vf = ['-vf', ','.join(vf)] if vf else []
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-r', str(fps), '-i', str(video), '-an', *vf,
                             '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    n, size = 0, w * h * 3 // 2
    try:
        while not limit or n < limit:
            data = proc.stdout.read(size)
            if len(data) < size:
                break
            flat = np.frombuffer(data, np.uint8)
            yield (flat[:w * h].reshape(h, w), flat[w * h:w * h * 5 // 4].reshape(h // 2, w // 2),
                   flat[w * h * 5 // 4:].reshape(h // 2, w // 2))
            n += 1
    finally:
        proc.kill()
        proc.wait()


def resample_tick(fps, resample='stride'):
    """(tick_dt, vel_scale) of the model clock. 'stride': every n-th frame (tick); 'blend': neighbouring frames
    blended to exact 20 Hz ticks (comma realtime_lead --resample blend)."""
    return (MODEL_DT, 1.0) if resample == 'blend' else tick(fps)[1:]


def model_ticks(frames, fps, tick_dt, blend=False):
    """Yield (i, pts, planes, ticks) for every decoded (y, u, v) frame; ticks = the planes the model is fed on this
    frame, at a constant tick_dt (comma realtime_lead VideoLeadPipeline.frames): none, one, or several."""
    next_tick, prev = 0., None
    for i, cur in enumerate(frames):
        pts, ticks = i / fps, []
        while next_tick <= pts + 1e-6:
            if blend and prev is not None and next_tick < pts - 1e-6:
                wgt = 1 - (pts - next_tick) * fps   # weight of the current frame
                ticks.append(tuple(cv2.addWeighted(a, 1 - wgt, b, wgt, 0) for a, b in zip(prev, cur, strict=True)))
            else:
                ticks.append(cur)
            next_tick += tick_dt
        prev = cur
        yield i, pts, cur, ticks


def wide_mode(cam_k, w, wide='auto'):
    """'warp' or 'dup'; 'auto' (realtime_lead) warps the wide input only for a lens wider than WIDE_HFOV_DEG."""
    if wide != 'auto':
        return wide
    return 'warp' if np.degrees(2 * np.arctan(w / 2 / cam_k[0, 0])) > WIDE_HFOV_DEG else 'dup'


def warp_matrices(cam_k, rpy, w, wide='auto'):
    """(narrow, wide) model-frame pixel -> camera pixel matrices; wide is None when the narrow input is duplicated."""
    narrow = get_warp_matrix(rpy, cam_k, False)
    return narrow, get_warp_matrix(rpy, cam_k, True) if wide_mode(cam_k, w, wide) == 'warp' else None


def coverage(warps, w, h):
    """Fraction of model-frame pixels that sample inside the source image (rest is replicated border)."""
    x, y = np.meshgrid(np.arange(0, MODEL_W, 4.), np.arange(0, MODEL_H, 4.))
    fr = []
    for m in warps:
        if m is None:
            continue
        s = m @ np.stack([x.ravel(), y.ravel(), np.ones(x.size)])
        sx, sy = s[0] / s[2], s[1] / s[2]
        fr.append(np.mean((s[2] > 0) & (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)))
    return float(min(fr))


def frame_to_model_input(y, u, v, m):
    """Warp yuv420p planes into the model's (6, 128, 256) uint8 YUV tensor."""
    flags = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
    y_w = cv2.warpPerspective(y, m, (MODEL_W, MODEL_H), flags=flags)
    m_uv = np.diag([.5, .5, 1.]) @ m @ np.diag([2., 2., 1.])
    u_w = cv2.warpPerspective(u, m_uv, (MODEL_W // 2, MODEL_H // 2), flags=flags)
    v_w = cv2.warpPerspective(v, m_uv, (MODEL_W // 2, MODEL_H // 2), flags=flags)
    return np.stack([y_w[0::2, 0::2], y_w[1::2, 0::2], y_w[0::2, 1::2], y_w[1::2, 1::2], u_w, v_w])


def pack_frame(y, u, v, warps):
    """(narrow, wide) model inputs for one frame; warps from warp_matrices."""
    narrow = frame_to_model_input(y, u, v, warps[0])
    return np.stack([narrow, narrow if warps[1] is None else frame_to_model_input(y, u, v, warps[1])])


class _SliceUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) == ('builtins', 'slice'):
            return slice
        raise ValueError(f'unexpected class in model metadata: {module}.{name}')


class Gr14VinAI:
    def __init__(self, path=None, threads=4):
        path = path or PRUNED_PATH
        if not Path(path).exists():
            raise FileNotFoundError(f'{path} missing: run scripts/roadwatch/download_model.py')
        opts = ort.SessionOptions()
        opts.intra_op_num_threads, opts.inter_op_num_threads = threads, 1
        self.sess = ort.InferenceSession(str(path), opts, providers=['CPUExecutionProvider'])
        meta = self.sess.get_modelmeta().custom_metadata_map['output_slices']
        self.slices = _SliceUnpickler(io.BytesIO(base64.b64decode(meta))).load()
        self.names = [o.name for o in self.sess.get_outputs()]
        self.parser = Parser(ignore_missing=True)   # a pruned model has only the heads BT-A reads
        self.reset()

    def reset(self):
        """Zero the temporal state queues (new clip or new warp sweep)."""
        self.inputs = {x.name: np.zeros(x.shape, np.uint8 if x.type == 'tensor(uint8)' else np.float32)
                       for x in self.sess.get_inputs()}
        if 'traffic_convention' in self.inputs:   # policy-only inputs, absent from the pruned model
            self.inputs['traffic_convention'][0] = [1, 0]   # right-hand traffic
        if 'action_t' in self.inputs:
            self.inputs['action_t'][0] = [.075, .375]       # modeld delays, vehicle actuator delay assumed 0

    def step(self, new_img):
        self.inputs['new_img'] = new_img
        out = dict(zip(self.names, self.sess.run(None, self.inputs)))
        for k in list(self.inputs):
            if 'next_' + k in out:
                self.inputs[k] = out['next_' + k]
        return self.parser.parse_outputs({k: out['outputs'][:, s].copy() for k, s in self.slices.items()})
