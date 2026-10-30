"""Download the model from cuongnh04/model_Gr14VinAI at the pinned commit, verify its SHA-256 and save it as
models/gr14VinAI.onnx. The file there is already pruned (prune_model.py), so it is not pruned again."""
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.roadwatch.model import PRUNED_PATH

URL = 'https://github.com/cuongnh04/model_Gr14VinAI/raw/98804d07f3ec3ed9abec5cf666205ca9dd24a91d/gr14VinAI.onnx'
SHA256 = 'a2fa1fb549537fe219fa650838d5f9cab56a23906df91966b294c306e8deaf77'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    if PRUNED_PATH.exists():
        sys.exit(f'{PRUNED_PATH} already present')
    PRUNED_PATH.parent.mkdir(exist_ok=True)
    tmp = PRUNED_PATH.with_suffix('.partial')
    urllib.request.urlretrieve(URL, tmp)
    if sha256(tmp) != SHA256:
        tmp.unlink()
        sys.exit('SHA-256 mismatch, download discarded')
    tmp.rename(PRUNED_PATH)
    print(f'saved {PRUNED_PATH}')
