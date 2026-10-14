"""Compare a video run on the phone's GPU (/phone, "Video có sẵn") with the same video run in Lai thu.

    python -m scripts.roadwatch.compare_phone_clip PHONE_JSON RUN_DIR [--fy 962]

PHONE_JSON: runs/<dir>/phone_clips/<id>.json (written by /api/phone/clip-result); RUN_DIR: the Lai thu run of the same
file (runs/<dir>/<run_id>/, with lead_distance.csv, run.json and input.*). The phone's rows are on the video's own clock,
the laptop's on frame / 20: the laptop clock is scaled so the two ends meet. Reports, for the ticks the phone has:
the lead distance (both have one: median / p90 |difference|; who has a lead when), the model's speed, and the lane
border's jitter 15 m ahead (accel_rms, m/s^2) against the laptop pipeline run on the run's own input at the phone's rate.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .lane_jitter_ref import jitter, reference


def load_laptop(run_dir):
    rows = list(csv.DictReader(open(run_dir / 'lead_distance.csv')))
    f = lambda r, k: float(r[k])  # noqa: E731
    return (np.array([f(r, 'time_s') for r in rows]), np.array([f(r, 'lead_dist_bumper_m') for r in rows]),
            np.array([f(r, 'ego_speed_model_mps') * 3.6 for r in rows]), np.array([f(r, 'calib_settled') for r in rows]) > 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('phone', type=Path)
    ap.add_argument('run_dir', type=Path)
    ap.add_argument('--fy', type=float, default=962.0)
    a = ap.parse_args()
    ph, meta = json.loads(a.phone.read_text()), json.loads((a.run_dir / 'run.json').read_text())
    rows = [r for r in ph['rows'] if r['status'] == 'calibrated']
    lt, lgap, lspeed, lsettled = load_laptop(a.run_dir)
    duration = ph.get('duration') or ph['rows'][-1]['t']   # older results: the last tick
    scale = duration / (meta['frames'] / meta['fps'])   # laptop time_s -> video time
    lt = lt * scale
    pt = np.array([r['t'] for r in rows])
    idx = np.clip(np.searchsorted(lt, pt), 1, len(lt) - 1)
    idx = np.where(np.abs(lt[idx - 1] - pt) < np.abs(lt[idx] - pt), idx - 1, idx)   # nearest laptop tick
    pg = np.array([np.nan if r['gap'] is None else r['gap'] for r in rows])
    lg, lsp, ok = lgap[idx], lspeed[idx], lsettled[idx]
    pg, pv = pg[ok], np.array([r['model_kmh'] for r in rows])[ok]
    lg, lsp = lg[ok], lsp[ok]
    both = ~np.isnan(pg) & ~np.isnan(lg)
    print(f'video {ph["video"]}, {duration:.1f} s; phone {len(ph["rows"])} ticks (calibrated and matched: {ok.sum()}), '
          f'laptop {len(lt)} ticks, clock scale {scale:.3f}')
    print(f'lead: both {both.mean() * 100:.0f} %, only phone {(~np.isnan(pg) & np.isnan(lg)).mean() * 100:.0f} %, '
          f'only laptop {(np.isnan(pg) & ~np.isnan(lg)).mean() * 100:.0f} %, neither {(np.isnan(pg) & np.isnan(lg)).mean() * 100:.0f} %')
    if both.any():
        d = np.abs(pg[both] - lg[both])
        print(f'lead distance, where both have one: median |diff| {np.median(d):.2f} m, p90 {np.percentile(d, 90):.2f} m '
              f'({both.sum()} ticks); phone median {np.median(pg[both]):.1f} m, laptop {np.median(lg[both]):.1f} m')
    print(f'model speed km/h: phone median {np.median(pv):.1f}, laptop {np.median(lsp):.1f}, median |diff| {np.median(np.abs(pv - lsp)):.1f}')
    t = [r['t'] for r in rows]
    hz = round(len(rows) / (t[-1] - t[0])) if len(rows) > 2 else 10
    pl, pr = jitter(t, [r['yl15'] for r in rows]), jitter(t, [r['yr15'] for r in rows])
    inp = next(a.run_dir.glob('input.*'))
    ref = reference(inp, meta['crop'], meta['size'], min(20, max(1, hz)), fy=a.fy, d_cam=meta['d_cam_bumper_m'])
    rt = np.array(ref['t']) * scale   # the laptop run's clock (frame / 20) in video time, so both are per real second
    ll, lr = jitter(rt, ref['yl']), jitter(rt, ref['yr'])
    print(f'lane border @15 m, accel_rms (m/s^2, per real second): phone L {pl[0]:.2f} R {pr[0]:.2f} at about {hz} Hz; '
          f'laptop at about {ref["hz"] / scale:.0f} Hz L {ll[0]:.2f} R {lr[0]:.2f}')
    pc = {}
    for r in rows:
        pc[r['lane_ref']] = pc.get(r['lane_ref'], 0) + 1
    print(f'lane centre from: phone {pc}, laptop {ref["refs"]}')


if __name__ == '__main__':
    main()
