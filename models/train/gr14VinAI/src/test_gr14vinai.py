import unittest

import torch

import train_distance as g


class Gr14VinAITests(unittest.TestCase):
    def test_outputs_are_a_probability_and_a_distance_within_range(self):
        torch.manual_seed(0)
        model = g.Deploy(g.Gr14VinAI()).eval()
        for scale in (0, 255, 1e6):  # even absurd inputs must not produce an out-of-range answer
            prob, dist = model(torch.rand(3, 12, 128, 256) * scale)
            self.assertEqual((tuple(prob.shape), tuple(dist.shape)), ((3, 1), (3, 1)))
            self.assertTrue(((prob >= 0) & (prob <= 1)).all())
            self.assertTrue(((dist >= 0) & (dist <= g.MAX_M)).all())

    def test_mirror_matches_flipping_the_full_resolution_image(self):
        luma = torch.rand(256, 512)
        planes = lambda y: torch.stack([y[0::2, 0::2], y[1::2, 0::2], y[0::2, 1::2], y[1::2, 1::2]])
        self.assertTrue(torch.equal(planes(luma.flip(-1)), planes(luma).flip(-1)[g.MIRROR[:4]]))

    def test_augment_keeps_shape_and_pixel_range(self):
        x = torch.rand(8, 12, 128, 256) * 255
        out, (flip, right, down, zoom) = g.augment(x)
        self.assertEqual(out.shape, x.shape)
        self.assertTrue(((out >= 0) & (out <= 255)).all())

    def test_distance_loss_ignores_frames_without_target(self):
        logit, d = torch.zeros(2, 1), torch.tensor([[0.5], [0.9]])
        labels = g.hard(torch.tensor([[1.0, 50.0], [0.0, 0.0]]))
        with_garbage = g.criterion(logit, d, labels)
        d[1] = -7.0  # prediction on the no-target frame must not matter
        self.assertEqual(with_garbage, g.criterion(logit, d, labels))

    def test_magnify_moves_pixels_away_from_the_vanishing_point(self):
        x = torch.rand(2, 12, 128, 256) * 255
        self.assertTrue(torch.allclose(g.magnify(x, torch.ones(2)), x, atol=0.1))  # factor 1 changes nothing
        full = torch.zeros(1, 1, 256, 512)
        full[0, 0, 88:92, 300:304] = 255  # a bright square about 42 px below and 46 px right of the vanishing point (256, 47.6)
        planes = torch.nn.functional.pixel_unshuffle(full, 2)[:, [0, 2, 1, 3]]
        out = g.magnify(torch.cat([planes, torch.zeros(1, 2, 128, 256)] * 2, 1), torch.tensor([2.0]))
        big = torch.nn.functional.pixel_shuffle(out[:, [0, 2, 1, 3]], 2)[0, 0]
        rows, cols = torch.nonzero(big > 128, as_tuple=True)
        self.assertAlmostEqual(rows.float().mean().item() + 0.5, 47.6 + 2 * (90 - 47.6), delta=1)  # twice as far from it
        self.assertAlmostEqual(cols.float().mean().item() + 0.5, 256 + 2 * (302 - 256), delta=1)

    def test_lead_softens_the_label_at_the_limits_and_follows_magnification(self):
        slots = lambda *objects: torch.tensor([[0.0] + [v for o in objects for v in o] + [0.0] * (2 * (g.SLOTS - len(objects)))])
        _, soft, seen, dist, side = g.lead(slots((60.0, 0.2)))
        self.assertGreater(soft.item(), 0.99)
        self.assertEqual((seen.item(), dist.item()), (True, 60.0))
        self.assertAlmostEqual(g.lead(slots((100.0, 0.0)))[1].item(), 0.5, places=3)  # exactly on the range limit: a coin flip
        _, soft, seen, dist, side = g.lead(slots((40.0, 2.0), (120.0, -0.5)))  # nobody in the box
        self.assertLess(soft.item(), 0.05)
        self.assertEqual((seen.item(), dist.item()), (True, 40.0))  # the one beside the lane is nearer to being a target
        _, soft, seen, dist, side = g.lead(slots((40.0, 2.0), (120.0, -0.5)), zoom=torch.tensor([[1.25]]))
        self.assertGreater(soft.item(), 0.7)  # magnified 1.25x the far car is at 96 m, inside the box
        self.assertAlmostEqual(dist.item(), 96.0, places=3)
        self.assertEqual(g.lead(slots())[2].item(), False)  # empty road: nothing to describe

    def test_dataset_label_follows_magnification(self):
        y = torch.tensor([[1.0, 90.0, 0.5], [0.0, 0.0, 0.0]])
        radar = torch.zeros(2, 1 + 2 * g.SLOTS)
        radar[1, 1:3] = torch.tensor([120.0, -0.4])
        _, _, seen, dist, side = g.hard(y, radar, torch.tensor([0.8, 1.25]))
        self.assertEqual(seen.tolist(), [False, True])  # 90 m shown at 112 m is out of range; 120 m shown at 96 m is in
        self.assertAlmostEqual(dist[1].item(), 96.0, places=3)
        self.assertEqual((dist[0].item(), round(side[1].item(), 3)), (0.0, -0.4))
        self.assertEqual(g.hard(y)[2].tolist(), [True, False])  # as filmed: the label as the dataset gives it

    def test_curved_labels_follow_the_lane_and_the_magnification(self):
        path = torch.arange(1, 14).float()[None] * 0.5  # the lane is 0.5 m to the left at 10 m, 1 m at 20 m, ... 6.5 m at 130 m
        self.assertTrue(torch.allclose(g.lane_at(path, torch.tensor([[0.0, 5.0, 20.0, 125.0]])), torch.tensor([[0.0, 0.25, 1.0, 6.25]])))
        y = torch.zeros(1, 3 + 13 + 3 * g.SLOTS)
        y[0, 3:16] = path
        y[0, 16:19] = torch.tensor([120.0, 6.4, 0.4])  # a moving vehicle 120 m ahead, 6.4 m left of the axis but only 0.4 m off the lane
        self.assertEqual(g.curved(y, torch.tensor([1.0]))[2].item(), False)  # beyond 100 m as filmed
        _, _, seen, dist, side = g.curved(y, torch.tensor([1.25]))
        self.assertEqual((seen.item(), round(dist.item(), 3), round(side.item(), 3)), (True, 96.0, 6.4))  # magnified it is in range, and in lane
        moved = (torch.tensor([False]), 0, 0)
        target = torch.tensor([[1.0, 2.0, 3.0, 4.0, 5.0]]) / g.PATH_UNIT  # exactly the lane at 20..100 m
        self.assertLess(g.path_loss(target, y, moved, torch.tensor([1.0])).item(), 1e-6)
        self.assertGreater(g.path_loss(-target, y, moved, torch.tensor([1.0])).item(), 0.1)
        self.assertLess(g.path_loss(-target, y, (torch.tensor([True]), 0, 0), torch.tensor([1.0])).item(), 1e-6)  # mirrored: the bend flips

    def test_soft_curved_labels_are_soft_only_at_the_limits(self):
        def frame(target, *moving, lane=0.0):  # target (metres ahead, yRel) or None; moving objects (metres ahead, yRel); the lane lies `lane` m to the left
            y = torch.zeros(1, 3 + 13 + 3 * g.SLOTS)
            y[0, 3:16] = lane
            if target:
                y[0, :3] = torch.tensor([1.0, *target])
            for i, (d, side) in enumerate(moving):
                y[0, 16 + 3 * i:19 + 3 * i] = torch.tensor([d, side, side - lane])
            return y
        one = torch.tensor([1.0])
        unusable, soft, seen, dist, side = g.curved_soft(frame((60.0, 4.2), (60.0, 4.2), lane=4.0), one)  # on a bend, 0.2 m from the lane centre
        self.assertEqual((unusable.item(), seen.item(), dist.item(), round(side.item(), 3)), (False, True, 60.0, 4.2))
        self.assertGreater(soft.item(), 0.99)  # well inside: as the hard label
        unusable, soft, seen, dist, _ = g.curved_soft(frame((30.0, 0.3), (60.0, 0.0)), one)  # the target stands still, a vehicle drives behind it
        self.assertEqual((unusable.item(), seen.item(), dist.item()), (False, True, 30.0))  # the label's target stays the answer
        self.assertGreater(soft.item(), 0.99)
        self.assertAlmostEqual(g.curved_soft(frame((100.0, 0.0)), one)[1].item(), 0.5, places=3)  # on the 100 m limit
        self.assertAlmostEqual(g.curved_soft(frame((60.0, 1.5)), one)[1].item(), 0.5, places=3)  # on the lane edge
        _, soft, seen, dist, _ = g.curved_soft(frame(None, (60.0, 2.5)), one)
        self.assertLess(soft.item(), 0.01)  # a vehicle a metre outside the lane: no target, but still described
        self.assertEqual((seen.item(), dist.item()), (True, 60.0))
        _, soft, seen, dist, _ = g.curved_soft(frame(None, (120.0, 0.0)), torch.tensor([1.25]))
        self.assertGreater(soft.item(), 0.7)  # magnified 1.25x the vehicle at 120 m is at 96 m
        self.assertAlmostEqual(dist.item(), 96.0, places=3)
        _, soft, seen, dist, _ = g.curved_soft(frame((90.0, 0.0)), torch.tensor([0.8]))
        self.assertLess(soft.item(), 0.05)  # shrunk to 0.8x the target at 90 m is at 112.5 m: beyond the limit, still described
        self.assertEqual((seen.item(), round(dist.item(), 3)), (True, 112.5))
        self.assertEqual([t.item() for t in g.curved_soft(frame(None), one)[:3]], [False, 0.0, False])  # empty road
        y = torch.cat([frame((60.0, 4.2), (60.0, 4.2), lane=4.0), frame(None, (40.0, 3.0)), frame(None), frame((30.0, 0.3), (60.0, 0.0))])
        zoom = torch.ones(len(y))
        for a, b in zip(g.curved_soft(y, zoom)[1:], g.curved(y, zoom)[1:]):  # away from the limits: the labels of `curve`
            self.assertTrue(torch.allclose(a.float(), b.float(), atol=1e-3), (a, b))

    def test_balance_gives_a_rare_group_a_bigger_share(self):
        import numpy as np
        meta = np.zeros((105, 2), np.float32)
        meta[:100] = 1, 70.0  # 100 day frames with a vehicle at 70 m
        meta[100:104] = 1, 10.0  # 4 at 10 m
        meta[104, 0] = -1  # unusable: never drawn
        w, group = g.balance_weights(meta, np.zeros(105, bool))
        self.assertAlmostEqual(w[:100].sum() / w[100:104].sum(), 5.0, places=5)  # sqrt(100) : sqrt(4) instead of 100 : 4
        self.assertEqual((w[104], group[0], group[100]), (0.0, 4, 1))
        self.assertGreater(g.balance_weights(meta, np.arange(105) < 10)[0][0], w[10])  # the same kind of frame is rarer at night

    def test_path_head_tells_cells_how_far_they_are_from_the_lane(self):
        net = g.Gr14VinAI(curve=True).eval()
        self.assertTrue(torch.allclose(net.hat.sum(1), torch.ones(len(net.hat)), atol=1e-5))  # interpolation weights of every cell
        logit, d, extra = net(torch.rand(2, 12, 128, 256) * 255)
        self.assertEqual(tuple(extra["path"].shape), (2, len(g.PATH_AT)))
        prob, dist, lane = g.Deploy(g.Mirrored(net)).eval()(torch.rand(1, 12, 128, 256) * 255)
        self.assertEqual(tuple(lane.shape), (1, len(g.PATH_AT)))


if __name__ == "__main__":
    unittest.main()
