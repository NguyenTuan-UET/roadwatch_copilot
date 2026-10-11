"""Technical checks on the reconstruction; synthetic examples are not training evidence."""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import pytest
import torch
from onnx import numpy_helper

from model import REFERENCE, Gr14VinAI, sha256
from train import load_data, train, verify


@pytest.fixture(scope='module')
def model():
    if not REFERENCE.exists():
        pytest.skip('reference ONNX not present')
    torch.set_num_threads(4)
    return Gr14VinAI()


def test_graph_and_unchanged_export_match_reference(model, tmp_path):
    artifact = tmp_path / 'restored.onnx'
    model.export(artifact)
    got = onnx.load(str(artifact))
    source = onnx.load(str(REFERENCE))
    assert [n.SerializeToString() for n in got.graph.node] == [n.SerializeToString() for n in source.graph.node]
    for expected, actual in zip(source.graph.initializer, got.graph.initializer, strict=True):
        assert expected.name == actual.name
        np.testing.assert_array_equal(numpy_helper.to_array(expected), numpy_helper.to_array(actual))
    report = verify(model, 3, 0)
    assert report['next_state_exact']
    assert report['unchanged_export_max_abs_error'] == 0
    assert report['max_abs_error'] < 0.001


def test_reference_cannot_be_overwritten(model):
    with pytest.raises(ValueError, match='overwrite'):
        model.export(REFERENCE)


def test_rejects_old_three_head_interface():
    old = Path(__file__).resolve().parents[1] / 'model/gr14VinAI.onnx'
    if not old.exists():
        pytest.skip('legacy model not present')
    with pytest.raises(ValueError, match='707-output'):
        Gr14VinAI(old)


def test_one_real_gradient_step_changes_weights_and_export_is_runnable(tmp_path):
    import onnxruntime as ort

    if not REFERENCE.exists():
        pytest.skip('reference ONNX not present')
    torch.set_num_threads(4)
    torch.manual_seed(0)
    net = Gr14VinAI()
    image = np.full((1, 2, 6, 128, 256), 128, np.uint8)
    state = np.zeros((1, 2, 5, 6, 128, 256), np.uint8)
    with torch.no_grad():
        baseline = net(torch.from_numpy(image[0]), torch.from_numpy(state[0]))[0].numpy()
    mask = np.zeros((1, 707), bool)
    mask[0, 560] = True  # current distance mean of first lead choice, not a fabricated full set of labels
    target = np.full((1, 707), np.nan, np.float32)
    target[0, 560] = baseline[0, 560] + 1
    training, validation = tmp_path / 'train.npz', tmp_path / 'val.npz'
    np.savez(training, new_img=image, state_img_q=state, targets=target, target_mask=mask)
    target[0, 560] += 0.1
    np.savez(validation, new_img=image, state_img_q=state, targets=target, target_mask=mask)
    output = tmp_path / 'run'
    args = argparse.Namespace(train_data=training, val_data=validation, out_dir=output,
                              seed=0, epochs=1, lr=1e-5, device='cpu')
    train(args, net)
    metadata = json.loads((output / 'training.json').read_text())
    assert metadata['status'] == 'complete' and metadata['supervised_steps'] == 1
    checkpoint = torch.load(output / 'best.pt', weights_only=True)
    assert checkpoint['source_sha256'] == sha256(REFERENCE)
    assert all(torch.isfinite(w).all() for w in checkpoint['state_dict'].values())
    exported = tmp_path / 'trained.onnx'
    net.load_state_dict(checkpoint['state_dict'])
    net.export(exported, sha256(output / 'best.pt'))
    source_weights = {w.name: numpy_helper.to_array(w) for w in onnx.load(str(REFERENCE)).graph.initializer}
    assert any(not np.array_equal(numpy_helper.to_array(w), source_weights[w.name])
               for w in onnx.load(str(exported)).graph.initializer)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    session = ort.InferenceSession(str(exported), opts, providers=['CPUExecutionProvider'])
    result, next_state = session.run(None, {'new_img': image[0], 'state_img_q': state[0]})
    assert result.shape == (1, 707) and np.isfinite(result).all()
    assert next_state.shape == (2, 5, 6, 128, 256)


def test_dataset_cannot_silently_treat_missing_targets_as_zero(tmp_path):
    path = tmp_path / 'bad.npz'
    np.savez(path, new_img=np.zeros((1, 2, 6, 128, 256), np.uint8),
             state_img_q=np.zeros((1, 2, 5, 6, 128, 256), np.uint8),
             targets=np.full((1, 707), np.nan, np.float32), target_mask=np.ones((1, 707), bool))
    with pytest.raises(ValueError, match='finite'):
        load_data(path)
