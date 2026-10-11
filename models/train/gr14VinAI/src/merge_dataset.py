"""Join the 100 original videos with the 254 collected later into dataset "_v2", the one everything else works on.

    python src/merge_dataset.py        then   python src/train_distance.py prepare | dense | radar | curve

data/prepared_dataset/          the original 100 videos as preprocess_dataset.py prepared them (images, labels, 80/10/10 split)
data/prepared_dataset_added/    the 254 added videos, prepared the same way; manifests/selection.csv says why each was picked
data/prepared_dataset_v2/       written here: labels/ and manifests/ of all 354 with the split below; images stay where they are

The original 80/10/10 split is kept as it is, so results on its test videos stay comparable. Of the new videos:
  - those from a drive that already has videos in the original train split go to train (that drive is in no other split);
  - the rest are split by drive, 80/10/10 within each (car, time of day) group, so no new drive is in two splits.
Labels are the ones the preprocessing script already wrote for each video; nothing is relabelled here. The videos
themselves are all in data/raw/.
"""
import csv
import json
import random
from collections import Counter, defaultdict

from common import RAW, ROOT

OLD, NEW, OUT = ROOT / "data/prepared_dataset", ROOT / "data/prepared_dataset_added", ROOT / "data/prepared_dataset_v2"
SPLITS = ("train", "val", "test")
read = lambda path: list(csv.DictReader(open(path, encoding="utf-8")))
drive = lambda path: path.rsplit("/", 1)[0]


def main():
    manifest = json.loads((OLD / "manifests/split_manifest.json").read_text(encoding="utf-8"))
    assert manifest["parameters"] == json.loads((NEW / "manifests/split_manifest.json").read_text(encoding="utf-8"))["parameters"]
    old = {r["sc_name"]: r["path"] for r in read(RAW / "scenario_index.csv") if int(r["sc_name"][3:]) <= 100}
    split = {scb: s for s in SPLITS for scb in manifest["splits"][s]}
    assert set(split) == set(old) and len(old) == 100
    old_splits = defaultdict(set)
    for scb, path in old.items():
        old_splits[drive(path)].add(split[scb])
    kind = {"day": "ngay", "dusk": "chang_vang", "night": "dem"}
    time = {scb: kind[k] for scb, k in json.loads((ROOT / "results/time_of_day.json").read_text(encoding="utf-8"))["kind"].items()}

    new = read(NEW / "manifests/selection.csv")
    assert not {r["path"] for r in new} & set(old.values()) and len({r["path"] for r in new}) == len(new)
    groups = defaultdict(lambda: defaultdict(list))  # (car, time of day) -> drive -> videos
    for r in new:
        time[r["sc_name"]] = r["thoi_diem"]
        if drive(r["path"]) in old_splits:
            assert old_splits[drive(r["path"])] == {"train"}, r["path"]
            split[r["sc_name"]] = "train"
        else:
            groups[r["xe"]][drive(r["path"])].append(r)
    rng = random.Random(0)
    for car, drives in sorted(groups.items()):
        by_time = defaultdict(list)
        for d, rows in sorted(drives.items()):
            times = Counter(r["thoi_diem"] for r in rows)
            by_time["chang_vang" if "chang_vang" in times else times.most_common(1)[0][0]].append(d)
        for t, ds in sorted(by_time.items()):
            rng.shuffle(ds)
            total, got = sum(len(drives[d]) for d in ds), Counter()
            for i, d in enumerate(ds):  # test first, then validation, each up to a tenth of the group's videos
                to = "test" if got["test"] < 0.1 * total and len(ds) >= 2 else "val" if got["val"] < 0.1 * total and len(ds) >= 3 else "train"
                got[to] += len(drives[d])
                for r in drives[d]:
                    split[r["sc_name"]] = to
    path = {**old, **{r["sc_name"]: r["path"] for r in new}}
    where = defaultdict(set)
    for scb in path:
        if scb not in old:
            where[drive(path[scb])].add(split[scb])
    assert all(len(s) == 1 for s in where.values()), "a new drive is in two splits"

    assert all((RAW / scb / "video.hevc").is_file() for scb in path), "a video is missing from data/raw"
    rows = [dict(r, image_path=f"../{folder.name}/{r['image_path']}")  # relative to OUT, so DATA / image_path finds the picture
            for folder in (OLD, NEW) for s in SPLITS for r in read(folder / f"labels/{s}.csv")]
    (OUT / "labels").mkdir(parents=True, exist_ok=True)
    (OUT / "manifests").mkdir(exist_ok=True)
    for s in SPLITS:
        with open(OUT / f"labels/{s}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(rows[0]))
            w.writeheader()
            w.writerows(dict(r, split=s) for r in rows if split[r["scb_id"]] == s)
    order = sorted(path, key=lambda scb: int(scb[3:]))
    manifest.update(splits={s: [scb for scb in order if split[scb] == s] for s in SPLITS}, selected_scbs=order,
                    route_warning="Original 100 videos: split by video, as before. Videos added later: split by drive.")
    manifest.pop("cross_split_routes", None)
    (OUT / "manifests/split_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    with open(OUT / "manifests/segments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scb_id", "split", "origin", "time_of_day", "path"])
        w.writerows([scb, split[scb], "original" if scb in old else "added", time[scb], path[scb]] for scb in order)
    for s in SPLITS:
        scbs = manifest["splits"][s]
        print(f"{s}: {len(scbs)} videos ({sum(scb in old for scb in scbs)} original, {sum(scb not in old for scb in scbs)} added) | "
              f"{dict(Counter(time[scb] for scb in scbs))} | {sum(split[r['scb_id']] == s for r in rows)} labelled frames")


if __name__ == "__main__":
    main()
