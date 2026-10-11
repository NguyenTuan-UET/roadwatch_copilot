"""Prepare whole-SCB camera/radar datasets. See docs/preprocessing.md."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw

SPLITS = ('train', 'val', 'test')
FIELDS = ['split', 'scb_id', 'segment_id', 'route_id', 'frame_index', 'image_path',
          'frame_time', 'radar_time', 'distance_m', 'has_target', 'track_id',
          'y_rel_m', 'radar_delta_t', 'label_quality', 'image_extracted']
SEGMENT_FIELDS = ['scb_id', 'split', 'route_id', 'source_segment', 'video_path',
                  'frame_count', 'decoded_frame_count', 'duration_s', 'width', 'height',
                  'radar_count', 'radar_start_time', 'radar_end_time', 'selected_count',
                  'image_count', 'annotation_count', 'status', 'error']


def split_groups(groups, ratios, seed):
    if len(ratios) != 3 or any(not math.isfinite(r) or r <= 0 for r in ratios) or not math.isclose(sum(ratios), 1):
        raise ValueError('Split ratios must be three positive numbers summing to 1.')
    groups = sorted(set(groups), key=lambda name: int(name[3:]))
    if len(groups) < 3:
        raise ValueError('At least 3 SCBs are needed for train/val/test.')
    raw = np.asarray(ratios) * len(groups)
    counts = np.floor(raw).astype(int)
    for i in sorted(range(3), key=lambda i: -(raw[i] - counts[i]))[:len(groups) - sum(counts)]:
        counts[i] += 1
    for i in range(3):
        if counts[i] == 0:
            donor = int(np.argmax(counts))
            counts[donor] -= 1
            counts[i] = 1
    random.Random(seed).shuffle(groups)
    assignments, start = {}, 0
    for split, count in zip(SPLITS, counts):
        assignments.update({group: split for group in groups[start:start + count]})
        start += count
    return assignments


def select_frames(frame_count, requested):
    if frame_count <= 0 or requested <= 0:
        raise ValueError('Frame counts must be positive.')
    return np.floor(np.arange(min(requested, frame_count)) * frame_count / min(requested, frame_count)).astype(int)


def load_arrays(scb):
    pose = scb / 'global_pose/frame_times'
    if not pose.exists():
        pose = scb / 'global_pos/frame_times'
    frames = np.load(pose, allow_pickle=False)
    times = np.load(scb / 'processed_log/CAN/radar/t', allow_pickle=False)
    values = np.load(scb / 'processed_log/CAN/radar/value', allow_pickle=False)
    for name, array, strict in [('frame_times', frames, True), ('radar/t', times, False)]:
        if array.ndim != 1 or not len(array) or not np.isfinite(array).all():
            raise ValueError(f'{name}: expected nonempty finite 1D timestamps')
        if np.any(np.diff(array) <= 0) if strict else np.any(np.diff(array) < 0):
            raise ValueError(f'{name}: timestamps not ordered')
    if values.shape != (len(times), 7) or not np.issubdtype(values.dtype, np.number):
        raise ValueError('radar/value must have shape (len(radar/t), 7) and numeric dtype')
    if frames[-1] < times[0] or frames[0] > times[-1]:
        raise ValueError('Camera and radar timestamp ranges do not overlap')
    return frames, times, values


def label_frame(frame_time, times, values, lane_y, max_distance, max_delta):
    label = dict(radar_time=None, distance_m=float('nan'), has_target=None, track_id=None,
                 y_rel_m=None, radar_delta_t=None, label_quality='no_radar_sync')
    left = np.searchsorted(times, frame_time - max_delta, side='left')
    right = np.searchsorted(times, frame_time + max_delta, side='right')
    if left == right:
        return label
    # CAN track messages do not necessarily share an identical timestamp.
    # Select the nearest update per track BEFORE filtering invalid/sentinel ranges,
    # so an older positive detection cannot replace a newer no-target update.
    nearest = {}
    for index in range(left, right):
        track = values[index, 5]
        if not np.isfinite(track) or track != int(track):
            continue
        if track not in nearest or abs(times[index] - frame_time) < abs(times[nearest[track]] - frame_time):
            nearest[track] = index
    indices = [i for i in nearest.values() if np.isfinite(values[i, :2]).all()]
    if not indices:
        label['label_quality'] = 'invalid_radar'
        return label
    targets = [i for i in indices if 0 < values[i, 0] <= max_distance
               and not np.isclose(values[i, 0], 258.6375, rtol=0, atol=1e-4)
               and abs(values[i, 1]) <= lane_y]
    if targets:
        index = min(targets, key=lambda i: (values[i, 0], abs(times[i] - frame_time), values[i, 5]))
        label.update(distance_m=float(values[index, 0]), has_target=1, track_id=int(values[index, 5]),
                     y_rel_m=float(values[index, 1]), label_quality='good')
    else:
        index = min(indices, key=lambda i: abs(times[i] - frame_time))
        label.update(has_target=0, label_quality='no_target')
    label.update(radar_time=float(times[index]), radar_delta_t=float(times[index] - frame_time))
    return label


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def extract_frames(video, indices, destination, expected_count, log_path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.extract-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        # A flat sum of 120 eq() terms exceeds FFmpeg's expression depth limit.
        terms = [f'eq(n,{int(index)})' for index in indices]
        while len(terms) > 1:
            terms = ['(' + '+'.join(terms[i:i + 2]) + ')' for i in range(0, len(terms), 2)]
        selection = terms[0]
        command = ['ffmpeg', '-hide_banner', '-nostdin', '-xerror', '-threads', '2', '-i', str(video),
                   '-map', '0:v:0', '-an', '-vf', f"showinfo=checksum=0,select='{selection}'",
                   '-fps_mode', 'vfr', '-threads', '2', '-compression_level', '3',
                   '-start_number', '0', str(stage / '%06d.png')]
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')
        log_path.write_text(result.stderr, encoding='utf-8')
        if result.returncode:
            raise ValueError(f'FFmpeg failed; see {log_path.name}: {result.stderr[-500:]}')
        decoded = re.findall(r'Parsed_showinfo_\d+[^\n]*\bn:\s*(\d+)[^\n]*\bs:(\d+)x(\d+)', result.stderr)
        if len(decoded) != expected_count or [int(row[0]) for row in decoded] != list(range(expected_count)):
            raise ValueError(f'Video/timestamp frame mismatch: decoded={len(decoded)}, timestamps={expected_count}')
        sizes = {(int(row[1]), int(row[2])) for row in decoded}
        if len(sizes) != 1:
            raise ValueError('Video dimensions change within segment')
        if len(list(stage.glob('*.png'))) != len(indices):
            raise ValueError('Extracted PNG count does not match selected indices')
        # Rename through distinct names so selected source indices cannot collide
        # with FFmpeg's sequential output numbering.
        for sequence, index in enumerate(indices):
            (stage / f'{sequence:06d}.png').rename(stage / f'frame_{index:06d}.png')
        # Windows can briefly keep the freshly written directory locked.
        for attempt in range(6):
            try:
                stage.rename(destination)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.2 * (attempt + 1))
        return (*next(iter(sizes)), len(decoded))


def save_overlays(output, scb_id, rows, count):
    if not rows or count == 0:
        return
    target = output / 'reports/overlays' / scb_id
    target.mkdir(parents=True, exist_ok=True)
    for index in select_frames(len(rows), count):
        row = rows[index]
        with Image.open(output / row['image_path']) as source:
            preview = source.convert('RGB')
        preview.thumbnail((960, 720))
        draw = ImageDraw.Draw(preview)
        text = (f"{scb_id} | {row['split']} | frame {row['frame_index']}\n"
                f"target={row['has_target']}  distance={row['distance_m']:.2f} m  track={row['track_id']}\n"
                f"yRel={row['y_rel_m']}  delta_t={row['radar_delta_t']}\n"
                f"{row['label_quality']} | radar heuristic; no object association")
        draw.rectangle((0, 0, preview.width, 65), fill='black')
        draw.multiline_text((5, 5), text, fill='white', spacing=3)
        preview.save(target / f"frame_{row['frame_index']:06d}.jpg", quality=90)


def run(args):
    root, output = args.input.resolve(), args.output.resolve()
    if not root.is_dir():
        raise ValueError(f'Input directory does not exist: {root}')
    groups = sorted((p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'scb[1-9][0-9]*', p.name)),
                    key=lambda p: int(p.name[3:]))
    assignments = split_groups([p.name for p in groups], args.ratios, args.seed)
    if args.only and set(args.only) - set(assignments):
        raise ValueError('Unknown SCB in --only')
    if output == root or root.is_relative_to(output) or any(output.is_relative_to(p) for p in groups):
        raise ValueError('Output must be a separate directory outside the source SCBs')
    if output.exists():
        raise ValueError(f'Output already exists; choose a new directory: {output}')
    if not args.audit and not shutil.which('ffmpeg'):
        raise ValueError('FFmpeg is missing from PATH')
    routes = {}
    index_path = root / 'scenario_index.csv'
    if index_path.exists():
        with index_path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row['sc_name'] in routes:
                    raise ValueError(f"Duplicate SCB in scenario_index.csv: {row['sc_name']}")
                routes[row['sc_name']] = row['path']
    route_splits = defaultdict(set)
    for group, split in assignments.items():
        if group in routes:
            route_splits[routes[group].rsplit('/', 1)[0]].add(split)
    parameters = {'frames_per_video': args.frames_per_video, 'lane_y_meters': args.lane_y_meters,
                  'max_distance_meters': args.max_distance_meters,
                  'max_radar_delta_seconds': args.max_radar_delta_seconds, 'seed': args.seed,
                  'ratios': list(args.ratios), 'sampling': 'floor(k * frame_count / selected_count)',
                  'radar_matching': 'nearest row per track within window, then closest valid distance',
                  'sentinel_m': 258.6375, 'image_format': 'PNG', 'resize': False}
    output.mkdir(parents=True)
    for directory in ('manifests', 'labels', 'reports/logs', 'calibration'):
        (output / directory).mkdir(parents=True)
    (output / 'calibration/README.txt').write_text('No camera-radar extrinsics supplied. No projection or bounding-box association is performed.\n', encoding='utf-8')
    selected = [p for p in groups if not args.only or p.name in args.only]
    manifest = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'input_root': str(root),
                'mode': 'audit' if args.audit else 'extract', 'parameters': parameters,
                'splits': {s: sorted(g for g in assignments if assignments[g] == s) for s in SPLITS},
                'selected_scbs': [p.name for p in selected],
                'cross_split_routes': {r: sorted(s) for r, s in route_splits.items() if len(s) > 1},
                'route_warning': 'Split unit is SCB, as requested. SCBs from one route may cross splits.'}
    write_json(output / 'manifests/split_manifest.json', manifest)
    all_rows, segments, issues = [], [], []
    for number, scb in enumerate(selected, 1):
        split = assignments[scb.name]
        source_segment = routes.get(scb.name, '')
        route = source_segment.rsplit('/', 1)[0] if source_segment else ''
        segment = dict.fromkeys(SEGMENT_FIELDS, '')
        segment.update(scb_id=scb.name, split=split, route_id=route, source_segment=source_segment,
                       image_count=0, annotation_count=0, status='failed')
        try:
            videos = [p for p in (scb / 'video.hevc', scb / 'video.mp4') if p.is_file()]
            if not videos:
                raise ValueError('Missing video.hevc/video.mp4')
            video = videos[0]
            segment['video_path'] = video.relative_to(root).as_posix()
            frames, times, values = load_arrays(scb)
            indices = select_frames(len(frames), args.frames_per_video)
            segment.update(frame_count=len(frames), duration_s=float(frames[-1] - frames[0]),
                           radar_count=len(times), radar_start_time=float(times[0]), radar_end_time=float(times[-1]),
                           selected_count=len(indices))
            rows = []
            for index in indices:
                image_path = f'images/{split}/{scb.name}/frame_{index:06d}.png'
                row = dict(split=split, scb_id=scb.name, segment_id=scb.name, route_id=route,
                           frame_index=int(index), image_path=image_path, frame_time=float(frames[index]),
                           image_extracted=int(not args.audit))
                row.update(label_frame(frames[index], times, values, args.lane_y_meters,
                                       args.max_distance_meters, args.max_radar_delta_seconds))
                rows.append(row)
            if not args.audit:
                width, height, count = extract_frames(video, indices, output / f'images/{split}/{scb.name}',
                                                     len(frames), output / f'reports/logs/{scb.name}.log')
                segment.update(width=width, height=height, decoded_frame_count=count, image_count=len(rows))
                save_overlays(output, scb.name, rows, args.overlays_per_scb)
            segment.update(status='audited' if args.audit else 'ready',
                           annotation_count=sum(r['has_target'] is not None for r in rows))
            all_rows.extend(rows)
        except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
            segment['error'] = str(error)
            issues.append({'scb_id': scb.name, 'error': str(error)})
        segments.append(segment)
        print(f'[{number}/{len(selected)}] {scb.name}: {segment["status"]} {segment["error"]}', flush=True)
        # Checkpoint metadata after each SCB; summary.json is written only on completion.
        write_csv(output / 'manifests/segments.csv', SEGMENT_FIELDS, segments)
        write_csv(output / 'manifests/frame_index.csv', FIELDS, all_rows)
    usable = [r for r in all_rows if r['has_target'] is not None and r['image_extracted']]
    for split in SPLITS:
        write_csv(output / f'labels/{split}.csv', FIELDS, [r for r in usable if r['split'] == split])
    write_csv(output / 'reports/rejected_frames.csv', FIELDS, [r for r in all_rows if r['has_target'] is None])
    write_json(output / 'reports/errors.json', issues)
    summary = {'mode': manifest['mode'], 'status': 'partial' if issues else ('audit_only' if args.audit else 'complete'),
               'selected_scbs': len(selected), 'failed_scbs': len(issues), 'sampled_frames': len(all_rows),
               'extracted_images': sum(r['image_extracted'] for r in all_rows), 'training_rows': len(usable),
               'label_quality': dict(Counter(r['label_quality'] for r in all_rows)),
               'split_scbs': {s: sum(assignments[p.name] == s for p in selected) for s in SPLITS},
               'training_rows_by_split': {s: sum(r['split'] == s for r in usable) for s in SPLITS},
               'cross_split_route_count': len(manifest['cross_split_routes'])}
    write_json(output / 'reports/summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)
    return 2 if issues else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('prepared_dataset'))
    parser.add_argument('--frames-per-video', type=int, default=120)
    parser.add_argument('--ratios', type=float, nargs=3, default=(0.8, 0.1, 0.1), metavar=('TRAIN', 'VAL', 'TEST'))
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--lane-y-meters', type=float, default=1.5)
    parser.add_argument('--max-distance-meters', type=float, default=100)
    parser.add_argument('--max-radar-delta-seconds', type=float, default=0.05)
    parser.add_argument('--overlays-per-scb', type=int, default=3)
    parser.add_argument('--audit', action='store_true', help='Check arrays/labels without decoding videos; not training data')
    parser.add_argument('--only', nargs='+', help='Process named SCBs but keep split assignment based on all source SCBs')
    args = parser.parse_args(argv)
    if args.frames_per_video <= 0 or args.overlays_per_scb < 0:
        parser.error('frames-per-video must be positive; overlays-per-scb must be nonnegative')
    if any(not math.isfinite(v) or v <= 0 for v in (args.lane_y_meters, args.max_distance_meters, args.max_radar_delta_seconds)):
        parser.error('Radar thresholds must be finite positive numbers')
    try:
        return run(args)
    except (OSError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
