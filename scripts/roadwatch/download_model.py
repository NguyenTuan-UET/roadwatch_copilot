"""Download openpilot's driving_supercombo.onnx (MIT) at the pinned commit, verify its SHA-256,
prune it to models/gr14VinAI.onnx and delete the full model; only the pruned model is kept."""
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.roadwatch.model import MODEL_SHA256, PRUNED_PATH

sys.path.insert(0, str(Path(__file__).parent))
from prune_model import MODEL_PATH, prune  # noqa: E402

URL = ('https://media.githubusercontent.com/media/commaai/openpilot/c933446486e6923c8468a979b6fab890b46f5cdb/'
       'openpilot/selfdrive/modeld/models/driving_supercombo.onnx')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    if PRUNED_PATH.exists():
        sys.exit(f'{PRUNED_PATH} already present')
    MODEL_PATH.parent.mkdir(exist_ok=True)
    tmp = MODEL_PATH.with_suffix('.partial')
    urllib.request.urlretrieve(URL, tmp)
    if sha256(tmp) != MODEL_SHA256:
        tmp.unlink()
        sys.exit('SHA-256 mismatch, download discarded')
    tmp.rename(MODEL_PATH)
    try:
        prune()
    finally:
        MODEL_PATH.unlink()
    print(f'deleted {MODEL_PATH.name}; runtime uses {PRUNED_PATH.name}')
