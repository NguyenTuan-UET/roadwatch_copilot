"""Prune supercombo to the heads BT-A uses; write models/gr14VinAI.onnx.

Kept: lead, lead_prob, lane_lines, lane_lines_prob, pose, road_transform (+ whatever state queues the
vision trunk still needs). Dropped: the policy branch (plan, desire_state) and the vision heads meta,
desire_pred, road_edges, wide_from_device_euler. Dead nodes, initializers and inputs are removed.
Called by download_model.py; the full model is a temporary file there and is deleted afterwards.
Needs `onnx` (offline tool, not a runtime dep).
"""
import base64
import io
import pickle
import sys
from pathlib import Path

import onnx
from onnx import helper, shape_inference

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.roadwatch.model import MODEL_SHA256, PRUNED_PATH, _SliceUnpickler  # noqa: E402

KEEP = ['pose', 'road_transform', 'lane_lines', 'lane_lines_prob', 'lead', 'lead_prob']
MODEL_PATH = PRUNED_PATH.with_name('driving_supercombo.onnx')   # temporary, download_model.py deletes it
OUT_PATH = PRUNED_PATH


def head_sources(graph):
    """Map each vision head slice (start, stop) of `outputs` to the tensor that produces it."""
    shp = {v.name: [d.dim_value for d in v.type.tensor_type.shape.dim] for v in graph.value_info}
    prod = {o: n for n in graph.node for o in n.output}
    n = prod[prod[prod['outputs'].input[0]].input[0]]          # Cast <- Concat(vision, policy)
    n = prod[n.input[0]]                                       # vision part
    while n.op_type != 'Concat':
        n = prod[n.input[0]]
    src, off = {}, 0
    for t in n.input:
        src[(off, off + shp[t][-1])] = t
        off += shp[t][-1]
    return src


def prune():
    if not MODEL_PATH.exists():
        sys.exit(f'{MODEL_PATH} missing: run scripts/roadwatch/download_model.py')
    m = shape_inference.infer_shapes(onnx.load(str(MODEL_PATH)))
    meta = {p.key: p.value for p in m.metadata_props}
    slices = _SliceUnpickler(io.BytesIO(base64.b64decode(meta['output_slices']))).load()
    src = head_sources(m.graph)
    tensors, new_slices, off = [], {}, 0
    for k in KEEP:
        s = slices[k]
        tensors.append(src[(s.start, s.stop)])
        new_slices[k] = slice(off, off + s.stop - s.start)
        off += s.stop - s.start
    g = m.graph
    g.node.append(helper.make_node('Concat', tensors, ['bta_concat'], axis=1))
    g.node.append(helper.make_node('Cast', ['bta_concat'], ['bta_outputs'], to=onnx.TensorProto.FLOAT))
    g.value_info.append(helper.make_tensor_value_info('bta_outputs', onnx.TensorProto.FLOAT, [1, off]))
    names = [i.name for i in g.input]
    outs = ['bta_outputs']
    while True:   # keep each state queue's update while its input is still read
        used = {i for n in onnx.utils.Extractor(m).extract_model(names, outs).graph.node for i in n.input}
        more = [o.name for o in g.output if o.name.startswith('next_') and o.name[5:] in used and o.name not in outs]
        if not more:
            break
        outs += more
    need = [i for i in names if i in used]   # inputs only the policy branch read are dropped
    sub = onnx.utils.Extractor(m).extract_model(need, outs)
    sub.graph.output[0].name = 'outputs'
    for n in sub.graph.node:
        n.output[:] = ['outputs' if o == 'bta_outputs' else o for o in n.output]
    del sub.metadata_props[:]
    for k, v in meta.items():
        sub.metadata_props.add(key=k, value=v)
    sub.metadata_props[[p.key for p in sub.metadata_props].index('output_slices')].value = \
        base64.b64encode(pickle.dumps(new_slices)).decode()
    sub.metadata_props.add(key='pruned_from_sha256', value=MODEL_SHA256)
    onnx.checker.check_model(sub)
    onnx.save(sub, str(OUT_PATH))
    print(f'{OUT_PATH.name}: inputs {need}; outputs {[o.name for o in sub.graph.output]}; '
          f'{OUT_PATH.stat().st_size / 1e6:.1f} MB (full {MODEL_PATH.stat().st_size / 1e6:.1f} MB)')

