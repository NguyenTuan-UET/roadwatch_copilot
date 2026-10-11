"""One checkpoint on the test split of dataset _v2, separately for the original test videos and the ones added later.

    GR14_SET=_v2 GR14_RECIPE=<recipe of the checkpoint> GR14_CKPT=<file.pt> python src/eval_sets.py [original]

The has_target threshold is the best one on validation: on all validation videos, or with `original` only on the original
ones (for a model trained on the original videos alone). Scored against the dataset's labels (straight corridor) and, when
`train_distance.py curve` has run, against the labels whose corridor follows the road.
"""
import csv
import sys

import numpy as np
import torch

import train_distance as g
from common import DATA, print_metrics


def main():
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = g.load_net(dev)
    seg = {r["scb_id"]: r for r in csv.DictReader(open(DATA / "manifests/segments.csv", encoding="utf-8"))}
    of = lambda split, key: np.array([seg[r["scb_id"]][key] for r in csv.DictReader(open(DATA / f"labels/{split}.csv", encoding="utf-8"))])
    (xv, yv), (xs, ys) = g.load("val"), g.load("test")
    pv, (_, prob, dist) = g.predict(net, xv, yv, dev)[1], g.predict(net, xs, ys, dev)
    origin, time = of("test", "origin"), of("test", "time_of_day")
    curved = g.CACHE / "test_c.npy"
    for name, yv_, ys_ in [("straight corridor (the dataset's labels)", yv, ys)] + ([("corridor that follows the road", np.load(g.CACHE / "val_c.npy"), np.load(curved))] if curved.exists() else []):
        vok = (yv_[:, 0] >= 0) & ((of("val", "origin") == "original") if "original" in sys.argv else True)
        threshold = g.best_threshold(pv[vok], yv_[vok, 0] > 0)
        print(f"\n===== labels: {name} | threshold {threshold:.2f} from validation ({'original videos' if 'original' in sys.argv else 'all videos'})")
        ok, has, d = ys_[:, 0] >= 0, ys_[:, 0] > 0, ys_[:, 1]
        for title, m in [("original test videos", origin == "original"), ("added test videos", origin == "added"), ("all test videos", origin != "")] + \
                        [(f"added, {t}", (origin == "added") & (time == t)) for t in ("ngay", "chang_vang", "dem")]:
            m = m & ok
            if not (m & has).any():
                continue
            print(f"\n--- {title}")
            print_metrics(has[m], d[m], prob[m], dist[m], threshold)
            err = np.abs(dist - d)
            print("  " + "  ".join(f"({lo},{lo + 20}] m: n={(b := m & has & (d > lo) & (d <= lo + 20)).sum()} MAE {err[b].mean():.2f}" for lo in (40, 60, 80) if (m & has & (d > lo) & (d <= lo + 20)).any()))


if __name__ == "__main__":
    main()
