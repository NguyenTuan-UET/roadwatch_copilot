"""Evaluate the reference model on the test videos: openpilot's supercombo driving model (comma.ai), run unmodified
from the file `driving_supercombo (1).onnx` in the project root. It is not this project's model; it is the yardstick.

    python src/baseline_eval.py                 # every test video
    python src/baseline_eval.py scb4 scb14      # only these

Writes results/baseline/preds_<scb>.csv (one row per video frame) and prints metrics on the labelled frames.

How it is fed, and what is assumed (none of this comes with the file, so read the numbers with that in mind):
  - it wants two cameras, a narrow and a wide one. The dataset has one camera, so the wide view is cut from the same
    frames at half the focal length, as openpilot's wide model frame is defined (focal 455 px, centre row 151.8);
  - it keeps its own memory of earlier frames (the state_* inputs), fed back from its outputs frame after frame;
  - desire = none, left-hand-drive traffic, action_t = 0;
  - its answer is read with the output layout stored inside the file ("output_slices"): lead = 3 x 6 x 4 means then
    as many spreads; the first row, first time step is the lead now: metres ahead of the camera, metres sideways.
    A lead counts as reported when lead_prob > 0.5, openpilot's own rule, and it is within the dataset's 100 m.
"""
import base64
import io
import pickle
import sys

import numpy as np

from common import FOCAL, RADAR_TO_CAMERA, RAW, ROOT, labelled, onnx_session, print_metrics, read_yuv_frames, vanishing_point

MODEL = ROOT / "driving_supercombo (1).onnx"
OUT = ROOT / "results" / "baseline"
WIDE_ROW = 151.8  # where the vanishing point sits in the wide model frame
ROAD_FIRST = True  # which of the two image slots is the narrow camera; checked against radar on a training video


class OnlySlices(pickle.Unpickler):  # the layout is a pickled dict of slices; nothing else may be loaded from the file
    def find_class(self, module, name):
        if (module, name) == ("builtins", "slice"):
            return slice
        raise pickle.UnpicklingError(f"refusing {module}.{name}")


def session():
    if not MODEL.exists():
        sys.exit(f"{MODEL} not found")
    sess = onnx_session(MODEL)
    layout = OnlySlices(io.BytesIO(base64.b64decode(sess.get_modelmeta().custom_metadata_map["output_slices"]))).load()
    return sess, layout


def run_model(sess, layout, scb, road_first=ROAD_FIRST):
    """Yield (frame, lead probability now, metres ahead as the radar counts them, metres to the side) for every frame."""
    vp = vanishing_point(RAW / scb)
    video = RAW / scb / "video.hevc"
    wide = read_yuv_frames(video, (vp[0], vp[1] - 2 * (WIDE_ROW - 47.6)), focal=2 * FOCAL)  # the same camera, half the focal length
    inputs = {i.name: np.zeros(i.shape, {"tensor(float)": np.float32, "tensor(float16)": np.float16, "tensor(uint8)": np.uint8}[i.type])
              for i in sess.get_inputs()}
    inputs["traffic_convention"][0, 0] = 1
    names = [o.name for o in sess.get_outputs()]
    for n, (road, big) in enumerate(zip(read_yuv_frames(video, vp), wide)):
        inputs["new_img"] = np.stack([road, big] if road_first else [big, road]).astype(inputs["new_img"].dtype)
        result = dict(zip(names, sess.run(None, inputs)))
        for name in names[1:]:  # next_state_x -> state_x
            inputs[name[5:]] = result[name]
        out = result["outputs"][0].astype(np.float32)
        lead = out[layout["lead"]]
        now = lead[:len(lead) // 2].reshape(3, 6, 4)[0, 0]
        yield n, 1 / (1 + np.exp(-out[layout["lead_prob"]][0])), now[0] - RADAR_TO_CAMERA, now[1]


def main():
    sess, layout = session()
    rows = [r for r in labelled("test") if not sys.argv[1:] or r["scb_id"] in sys.argv[1:]]
    OUT.mkdir(parents=True, exist_ok=True)
    preds = {}
    for scb in dict.fromkeys(r["scb_id"] for r in rows):
        frames = list(run_model(sess, layout, scb))
        np.savetxt(OUT / f"preds_{scb}.csv", frames, "%.4f", ",", header="frame_index,lead_prob,lead_d_m,lead_y_m", comments="")
        preds[scb] = np.array(frames)
        print(f"{scb}: {len(frames)} frames", flush=True)
    has = np.array([r["has_target"] == "1" for r in rows])
    dist = np.array([float(r["distance_m"]) if h else 0 for r, h in zip(rows, has)])
    p = np.array([preds[r["scb_id"]][int(r["frame_index"])] for r in rows])
    prob = np.where(p[:, 2] <= 100, p[:, 1], 0)  # a lead beyond the dataset's 100 m is not a target by the dataset's rule
    print("\nreference model on the test split")
    print_metrics(has, dist, prob, np.clip(p[:, 2], 0, 100), 0.5)


if __name__ == "__main__":
    main()
