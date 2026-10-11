"""Validate prepared CSV labels, split isolation and every PNG before training."""

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys

from PIL import Image


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(root, allow_partial=False):
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifests/split_manifest.json').read_text(encoding='utf-8'))
    summary = json.loads((root / 'reports/summary.json').read_text(encoding='utf-8'))
    require(manifest['mode'] == 'extract', 'Audit output has no training images')
    require(summary['status'] == 'complete' or (allow_partial and summary['status'] == 'partial'),
            'Dataset is incomplete; inspect reports/errors.json')
    assignments = {}
    for split, groups in manifest['splits'].items():
        for group in groups:
            require(group not in assignments, f'SCB leakage: {group}')
            assignments[group] = split
    segments = {r['scb_id']: r for r in read_csv(root / 'manifests/segments.csv')}
    rows = read_csv(root / 'manifests/frame_index.csv')
    parameters = manifest['parameters']
    seen, image_paths, usable, per_scb = set(), set(), {}, Counter()
    for row in rows:
        group, split, index = row['scb_id'], row['split'], int(row['frame_index'])
        key = (group, index)
        require(key not in seen, f'Duplicate frame: {key}')
        seen.add(key)
        require(assignments.get(group) == split, f'Wrong split: {key}')
        segment = segments[group]
        require(segment['status'] == 'ready', f'Unusable segment: {group}')
        require(0 <= index < int(segment['frame_count']), f'Bad frame index: {key}')
        require(segment['frame_count'] == segment['decoded_frame_count'], f'Video count mismatch: {group}')
        require(row['image_extracted'] == '1', f'Image not extracted: {key}')
        path = (root / row['image_path']).resolve()
        require(path.is_relative_to(root / 'images' / split / group), f'Invalid image path: {path}')
        require(path not in image_paths, f'Reused image path: {path}')
        image_paths.add(path)
        require(path.is_file(), f'Missing image: {path}')
        with Image.open(path) as image:
            require(image.format == 'PNG', f'Expected PNG: {path}')
            require(image.size == (int(segment['width']), int(segment['height'])), f'Wrong image size: {path}')
            image.verify()
        require(math.isfinite(float(row['frame_time'])), f'Bad timestamp: {key}')
        per_scb[group] += 1
        target = row['has_target']
        if target == '':
            require(row['label_quality'] in ('no_radar_sync', 'invalid_radar'), f'Bad unknown label: {key}')
            require(math.isnan(float(row['distance_m'])), f'Unknown distance must be NaN: {key}')
            continue
        require(target in ('0', '1'), f'Bad target flag: {key}')
        delta = float(row['radar_delta_t'])
        require(math.isfinite(delta) and abs(delta) <= parameters['max_radar_delta_seconds'] + 1e-9,
                f'Bad radar synchronization: {key}')
        require(math.isclose(float(row['radar_time']) - float(row['frame_time']), delta, abs_tol=1e-9),
                f'Inconsistent radar delta: {key}')
        distance = float(row['distance_m'])
        if target == '1':
            require(row['label_quality'] == 'good', f'Bad positive quality: {key}')
            require(0 < distance <= parameters['max_distance_meters'] and abs(distance - 258.6375) > 1e-4,
                    f'Invalid distance: {key}')
            require(abs(float(row['y_rel_m'])) <= parameters['lane_y_meters'], f'Invalid lateral position: {key}')
            require(row['track_id'] != '', f'Missing track: {key}')
        else:
            require(row['label_quality'] == 'no_target' and math.isnan(distance), f'Bad negative label: {key}')
        usable[key] = row
    for group, segment in segments.items():
        if segment['status'] == 'ready':
            require(per_scb[group] == int(segment['selected_count']) == int(segment['image_count']),
                    f'Sample count mismatch: {group}')
    training_count = 0
    for split in ('train', 'val', 'test'):
        labels = read_csv(root / f'labels/{split}.csv')
        expected = {key: row for key, row in usable.items() if row['split'] == split}
        actual = {(r['scb_id'], int(r['frame_index'])): r for r in labels}
        require(len(actual) == len(labels) and actual == expected, f'labels/{split}.csv differs from usable manifest rows')
        training_count += len(labels)
    require(training_count == summary['training_rows'], 'Summary training count mismatch')
    require(len(rows) == summary['extracted_images'], 'Summary image count mismatch')
    bins = {'0-10': 0, '10-20': 0, '20-40': 0, '40-100': 0, 'over-100': 0}
    for row in usable.values():
        if row['has_target'] == '1':
            distance = float(row['distance_m'])
            bucket = '0-10' if distance <= 10 else '10-20' if distance <= 20 else '20-40' if distance <= 40 else '40-100' if distance <= 100 else 'over-100'
            bins[bucket] += 1
    report = {'status': 'passed', 'checked_images': len(rows), 'training_rows': training_count,
              'scb_count': len(per_scb), 'cross_split_route_count': summary['cross_split_route_count'],
              'distance_bins_m': bins,
              'target_counts_by_split': {split: dict(Counter(r['has_target'] for r in usable.values() if r['split'] == split))
                                         for split in ('train', 'val', 'test')}}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--allow-partial', action='store_true', help='Validate surviving rows of a reported partial run')
    args = parser.parse_args()
    try:
        report = validate(args.dataset, args.allow_partial)
        (args.dataset / 'reports/validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f'VALIDATION FAILED: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
