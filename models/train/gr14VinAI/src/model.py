"""Trainable reconstruction of the actual 707-output ONNX graph, not a guessed network."""
import copy
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np
import onnx
import torch
import torch.nn.functional as functional
from onnx import numpy_helper
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent / 'P-014/models/gr14VinAI.onnx'
SLICES = {'pose': (0, 12), 'road_transform': (12, 24), 'lane_lines': (24, 552),
          'lane_lines_prob': (552, 560), 'lead': (560, 704), 'lead_prob': (704, 707)}
SUPPORTED = {'Conv', 'Gemm', 'Relu', 'Add', 'Gelu', 'Mul', 'Slice', 'Concat', 'Reshape', 'Cast',
             'Gather', 'Div', 'ReduceMean', 'Unsqueeze', 'Sub', 'Sigmoid', 'ReduceL2', 'Clip', 'Expand'}


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Gr14VinAI(nn.Module):
    """Same nodes, wiring, parameters and public shapes as REFERENCE; FP32 autograd internally.

    The source uses FP16 parameters/casts. Reconstruction promotes them to FP32 for stable training;
    export restores each initializer's original dtype and leaves the source graph topology intact.
    """
    def __init__(self, source: Path = REFERENCE) -> None:
        super().__init__()
        self.source = Path(source)
        self.source_sha256 = sha256(self.source)
        self.graph_model = onnx.load(str(self.source))
        onnx.checker.check_model(self.graph_model)
        graph = self.graph_model.graph
        self.inputs = {i.name: ([d.dim_value for d in i.type.tensor_type.shape.dim], i.type.tensor_type.elem_type)
                       for i in graph.input}
        outputs = {o.name: ([d.dim_value for d in o.type.tensor_type.shape.dim], o.type.tensor_type.elem_type)
                   for o in graph.output}
        if self.inputs != {'new_img': ([2, 6, 128, 256], 2), 'state_img_q': ([2, 5, 6, 128, 256], 2)} or outputs != {
            'outputs': ([1, 707], 1), 'next_state_img_q': ([2, 5, 6, 128, 256], 2)
        }:
            raise ValueError(f'{source}: not the expected 707-output/state-queue model')
        unknown = set(n.op_type for n in graph.node) - SUPPORTED
        if unknown:
            raise ValueError(f'unsupported ONNX operators: {sorted(unknown)}')
        trainable = {name for n in graph.node if n.op_type in {'Conv', 'Gemm'} for name in n.input[1:]}
        self.weights = nn.ParameterDict()
        self.tensor_names = {}
        for index, item in enumerate(graph.initializer):
            key = f'tensor_{index}'
            tensor = torch.from_numpy(numpy_helper.to_array(item).copy())
            if tensor.is_floating_point():
                tensor = tensor.float()
            if item.name in trainable:
                self.weights[key] = nn.Parameter(tensor)
                self.tensor_names[item.name] = ('weight', key)
            else:
                self.register_buffer(key, tensor)
                self.tensor_names[item.name] = ('buffer', key)
        self.nodes = [(node.op_type, list(node.input), list(node.output),
                       {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}) for node in graph.node]

    def forward(self, new_img: torch.Tensor, state_img_q: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if new_img.shape != (2, 6, 128, 256) or state_img_q.shape != (2, 5, 6, 128, 256):
            raise ValueError('expected new_img [2,6,128,256], state_img_q [2,5,6,128,256]')
        if new_img.dtype != torch.uint8 or state_img_q.dtype != torch.uint8:
            raise ValueError('both inputs must be uint8 packed YUV planes')
        env = {'new_img': new_img, 'state_img_q': state_img_q}
        for name, (kind, key) in self.tensor_names.items():
            env[name] = self.weights[key] if kind == 'weight' else getattr(self, key)
        for op, inputs, outputs, attrs in self.nodes:
            if len(outputs) != 1:
                raise ValueError(f'{op}: expected one output')
            env[outputs[0]] = self._op(op, [env[name] if name else None for name in inputs], attrs)
        return env['outputs'], env['next_state_img_q']

    def _op(self, op: str, x: list[torch.Tensor], a: dict) -> torch.Tensor:
        if op == 'Conv':
            pads = a.get('pads', [0, 0, 0, 0])
            if a.get('auto_pad', b'NOTSET') != b'NOTSET':
                raise ValueError('automatic Conv padding not supported')
            image = functional.pad(x[0], (pads[1], pads[3], pads[0], pads[2]))
            return functional.conv2d(image, x[1], x[2] if len(x) > 2 else None,
                            stride=a.get('strides', [1, 1]), dilation=a.get('dilations', [1, 1]), groups=a.get('group', 1))
        if op == 'Gemm':
            left = x[0].T if a.get('transA', 0) else x[0]
            right = x[1].T if a.get('transB', 0) else x[1]
            out = a.get('alpha', 1) * (left @ right)
            return out + a.get('beta', 1) * x[2] if len(x) > 2 else out
        if op == 'Add':
            return x[0] + x[1]
        if op == 'Sub':
            return x[0] - x[1]
        if op == 'Mul':
            return x[0] * x[1]
        if op == 'Div':
            return x[0] / x[1]
        if op == 'Relu':
            return functional.relu(x[0])
        if op == 'Gelu':
            return functional.gelu(x[0], approximate=a.get('approximate', b'none').decode())
        if op == 'Sigmoid':
            return torch.sigmoid(x[0])
        if op == 'Cast':
            # FP16 casts become FP32 during training. Export keeps the original ONNX Cast nodes.
            dtype = {1: torch.float32, 10: next(self.parameters()).dtype, 2: torch.uint8, 7: torch.int64}[a['to']]
            return x[0].to(dtype)
        if op == 'Concat':
            return torch.cat(x, dim=a.get('axis', 0))
        if op == 'Reshape':
            shape = x[1].tolist()
            if not a.get('allowzero', 0):
                shape = [x[0].shape[i] if size == 0 else size for i, size in enumerate(shape)]
            return x[0].reshape(shape)
        if op == 'Slice':
            slices = [slice(None)] * x[0].ndim
            axes = x[3].tolist() if len(x) > 3 else range(len(x[1]))
            steps = x[4].tolist() if len(x) > 4 else [1] * len(x[1])
            for start, stop, axis, step in zip(x[1].tolist(), x[2].tolist(), axes, steps):
                slices[axis] = slice(start, stop, step)
            return x[0][tuple(slices)]
        if op == 'Gather':
            axis = a.get('axis', 0) % x[0].ndim
            idx = x[1].long()
            idx = torch.where(idx < 0, idx + x[0].shape[axis], idx)
            selected = torch.index_select(x[0], axis, idx.flatten())
            return selected.reshape(*x[0].shape[:axis], *idx.shape, *x[0].shape[axis + 1:])
        if op == 'Unsqueeze':
            out = x[0]
            rank = out.ndim + x[1].numel()
            for axis in sorted(axis % rank for axis in x[1].tolist()):
                out = out.unsqueeze(axis)
            return out
        if op in {'ReduceMean', 'ReduceL2'}:
            axes = tuple(x[1].tolist()) if len(x) > 1 else tuple(a.get('axes', range(x[0].ndim)))
            if not axes:
                if a.get('noop_with_empty_axes', 0):
                    return x[0]
                axes = tuple(range(x[0].ndim))
            keep = bool(a.get('keepdims', 1))
            return x[0].mean(axes, keepdim=keep) if op == 'ReduceMean' else torch.linalg.vector_norm(x[0], dim=axes, keepdim=keep)
        if op == 'Clip':
            minimum = x[1].item() if len(x) > 1 and x[1] is not None else None
            maximum = x[2].item() if len(x) > 2 and x[2] is not None else None
            return torch.clamp(x[0], min=minimum, max=maximum)
        if op == 'Expand':
            return x[0].expand(x[1].tolist())
        raise ValueError(f'unsupported operator: {op}')

    def export(self, path: Path, checkpoint_sha256: str | None = None) -> None:
        if Path(path).resolve() == self.source.resolve():
            raise ValueError('refusing to overwrite the reference model')
        graph_model = copy.deepcopy(self.graph_model)
        for index, original in enumerate(self.graph_model.graph.initializer):
            kind, key = self.tensor_names[original.name]
            if kind == 'weight':
                dtype = numpy_helper.to_array(original).dtype
                value = self.weights[key].detach().cpu().numpy().astype(dtype)
                if not np.isfinite(value).all():
                    raise ValueError(f'{original.name}: weights overflow the export dtype {dtype}')
                graph_model.graph.initializer[index].CopyFrom(numpy_helper.from_array(value, original.name))
        if checkpoint_sha256:
            meta = {p.key: p.value for p in graph_model.metadata_props}
            meta.update(model_checkpoint=checkpoint_sha256, reconstruction_source_sha256=self.source_sha256,
                        training_method='fine-tune reconstructed ONNX graph; original training recipe unknown')
            onnx.helper.set_model_props(graph_model, meta)
        onnx.checker.check_model(graph_model)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        onnx.save(graph_model, str(path))

    def float32_onnx(self) -> bytes:
        """The same graph with FP16 weights, value types and casts promoted for an autograd oracle."""
        model = copy.deepcopy(self.graph_model)
        for item in model.graph.initializer:
            if item.data_type == onnx.TensorProto.FLOAT16:
                item.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(item).astype(np.float32), item.name))
        for value in [*model.graph.input, *model.graph.output, *model.graph.value_info]:
            if value.type.tensor_type.elem_type == onnx.TensorProto.FLOAT16:
                value.type.tensor_type.elem_type = onnx.TensorProto.FLOAT
        for node in model.graph.node:
            if node.op_type == 'Cast':
                for attr in node.attribute:
                    if attr.name == 'to' and attr.i == onnx.TensorProto.FLOAT16:
                        attr.i = onnx.TensorProto.FLOAT
        onnx.checker.check_model(model)
        return model.SerializeToString()

    def describe(self) -> dict:
        return dict(source=str(self.source.resolve()), source_sha256=self.source_sha256,
                    origin='reconstructed from existing ONNX, not recovered training history',
                    operators=dict(Counter(n[0] for n in self.nodes)), inputs=self.inputs,
                    outputs={'outputs': [1, 707], 'next_state_img_q': [2, 5, 6, 128, 256]},
                    output_slices=SLICES, trainable_parameters=sum(p.numel() for p in self.parameters()),
                    internal_precision='float32; ONNX export retains original initializer dtypes')
