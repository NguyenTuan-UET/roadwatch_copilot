import tempfile
import unittest

import numpy as np

import app
from common import RAW, X_IDXS


class AppTests(unittest.TestCase):
    def test_an_uploaded_copy_of_a_dataset_video_is_recognised_and_gets_its_radar(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = f"{tmp}/video.hevc"  # an upload keeps the content, not the scb folder it came from
            with open(copy, "wb") as f:
                f.write((RAW / "scb4/video.hevc").read_bytes())
            self.assertEqual(app.which_scb(copy), "scb4")
            with open(copy, "ab") as f:
                f.write(b"x")
            self.assertIsNone(app.which_scb(copy))
        split, radar = app.radar_of("scb4")
        self.assertEqual(split, "test")
        self.assertEqual(radar[0], (49.6375, 1.8125))  # labels_curved/test.csv, first row: metres, yRel

    def test_picture_puts_every_pixel_back_where_it_was(self):
        luma = np.zeros((256, 512), np.float32)
        luma[101, 300] = 255  # odd row, even column: lands in the second of the four pixel phases
        frame = np.stack([luma[0::2, 0::2], luma[1::2, 0::2], luma[0::2, 1::2], luma[1::2, 1::2],
                          np.full((128, 256), 128, np.float32), np.full((128, 256), 128, np.float32)])
        rgb = app.picture(frame)
        self.assertEqual(rgb.shape, (256, 512, 3))
        self.assertEqual(np.unravel_index(rgb.sum(2).argmax(), (256, 512)), (101, 300))

    def test_the_distance_bar_is_drawn_on_the_lane_the_model_predicts(self):
        black = np.zeros((256, 512, 3), np.uint8)
        # 50 m ahead the road is on row 47.6 + 910 * 1.22 / 51.5 = 69.2 of the window, 138 of the picture drawn at twice the size
        straight = app.draw(black, np.zeros(33), 50.0, None)
        self.assertEqual(straight.shape, (512, 1024, 3))
        self.assertEqual(tuple(straight[138, 512]), app.MODEL_COLOUR)  # straight lane: the bar is centred on the vanishing point
        self.assertEqual(tuple(straight[138, 300]), (0, 0, 0))
        bent = app.draw(black, np.interp(X_IDXS, (20, 100), (0, 8)), 50.0, None)  # lane 3 m to the LEFT at 50 m: 53 px left in the window
        self.assertEqual(tuple(bent[138, 406]), app.MODEL_COLOUR)
        self.assertEqual(tuple(bent[138, 512]), (0, 0, 0))
        self.assertEqual(tuple(app.draw(black, np.zeros(33), None, (50.0, 0.0))[138, 512]), app.RADAR_COLOUR)  # the radar's target

    def test_spread_picks_evenly_from_first_to_last(self):
        picked = app.spread(list(range(100)), 12)
        self.assertEqual((len(picked), picked[0], picked[-1], len(set(picked))), (12, 0, 99, 12))
        self.assertEqual(picked, sorted(picked))
        self.assertEqual(app.spread([3, 5], 12), [3, 5])
        self.assertEqual(app.spread([], 12), [])


if __name__ == "__main__":
    unittest.main()
