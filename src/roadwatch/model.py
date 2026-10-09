"""gr14VinAI inference on CPU: video decode, warp into the model frame, YUV packing, state queues.

The warp and packing reproduce openpilot's tinygrad warp (compile_warp.py: warp_perspective_tinygrad,
frames_to_tensor) at the pinned commit: nearest sampling with half-to-even rounding, clipped borders,
channels Y[0::2,0::2], Y[1::2,0::2], Y[0::2,1::2], Y[1::2,1::2], U, V.
"""
import base64
import io
import pickle
import subprocess
from pathlib import Path

import numpy as np
import onnxruntime as ort
from g01T014VinAI.common.transformations.model import get_warp_matrix
from g01T014VinAI.selfdrive.modeld.parse_model_outputs import Parser

PRUNED_PATH = Path(__file__).resolve().parents[2] / 'models/gr14VinAI.onnx'  # the only model used; not committed
MODEL_HZ = 20   # gr14VinAI's training frame rate (openpilot ModelConstants)
MODEL_SHA256 = '65a08adc31d5c456219687d99b7bf5e44d61dae2d49ea67850e76105c7248cce'


def decode(video, w, h, limit=0, fps=MODEL_HZ):
    """Yield (y, u, v) uint8 planes resampled to MODEL_HZ, decoded by ffmpeg without colour conversion.

    `fps` is the true capture rate; it overrides the container's, which is often wrong (raw .hevc has none).
    gr14VinAI infers motion from consecutive frames, so it must see exactly MODEL_HZ frames per second.
    """
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-r', str(fps), '-i', str(video), '-an', '-vf', f'fps={MODEL_HZ}',
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


def sampling_indices(matrix, width, height, src_w, src_h):
    """Source (row, col) for every output pixel; matrix maps output pixels to source pixels."""
    x, y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    sx = matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2]
    sy = matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2]
    sw = matrix[2, 0] * x + matrix[2, 1] * y + matrix[2, 2]
    return (np.clip(np.rint(sy / sw), 0, src_h - 1).astype(int),
            np.clip(np.rint(sx / sw), 0, src_w - 1).astype(int))


def warp_maps(cam_k, rpy, w, h):
    """Index maps for the main (MEDMODEL) and extra (SBIGMODEL) inputs; one camera feeds both."""
    uv = np.array([[1, 1, .5], [1, 1, .5], [2, 2, 1]], np.float32)
    maps = []
    for big in (False, True):
        m = get_warp_matrix(rpy, cam_k, big).astype(np.float32)
        maps.append((sampling_indices(m, 512, 256, w, h), sampling_indices(m * uv, 256, 128, w // 2, h // 2)))
    return maps


def coverage(maps, w, h):
    """Fraction of model-frame pixels that sample inside the source image (rest is replicated border)."""
    fr = []
    for (ry, rx), _ in maps:
        fr.append(np.mean((ry > 0) & (ry < h - 1) & (rx > 0) & (rx < w - 1)))
    return float(min(fr))


def pack_frame(y, u, v, maps):
    imgs = []
    for ym, uvm in maps:
        wy = y[ym]
        imgs.append(np.stack([wy[0::2, 0::2], wy[1::2, 0::2], wy[0::2, 1::2], wy[1::2, 1::2], u[uvm], v[uvm]]))
    return np.stack(imgs)


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
