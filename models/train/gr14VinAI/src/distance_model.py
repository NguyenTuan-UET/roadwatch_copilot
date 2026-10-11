"""gr14VinAI: a camera-only network that estimates the distance to the vehicle ahead.

Two streams look at the same input, input_imgs [1,12,128,256] (previous and current frame, each as 6
half-resolution YUV420 planes of a 512x256 window centred on the road's vanishing point):

  Context stream   the whole window. Hierarchical ConvNeXt backbone:
                   stem (conv 3x3 s2, depthwise 3x3 s2, 1x1), then stages of 2-2-6-2 blocks at widths 64-128-256-512,
                   each block a depthwise 3x3 followed by a ConvNeXt residual (depthwise 7x7, 1x1 x3, GELU, 1x1),
                   depthwise 7x7 stride-2 downsampling, squeeze-excite tail, global average -> 1024 numbers.
  Fovea stream     only the 256x128 px around the vanishing point, where 99.8 % of the lead vehicles are, but at
                   full resolution: the 4 luma planes are woven back into full-resolution pixels (pixel shuffle).
                   It also receives two fixed maps from the pinhole camera model: for every pixel, how far ahead
                   and how far sideways the road point it shows lies. Same blocks, 2 stages (96, 192), output 16x32 cells.
  Fusion           the context vector rescales the fovea features (FiLM). A spatial attention map over the 16x32
                   cells picks where the lead is; the features there, and the attended position, go to the heads.
  Heads            has_target (probability), distance as a distribution over 64 log-spaced bins (its mean is the
                   answer), sideways offset (auxiliary, training only).

During training the attention map is taught where the radar says the vehicle is (see train_distance.py).
The entire architecture is custom-designed for this distance estimation task (dual-stream context + fovea,
camera-geometry maps, radar-guided attention, distribution head). The weights are trained from scratch
on this project's data.
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from common import CAM_H, FOCAL, MODEL_CX as VP_X, MODEL_CY as VP_Y

MAX_M = 100.0  # the task's distance range
BINS = torch.logspace(math.log10(5), math.log10(110), 64)  # distance bin centres in metres
FOVEA = (0, 64, 64, 192)  # rows, cols of the half-resolution planes that the fovea stream magnifies
CELL = 8  # one attention cell covers 8x8 full-resolution pixels of the fovea
LANE = 1.5  # a vehicle counts as "same lane" within this many metres of the lane's centre line
PATH_AT = (20.0, 40.0, 60.0, 80.0, 100.0)  # metres ahead at which the path head says where the lane is
PATH_UNIT = torch.tensor([8 * (d / 100) ** 2 for d in PATH_AT])  # metres per unit of its output: a bend grows with distance squared


def conv_bn(cin, cout, kernel, stride=1, groups=1, act=True):
    layers = [nn.Conv2d(cin, cout, kernel, stride, kernel // 2, groups=groups, bias=False), nn.BatchNorm2d(cout)]
    return nn.Sequential(*layers, nn.GELU()) if act else nn.Sequential(*layers)


class Block(nn.Module):
    """Depthwise 3x3, then a ConvNeXt residual: depthwise 7x7 -> 1x1 (x3 wider) -> GELU -> 1x1."""

    def __init__(self, c, drop_path=0.0):
        super().__init__()
        self.local = conv_bn(c, c, 3, groups=c, act=False)
        self.branch = nn.Sequential(conv_bn(c, c, 7, groups=c, act=False), conv_bn(c, 3 * c, 1), conv_bn(3 * c, c, 1, act=False))
        nn.init.zeros_(self.branch[-1][1].weight)  # every block starts as "local conv only", which keeps deep stacks trainable
        self.drop_path = drop_path

    def forward(self, x):
        x = self.local(x)
        y = self.branch(x)
        if self.training and self.drop_path:  # stochastic depth: skip the residual for a random part of the batch
            keep = torch.rand(len(x), 1, 1, 1, device=x.device) >= self.drop_path
            y = y * keep / (1 - self.drop_path)
        return x + y


def down(c):
    """Halve the resolution, double the channels: depthwise 7x7 stride 2, then 1x1."""
    return nn.Sequential(conv_bn(c, 2 * c, 7, 2, groups=c, act=False), conv_bn(2 * c, 2 * c, 1))


def stages(width, depths, drop_path):
    layers, n, total = [], 0, sum(depths)
    for i, depth in enumerate(depths):
        if i:
            layers.append(down(width))
            width *= 2
        for _ in range(depth):
            layers.append(Block(width, drop_path * n / max(total - 1, 1)))
            n += 1
    return nn.Sequential(*layers), width


class SqueezeExcite(nn.Module):
    def __init__(self, c, mid):
        super().__init__()
        self.fc = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Conv2d(c, mid, 1), nn.ReLU(), nn.Conv2d(mid, c, 1), nn.Sigmoid())

    def forward(self, x):
        return x * self.fc(x)


class ResidualFC(nn.Module):
    """x + FC(ReLU(FC(x))), the block the reference model builds its heads from."""

    def __init__(self, width):
        super().__init__()
        self.a, self.b = nn.Linear(width, width), nn.Linear(width, width)

    def forward(self, x):
        return F.relu(x + self.b(F.relu(self.a(x))))


def branch(cin, width, out):
    return nn.Sequential(nn.Linear(cin, width), nn.ReLU(), ResidualFC(width), nn.Linear(width, out))


def ground_maps():
    """For every fovea pixel, the road point it shows: metres ahead and metres to the side, from the pinhole model."""
    r0, r1, c0, c1 = FOVEA
    rows = torch.arange(2 * r0, 2 * r1).float()[:, None] + 0.5
    cols = torch.arange(2 * c0, 2 * c1).float()[None, :] + 0.5
    ahead = (FOCAL * CAM_H / (rows - VP_Y).clamp(min=1e-3)).clamp(max=MAX_M).expand(-1, cols.shape[1])  # sky counts as "far"
    side = ((cols - VP_X) * ahead / FOCAL).clamp(-10, 10)
    return torch.stack([ahead / MAX_M, side / 10])[None]


class Gr14VinAI(nn.Module):
    def __init__(self, drop_path=0.1, context=64, curve=False):
        super().__init__()
        body, c = stages(context, (2, 2, 6, 2), drop_path)
        self.context = nn.Sequential(conv_bn(12, context, 3, 2), conv_bn(context, context, 3, 2, groups=context), conv_bn(context, context, 1), body,
                                     conv_bn(c, 2 * c, 3, groups=c), SqueezeExcite(2 * c, 64), nn.AdaptiveAvgPool2d(1), nn.Flatten())
        eye, self.fovea_width = stages(96, (2, 4), drop_path)
        self.fovea = nn.Sequential(conv_bn(6, 48, 3, 2), conv_bn(48, 96, 3, 2), eye)
        self.register_buffer("ground", ground_maps(), persistent=False)
        self.register_buffer("bins", BINS.clone(), persistent=False)
        self.film = nn.Linear(2 * c, 2 * self.fovea_width)
        self.curve = curve  # also say where the lane goes, and judge "same lane" against that instead of the straight axis
        if curve:
            cells = F.avg_pool2d(ground_maps(), CELL)[0].flatten(1)  # per attention cell: metres ahead / MAX_M, metres to the right / 10
            knots = torch.tensor((0.0,) + PATH_AT)
            self.register_buffer("hat", (1 - (cells[0, :, None] * MAX_M - knots[None]).abs() / 20).clamp(min=0), persistent=False)
            self.register_buffer("cell_right", cells[1] * 10, persistent=False)
            self.register_buffer("path_unit", PATH_UNIT.clone(), persistent=False)
            self.path = branch(2 * c + self.fovea_width, 64, len(PATH_AT))
        self.where = nn.Conv2d(self.fovea_width + 2 * curve, 1, 1)
        self.scene = nn.Sequential(nn.Linear(2 * c, 256), nn.ReLU())
        self.trunk = nn.Sequential(nn.Dropout(0.2), nn.Linear(self.fovea_width + 256 + 2 + 2 * curve, 512), nn.ReLU(), ResidualFC(512))
        self.has_target, self.distance, self.sideways = branch(512, 16, 1), branch(512, 128, len(BINS)), branch(512, 16, 1)

    def fovea_input(self, x):
        """Full-resolution luma of both frames, colour of the current one, and the two ground maps: [B,6,128,256]."""
        r0, r1, c0, c1 = FOVEA
        w = x[:, :, r0:r1, c0:c1]
        weave = lambda planes: F.pixel_shuffle(planes[:, [0, 2, 1, 3]], 2)  # planes are stored column-phase first
        colour = F.interpolate(w[:, 10:12], scale_factor=2.0, mode="nearest")
        return torch.cat([weave(w[:, 0:4]), weave(w[:, 6:10]), colour, self.ground.expand(len(x), -1, -1, -1)], 1)

    def forward(self, x):
        """x: [B,12,128,256] raw 0..255 YUV planes. Returns (has_target logit, distance / MAX_M, training extras)."""
        x = x / 127.5 - 1
        scene = self.context(x)
        feat = self.fovea(self.fovea_input(x))
        scale, shift = self.film(scene).chunk(2, 1)
        feat = feat * (1 + scale[:, :, None, None]) + shift[:, :, None, None]
        b, _, h, w = feat.shape
        extra, near = {}, []
        if self.curve:
            extra["path"] = self.path(torch.cat([scene, feat.mean((2, 3))], 1))  # the lane at PATH_AT, metres to the left / PATH_UNIT
            lane = F.pad(extra["path"].float() * self.path_unit, (1, 0)) @ self.hat.T  # ... at the distance every cell shows
            off = ((self.cell_right + lane) / LANE).clamp(-4, 4)  # each cell's road point: how many corridor half-widths from the lane centre
            hint = torch.stack([off, torch.exp(-off ** 2)], 1)
            feat_where = torch.cat([feat, hint.view(b, 2, h, w).to(feat.dtype)], 1)
        where = self.where(feat_where if self.curve else feat).flatten(1)  # one logit per 8x8 px cell: where is the lead?
        attention = where.softmax(1)
        if self.curve:
            near = [(attention[:, None].float() * hint).sum(2).to(feat.dtype)]  # where the attended spot lies relative to the lane
        picked = (feat.flatten(2) * attention[:, None]).sum(2)
        rows = torch.arange(h, device=x.device).float().repeat_interleave(w)
        cols = torch.arange(w, device=x.device).float().repeat(h)
        position = torch.stack([(attention * rows).sum(1) / h, (attention * cols).sum(1) / w], 1) * 2 - 1
        z = self.trunk(torch.cat([picked, self.scene(scene), position, *near], 1))
        bins = self.distance(z)
        metres = (bins.softmax(1) * self.bins).sum(1, keepdim=True)
        return self.has_target(z), metres / MAX_M, {"bins": bins, "where": where, "sideways": self.sideways(z), **extra}


MIRROR = [2, 3, 0, 1, 4, 5, 8, 9, 6, 7, 10, 11]  # in a mirrored image the Y planes of even and odd columns trade places


class Mirrored(nn.Module):
    """The network's answer averaged over the image and its mirror image. Measured on validation: more accurate than one
    look, at twice the computation. This is how the trained network is evaluated and exported."""

    def __init__(self, net):
        super().__init__()
        self.net = net

    def forward(self, x):
        logit, d, extra = self.net(torch.cat([x, x.flip(-1)[:, MIRROR]]))
        if "path" in extra:  # in the mirror image the lane bends the other way
            extra = {**extra, "path": (extra["path"][:len(x)] - extra["path"][len(x):]) / 2}
        return logit.view(2, -1, 1).mean(0), d.view(2, -1, 1).mean(0), extra


class Deploy(nn.Module):
    """What the .onnx computes: probability that a target exists, its distance in metres within [0, MAX_M], and for a
    network with a path head how many metres to the left of the straight axis the lane lies at PATH_AT."""

    def __init__(self, net):
        super().__init__()
        self.net = net

    def forward(self, input_imgs):
        logit, d, extra = self.net(input_imgs)
        out = torch.sigmoid(logit), (d * MAX_M).clamp(0, MAX_M)
        return (*out, extra["path"] * PATH_UNIT.to(d.device)) if "path" in extra else out
