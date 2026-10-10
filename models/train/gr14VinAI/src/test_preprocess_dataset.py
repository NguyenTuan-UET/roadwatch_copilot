import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import preprocess_dataset as prep
import validate_dataset as validation


class PreprocessTests(unittest.TestCase):
    def test_split_is_reproducible_and_whole_scb(self):
        groups = [f'scb{i}' for i in range(1, 101)]
        split = prep.split_groups(groups, (0.8, 0.1, 0.1), 42)
        self.assertEqual([list(split.values()).count(s) for s in prep.SPLITS], [80, 10, 10])
        self.assertEqual(split, prep.split_groups(list(reversed(groups)), (0.8, 0.1, 0.1), 42))
        self.assertEqual(set(split), set(groups))

    def test_sampling_spans_short_and_irregular_videos(self):
        self.assertEqual(prep.select_frames(1200, 120).tolist(), list(range(0, 1200, 10)))
        indices = prep.select_frames(1196, 120)
        self.assertEqual(len(set(indices)), 120)
        self.assertGreater(indices[-1], 1180)
        self.assertEqual(prep.select_frames(3, 120).tolist(), [0, 1, 2])

    def test_radar_considers_tracks_and_nearest_update_before_filtering(self):
        times = np.array([0.98, 0.99, 1.0, 1.01, 1.02])
        values = np.array([[5, 0, 0, 0, 0, 1, 0], [30, 0, 0, 0, 0, 2, 0],
                           [258.6375, 0, 0, 0, 0, 1, 0], [10, 2, 0, 0, 0, 3, 0],
                           [20, 1.5, 0, 0, 0, 4, 0]])
        label = prep.label_frame(1.0, times, values, 1.5, 100, 0.05)
        self.assertEqual((label['distance_m'], label['track_id']), (20, 4))
        self.assertEqual(label['has_target'], 1)
        self.assertAlmostEqual(label['radar_delta_t'], 0.02)

    def test_unknown_sync_is_not_a_negative(self):
        values = np.array([[258.6375, 0, 0, 0, 0, 1, 0]])
        negative = prep.label_frame(1, np.array([1.0]), values, 1.5, 100, 0.05)
        unknown = prep.label_frame(2, np.array([1.0]), values, 1.5, 100, 0.05)
        self.assertEqual(negative['has_target'], 0)
        self.assertTrue(np.isnan(negative['distance_m']))
        self.assertIsNone(unknown['has_target'])
        self.assertEqual(unknown['label_quality'], 'no_radar_sync')

    def test_radar_limits_and_bad_values(self):
        for distance, lateral, expected in [(100, -1.5, 1), (100.01, 0, 0), (0, 0, 0), (-1, 0, 0)]:
            values = np.array([[distance, lateral, 0, 0, 0, 1, 0]])
            self.assertEqual(prep.label_frame(0, np.array([0.0]), values, 1.5, 100, 0.05)['has_target'], expected)
        bad = np.array([[np.nan, 0, 0, 0, 0, 1, 0]])
        self.assertIsNone(prep.label_frame(0, np.array([0.0]), bad, 1.5, 100, 0.05)['has_target'])

    def test_invalid_ratios_are_rejected(self):
        for ratios in [(1, 0, 0), (0.8, 0.2, 0.1), (float('nan'), 0.1, 0.1)]:
            with self.assertRaises(ValueError):
                prep.split_groups(['scb1', 'scb2', 'scb3'], ratios, 42)

    def test_invalid_sensor_timestamps_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            scb = Path(directory)
            (scb / 'global_pose').mkdir()
            (scb / 'processed_log/CAN/radar').mkdir(parents=True)
            for path, array in [('processed_log/CAN/radar/t', np.array([1.0, 2.0])),
                                ('processed_log/CAN/radar/value', np.zeros((2, 7)))]:
                with (scb / path).open('wb') as stream:
                    np.save(stream, array)
            for bad_frames in [[], [float('nan')], [2.0, 1.0], [1.0, 1.0], [10.0, 11.0]]:
                with (scb / 'global_pose/frame_times').open('wb') as stream:
                    np.save(stream, np.array(bad_frames))
                with self.assertRaises(ValueError):
                    prep.load_arrays(scb)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_extract_120_frames_avoids_ffmpeg_expression_depth_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=64x48:r=20',
                            '-frames:v', '241', '-c:v', 'mpeg4', str(video)], check=True)
            indices = prep.select_frames(241, 120)
            size = prep.extract_frames(video, indices, root / 'images', 241, root / 'extract.log')
            self.assertEqual(size, (64, 48, 241))
            self.assertEqual(len(list((root / 'images').glob('*.png'))), 120)
            reference = root / 'reference.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-vf', f"select='eq(n,{indices[-1]})'",
                            '-frames:v', '1', str(reference)], check=True)
            with prep.Image.open(reference) as expected, prep.Image.open(root / f'images/frame_{indices[-1]:06d}.png') as actual:
                np.testing.assert_array_equal(np.array(actual), np.array(expected))
            original_rename = Path.rename
            transient_lock = []
            def rename_with_one_lock(path, target):
                if path.name.startswith('.extract-') and not transient_lock:
                    transient_lock.append(True)
                    raise PermissionError('Simulated transient Windows directory lock')
                return original_rename(path, target)
            with patch.object(Path, 'rename', rename_with_one_lock):
                prep.extract_frames(video, indices[:1], root / 'retry_images', 241, root / 'retry.log')
            self.assertTrue((root / 'retry_images/frame_000000.png').exists())

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_real_video_pipeline_excludes_bad_segment_and_protects_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(1, 4):
                scb = root / f'scb{number}'
                (scb / 'global_pose').mkdir(parents=True)
                (scb / 'processed_log/CAN/radar').mkdir(parents=True)
                for path, array in [('global_pose/frame_times', np.arange(4) / 4),
                                    ('processed_log/CAN/radar/t', np.array([0, .25, .5, .5]) if number == 2 else np.arange(4) / 4),
                                    ('processed_log/CAN/radar/value', np.tile([20, 0, 0, 0, 0, 1072, 0], (4, 1)))]:
                    with (scb / path).open('wb') as stream:
                        np.save(stream, array)
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=64x48:r=4',
                                '-frames:v', str(3 if number == 3 else 4), '-c:v', 'mpeg4', str(scb / 'video.mp4')], check=True)
            output = root / 'prepared'
            cmd = [sys.executable, str(Path(prep.__file__)), '--input', str(root), '--output', str(output), '--frames-per-video', '4']
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            with (output / 'manifests/frame_index.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 8)
            self.assertTrue(all((output / row['image_path']).exists() for row in rows))
            self.assertEqual({row['scb_id'] for row in rows}, {'scb1', 'scb2'})
            summary = json.loads((output / 'reports/summary.json').read_text())
            self.assertEqual(summary['failed_scbs'], 1)
            self.assertEqual(summary['training_rows'], 7)
            self.assertEqual(summary['label_quality']['no_radar_sync'], 1)
            report = validation.validate(output, allow_partial=True)
            self.assertEqual(report['checked_images'], 8)
            self.assertEqual(report['distance_bins_m']['10-20'], 7)
            with self.assertRaises(ValueError):
                validation.validate(output)
            (output / rows[0]['image_path']).unlink()
            with self.assertRaises(ValueError):
                validation.validate(output, allow_partial=True)
            second = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(len(list(output.glob('images/*/*/*.png'))), 7)


if __name__ == '__main__':
    unittest.main()
