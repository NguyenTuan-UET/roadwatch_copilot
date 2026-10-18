"""The phone's copies of gr14VinAI (/phone, running in the phone's browser), made from the laptop model.

    python -m scripts.roadwatch.make_phone_models [--src models/gr14VinAI.onnx]

Writes, next to the source (models/, not committed):
- gr14VinAI.mixed.onnx: the source with each ReduceL2 (L2 norm) computed in float32. In float16 its sum of squares
  (~81 thousand) overflows on the iPhone's GPU and the lanes and the lead come out wrong (/bench, 13/10/2026). Two
  nodes of the policy branch that JSEP 1.20.1 leaves on the CPU (so no graph capture) are rewritten as nodes it runs,
  with the same result: a ReduceMax over a short axis given as an input -> Slices, Greater + Where, Squeeze, a GatherND of
  constant consecutive rows -> Slice; and a Concat of many inputs, over WebGPU's 8 storage buffers per shader (the frame
  then comes out as zeros), -> a tree of smaller Concats (jsep_friendly).
- gr14VinAI.capture.onnx: mixed with the image inputs and the 5-frame queue (new_img, state_img_q, next_state_img_q)
  in float16 and the uint8 -> float16 Casts of the queue as Identity (0..255 are exact in float16). onnxruntime-web's
  JSEP runs no uint8 op on the GPU: they would fall back to the CPU every frame and enableGraphCapture refuses the
  session. The only way the model ran 12000 times in Safari without the tab being closed (iPhone 13, 14/10/2026; docs/WORKLOG.md).
- gr14VinAI.fp32.onnx: the source in float32 (and jsep_friendly), for the phone's CPU (WebAssembly).
Each one is checked against the source on ONNX Runtime CPU: capture equals mixed exactly; mixed and fp32 are close.
"""
import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

MODELS = Path(__file__).resolve().parents[2] / 'models'
F16, F32, U8 = TensorProto.FLOAT16, TensorProto.FLOAT, TensorProto.UINT8
QUEUE = ('new_img', 'state_img_q', 'next_state_img_q')


def mixed(model):
    """Each ReduceL2 between a Cast to float32 and a Cast back to float16."""
    g, out, n = model.graph, [], 0
    for node in g.node:
        if node.op_type == 'ReduceL2':
            x, y, name = node.input[0], node.output[0], node.name or f'reduce_l2_{n}'
            out.append(helper.make_node('Cast', [x], [x + '_fp32'], name=name + '_to_fp32', to=F32))
            node.input[0], node.output[0] = x + '_fp32', y + '_fp32'
            out += [node, helper.make_node('Cast', [y + '_fp32'], [y], name=name + '_to_fp16', to=F16)]
            n += 1
        else:
            out.append(node)
    if not n:
        raise SystemExit('no ReduceL2 in the source model')
    del g.node[:]
    g.node.extend(out)
    for v in list(g.value_info):   # the norms' own types changed: let shape inference redo them
        if v.name in {o for node in out if node.op_type == 'ReduceL2' for o in node.output}:
            g.value_info.remove(v)
    return model


CONCAT_MAX = 6   # inputs per Concat on the GPU (jsep_friendly)


def jsep_friendly(model):
    """ReduceMax with its axis as an input (opset 18) -> the largest of the slices along it (Greater + Where); GatherND of constant consecutive
    rows of the first axis -> Slice. Both are left on the CPU by onnxruntime-web 1.20.1's JSEP (14/10/2026). A Concat of
    more than CONCAT_MAX inputs -> a tree of Concats: JSEP binds each input as a storage buffer, over WebGPU's limit."""
    g = model.graph
    shapes = {v.name: [d.dim_value for d in v.type.tensor_type.shape.dim]
              for v in onnx.shape_inference.infer_shapes(model).graph.value_info}
    init = {t.name: numpy_helper.to_array(t) for t in g.initializer}
    const = lambda name, v: g.initializer.append(numpy_helper.from_array(np.array(v, np.int64), name))  # noqa: E731
    out, done = [], 0
    for node in g.node:
        attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
        if node.op_type == 'ReduceMax' and len(node.input) == 2 and node.input[1] in init:
            (axis,), x = init[node.input[1]].tolist(), node.input[0]
            n, name = shapes[x][axis], node.name or node.output[0]
            parts = []
            for k in range(n):
                for suffix, v in (('s', [k]), ('e', [k + 1]), ('a', [axis])):
                    const(f'{name}_{suffix}{k}', v)
                parts.append(f'{name}_part{k}')
                out.append(helper.make_node('Slice', [x, f'{name}_s{k}', f'{name}_e{k}', f'{name}_a{k}'], [parts[-1]],
                                            name=f'{name}_slice{k}'))
            keep = attrs.get('keepdims', 1)
            last = node.output[0] if keep else name + '_max'

            def bigger(a, b, out_name):   # max(a, b) exactly; JSEP 1.20.1 has no Max (14/10/2026), it has Greater and Where
                out.append(helper.make_node('Greater', [a, b], [out_name + '_gt'], name=out_name + '_gt'))
                out.append(helper.make_node('Where', [out_name + '_gt', a, b], [out_name], name=out_name))
            acc = parts[0]
            for k, part in enumerate(parts[1:], 1):
                acc_next = last if k == len(parts) - 1 else f'{name}_max{k}'
                bigger(acc, part, acc_next)
                acc = acc_next
            if not keep:
                out.append(helper.make_node('Squeeze', [name + '_max', node.input[1]], [node.output[0]], name=name + '_squeeze'))
            done += 1
        elif node.op_type == 'GatherND' and node.input[1] in init and not attrs.get('batch_dims', 0):
            idx, name = init[node.input[1]], node.name
            rows = idx[:, 0].tolist() if idx.ndim == 2 and idx.shape[1] == 1 else None
            if rows is None or rows != list(range(rows[0], rows[0] + len(rows))) or not (rows[0] < 0 <= rows[-1] + 1 or rows[0] >= 0):
                raise SystemExit(f'{name}: GatherND indices are not consecutive rows')
            # last rows (..., -1): end at the axis length, not INT64_MAX, which JSEP may narrow to int32
            end = rows[-1] + 1 if rows[-1] != -1 else shapes[node.input[0]][0]
            const(name + '_s', [rows[0]]), const(name + '_e', [end]), const(name + '_a', [0])
            out.append(helper.make_node('Slice', [node.input[0], name + '_s', name + '_e', name + '_a'], list(node.output), name=name))
            done += 1
        elif node.op_type == 'Concat' and len(node.input) > CONCAT_MAX:
            # each input is a storage buffer of the shader; WebGPU allows 8 per stage by default (with the output): a
            # Concat of more fails to build and the whole frame comes out as zeros (iPhone, 14/10/2026)
            ins, k = list(node.input), 0
            while len(ins) > CONCAT_MAX:
                groups, ins = [ins[i:i + CONCAT_MAX] for i in range(0, len(ins), CONCAT_MAX)], []
                for grp in groups:
                    if len(grp) == 1:
                        ins.append(grp[0])
                        continue
                    k += 1
                    ins.append(f'{node.name or node.output[0]}_part{k}')
                    out.append(helper.make_node('Concat', grp, [ins[-1]], name=ins[-1], axis=attrs['axis']))
            out.append(helper.make_node('Concat', ins, list(node.output), name=node.name, axis=attrs['axis']))
            done += 1
        else:
            out.append(node)
    del g.node[:]
    g.node.extend(out)
    used = {i for node in g.node for i in node.input}
    for t in [t for t in g.initializer if t.name not in used]:   # GatherND's indices
        g.initializer.remove(t)
    print(f'jsep_friendly: {done} nodes rewritten')
    return model


def capture(model):
    """The frame queue in float16 (see the module docstring)."""
    g = model.graph
    for v in [*g.input, *g.output]:
        if v.name in QUEUE:
            v.type.tensor_type.elem_type = F16
    typed = onnx.shape_inference.infer_shapes(model)   # the uint8 tensors, before their types are dropped
    uint8 = {v.name for v in typed.graph.value_info if v.type.tensor_type.elem_type == U8}
    for v in list(g.value_info):
        if v.name in uint8:
            g.value_info.remove(v)
    casts = 0
    for i, node in enumerate(g.node):
        to = next((a.i for a in node.attribute if a.name == 'to'), None)
        if node.op_type == 'Cast' and to == F16 and node.input[0] in uint8:
            g.node[i].CopyFrom(helper.make_node('Identity', list(node.input), list(node.output), name=node.name))
            casts += 1
    if not casts:
        raise SystemExit('no uint8 -> float16 Cast of the frame queue found')
    return model


def fp32(model):
    """Every float16 tensor, constant, Cast and type in float32."""
    g = model.graph
    for t in g.initializer:
        if t.data_type == F16:
            t.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(t).astype(np.float32), t.name))
    for node in g.node:
        for a in node.attribute:
            if a.name == 'to' and a.i == F16:
                a.i = F32
            if a.type == onnx.AttributeProto.TENSOR and a.t.data_type == F16:
                a.t.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(a.t).astype(np.float32), a.t.name))
    for v in [*g.input, *g.output, *g.value_info]:
        if v.type.tensor_type.elem_type == F16:
            v.type.tensor_type.elem_type = F32
    return model


def feeds(session, rng, half=False):
    """Random frames and states; desire 0 and traffic_convention [1, 0] (right-hand traffic) as model.Gr14VinAI."""
    out = {}
    for x in session.get_inputs():
        if x.type == 'tensor(uint8)' or x.name in QUEUE:
            v = rng.integers(0, 256, x.shape, dtype=np.uint8)
            out[x.name] = v.astype(np.float16) if half else v
        else:
            out[x.name] = np.zeros(x.shape, np.float32)
    if 'traffic_convention' in out:
        out['traffic_convention'][0] = [1, 0]
    for k in ('state_feat_q', 'state_desire_q'):   # running states, not zeros (they go through jsep_friendly's nodes)
        if k in out:
            out[k] = rng.normal(0, 1, out[k].shape).astype(np.float32)
    return out


def check(src, paths):
    import onnxruntime as ort
    sessions = {k: ort.InferenceSession(str(p)) for k, p in [('source', src), *paths.items()]}
    names = [o.name for o in sessions['source'].get_outputs()]
    got = {}
    for k, s in sessions.items():
        f = feeds(s, np.random.default_rng(0), half=k == 'capture')
        got[k] = dict(zip(names, s.run(names, f)))
    diff = lambda a, b, n: float(np.abs(got[a][n].astype(np.float32) - got[b][n].astype(np.float32)).max())  # noqa: E731
    for n in names:
        print(f'{n}: capture-mixed {diff("capture", "mixed", n)}, mixed-source {diff("mixed", "source", n):.3g}, '
              f'fp32-source {diff("fp32", "source", n):.3g}')
        if diff('capture', 'mixed', n):
            raise SystemExit(f'{n}: capture differs from mixed')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--src', type=Path, default=MODELS / 'gr14VinAI.onnx')
    args = ap.parse_args()
    out = {k: args.src.with_name(f'{args.src.stem}.{k}.onnx') for k in ('mixed', 'capture', 'fp32')}
    m = jsep_friendly(mixed(onnx.load(args.src)))
    onnx.checker.check_model(m)
    onnx.save(m, out['mixed'])
    c = capture(onnx.load(out['mixed']))
    onnx.checker.check_model(c)
    onnx.save(c, out['capture'])
    f = jsep_friendly(fp32(onnx.load(args.src)))   # same rewrite: the CPU build runs it too, and a GPU without f16 can
    onnx.checker.check_model(f)
    onnx.save(f, out['fp32'])
    check(args.src, out)
    for p in out.values():
        print(p, f'{p.stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
