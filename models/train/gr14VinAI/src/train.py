"""Reconstruct, verify, fine-tune and export the 707-output graph. No historical training claims."""
import argparse
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
import torch.nn.functional as functional

from model import REFERENCE, Gr14VinAI, sha256


def load_data(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        required = {'new_img', 'state_img_q', 'targets', 'target_mask'}
        if set(archive.files) != required:
            raise ValueError(f'{path}: expected arrays {sorted(required)}')
        data = {name: archive[name].copy() for name in required}
    count = len(data['new_img'])
    shapes = {'new_img': (count, 2, 6, 128, 256), 'state_img_q': (count, 2, 5, 6, 128, 256),
              'targets': (count, 707), 'target_mask': (count, 707)}
    if count == 0:
        raise ValueError(f'{path}: dataset is empty')
    for name, shape in shapes.items():
        if data[name].shape != shape:
            raise ValueError(f'{path}: {name} shape must be {shape}, got {data[name].shape}')
    if data['new_img'].dtype != np.uint8 or data['state_img_q'].dtype != np.uint8:
        raise ValueError(f'{path}: packed image and state arrays must be uint8')
    mask = data['target_mask']
    if mask.dtype != np.bool_ or not mask.any(axis=1).all():
        raise ValueError(f'{path}: target_mask must be bool with at least one labelled output per example')
    if not np.issubdtype(data['targets'].dtype, np.floating) or not np.isfinite(data['targets'][mask]).all():
        raise ValueError(f'{path}: supervised targets must be finite floating-point values')
    return data


def sample_loss(model: Gr14VinAI, data: dict, index: int, device: str) -> torch.Tensor:
    output, _ = model(torch.from_numpy(data['new_img'][index]).to(device),
                      torch.from_numpy(data['state_img_q'][index]).to(device))
    mask = torch.from_numpy(data['target_mask'][index]).to(device)
    target = torch.from_numpy(data['targets'][index]).to(device=device, dtype=torch.float32)
    return functional.smooth_l1_loss(output[0, mask], target[mask])


def verify(model: Gr14VinAI, samples: int, seed: int) -> dict:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads, opts.inter_op_num_threads = 4, 1
    session = ort.InferenceSession(str(model.source), opts, providers=['CPUExecutionProvider'])
    fp32 = ort.InferenceSession(model.float32_onnx(), opts, providers=['CPUExecutionProvider'])
    rng = np.random.default_rng(seed)
    state = np.zeros((2, 5, 6, 128, 256), np.uint8)
    maximum = rounding = exported_error = 0.0
    with tempfile.TemporaryDirectory() as folder:
        artifact = Path(folder) / 'restored.onnx'
        model.export(artifact)
        restored = ort.InferenceSession(str(artifact), opts, providers=['CPUExecutionProvider'])
        with torch.no_grad():
            for _ in range(samples):
                frame = rng.integers(0, 256, (2, 6, 128, 256), dtype=np.uint8)
                inputs = {'new_img': frame, 'state_img_q': state}
                native, next_state = session.run(['outputs', 'next_state_img_q'], inputs)
                expected, _ = fp32.run(['outputs', 'next_state_img_q'], inputs)
                exported, exported_state = restored.run(['outputs', 'next_state_img_q'], inputs)
                actual, actual_state = model(torch.from_numpy(frame), torch.from_numpy(state))
                if not torch.isfinite(actual).all():
                    raise ValueError('reconstructed graph returned non-finite output')
                np.testing.assert_array_equal(actual_state.numpy(), next_state)
                np.testing.assert_array_equal(exported_state, next_state)
                maximum = max(maximum, float(np.max(np.abs(expected - actual.numpy()))))
                rounding = max(rounding, float(np.max(np.abs(native - expected))))
                exported_error = max(exported_error, float(np.max(np.abs(native - exported))))
                state = next_state
    return dict(samples=samples, max_abs_error=maximum, fp16_vs_fp32_max_abs_error=rounding,
                unchanged_export_max_abs_error=exported_error, next_state_exact=True,
                input='synthetic random frames, sequential state', compared_with=model.source_sha256,
                precision_note='autograd checked against FP32 ONNX; unchanged export checked against native ONNX')


def train(args: argparse.Namespace, model: Gr14VinAI) -> None:
    if sha256(args.train_data) == sha256(args.val_data):
        raise ValueError('training and validation must be distinct datasets')
    training, validation = load_data(args.train_data), load_data(args.val_data)
    args.out_dir.mkdir(parents=True, exist_ok=False)
    metadata = dict(model.describe(), train_data_sha256=sha256(args.train_data),
                    val_data_sha256=sha256(args.val_data), seed=args.seed, epochs=args.epochs,
                    learning_rate=args.lr, loss='masked smooth L1 on raw outputs',
                    training_samples=len(training['new_img']), validation_samples=len(validation['new_img']),
                    torch_version=str(torch.__version__), status='running', supervised_steps=0)
    metadata_path = args.out_dir / 'training.json'
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    model.to(args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    best = math.inf
    try:
        with (args.out_dir / 'epochs.jsonl').open('x', encoding='utf-8') as log:
            for epoch in range(args.epochs):
                model.train()
                total = 0.0
                for index in torch.randperm(len(training['new_img'])).tolist():
                    optimizer.zero_grad(set_to_none=True)
                    loss = sample_loss(model, training, index, args.device)
                    if not torch.isfinite(loss):
                        raise ValueError(f'non-finite loss at training example {index}')
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
                    optimizer.step()
                    total += float(loss.detach())
                    metadata['supervised_steps'] += 1
                model.eval()
                with torch.no_grad():
                    val_loss = sum(float(sample_loss(model, validation, i, args.device))
                                   for i in range(len(validation['new_img']))) / len(validation['new_img'])
                if not math.isfinite(val_loss):
                    raise ValueError('non-finite validation loss')
                saved = val_loss < best
                if saved:
                    best = val_loss
                    torch.save(dict(source_sha256=model.source_sha256, state_dict=model.state_dict(),
                                    epoch=epoch + 1, validation_loss=val_loss), args.out_dir / 'best.pt')
                record = dict(epoch=epoch + 1, train_loss=total / len(training['new_img']),
                              validation_loss=val_loss, saved_best=saved)
                log.write(json.dumps(record, allow_nan=False) + '\n')
                log.flush()
                print(json.dumps(record), flush=True)
        metadata.update(status='complete', best_validation_loss=best, checkpoint_sha256=sha256(args.out_dir / 'best.pt'))
    except Exception:
        # Persist the actual failed run rather than recording a completed training session.
        metadata['status'] = 'failed'
        raise
    finally:
        metadata_path.write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be finite and > 0')
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=REFERENCE, help='reference 707-output ONNX')
    parser.add_argument('--seed', type=int, default=0)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('--out', type=Path)
    check = commands.add_parser('verify')
    check.add_argument('--samples', type=int, default=3)
    check.add_argument('--atol', type=positive, default=0.001, help='FP32 PyTorch vs FP32 ONNX tolerance, reported explicitly')
    training = commands.add_parser('train')
    training.add_argument('--train-data', type=Path, required=True)
    training.add_argument('--val-data', type=Path, required=True)
    training.add_argument('--epochs', type=int, default=1)
    training.add_argument('--lr', type=positive, default=1e-5)
    training.add_argument('--device', default='cpu')
    training.add_argument('--out-dir', type=Path, required=True)
    export = commands.add_parser('export')
    export.add_argument('--checkpoint', type=Path, help='omit to export unchanged reference weights')
    export.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if getattr(args, 'samples', 1) < 1 or getattr(args, 'epochs', 1) < 1:
        parser.error('samples and epochs must be >= 1')
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    model = Gr14VinAI(args.source)
    if args.command == 'inspect':
        description = json.dumps(model.describe(), indent=2)
        if args.out:
            with args.out.open('x', encoding='utf-8') as stream:
                stream.write(description)
        print(description)
    elif args.command == 'verify':
        report = verify(model, args.samples, args.seed)
        report.update(atol=args.atol, passed=report['max_abs_error'] <= args.atol and report['unchanged_export_max_abs_error'] == 0)
        print(json.dumps(report, indent=2))
        if not report['passed']:
            raise SystemExit('FP32 reconstruction differs beyond specified tolerance')
    elif args.command == 'train':
        train(args, model)
    elif args.command == 'export':
        if args.out.exists() or args.out.with_suffix('.json').exists():
            parser.error(f'refusing to overwrite output or metadata for {args.out}')
        checkpoint_hash = None
        if args.checkpoint:
            checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
            if checkpoint['source_sha256'] != model.source_sha256:
                raise ValueError('checkpoint architecture source differs from --source')
            model.load_state_dict(checkpoint['state_dict'])
            checkpoint_hash = sha256(args.checkpoint)
        model.export(args.out, checkpoint_hash)
        report = dict(model.describe(), checkpoint_sha256=checkpoint_hash,
                      artifact=str(args.out.resolve()), artifact_sha256=sha256(args.out))
        args.out.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
