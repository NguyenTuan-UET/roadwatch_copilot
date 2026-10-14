import test from "node:test";
import assert from "node:assert/strict";
import { close } from "./golden.mjs";
import { arange, interp, linspace, median, polyder, polyfit, polyval } from "../../../src/roadwatch/ui/onphone/num.mjs";

test("interp holds the end values outside the range, as np.interp", () => {
  assert.deepEqual([-1, 0, 0.5, 2, 3].map((x) => interp(x, [0, 1, 2], [10, 20, 40])), [10, 10, 15, 40, 40]);
});

test("linspace and arange as numpy", () => {
  assert.deepEqual(linspace(2, 4, 5), [2, 2.5, 3, 3.5, 4]);
  assert.deepEqual(arange(2, 5.5, 1), [2, 3, 4, 5]);
});

test("polyfit recovers a cubic on 2..80 (highest power first), polyval and polyder evaluate it", () => {
  const xs = arange(2, 80.5, 1), c = [2e-5, -3e-3, 0.05, 1.7];
  const ys = xs.map((x) => polyval(c, x));
  close(polyfit(xs, ys, 3), c, { atol: 1e-12, rtol: 1e-8 }, "coefficients");
  close(polyval(polyder(c), 10), 3 * 2e-5 * 100 - 2 * 3e-3 * 10 + 0.05, { atol: 1e-15 }, "derivative");
  const noisy = ys.map((y, i) => y + (i % 2 ? 0.01 : -0.01));   // least squares: the fit goes between
  // numpy.polyfit on the same points
  close(polyfit(xs, noisy, 1), [-0.07642399999999996, 2.9378774177215177], { atol: 1e-12, rtol: 1e-10 }, "line");
  close(polyfit(xs, noisy, 3), [1.9999999999999968e-05, -0.0030006088613683444, 0.05004992663220461, 1.6991665296728642],
        { atol: 1e-12, rtol: 1e-9 }, "cubic");
  assert.equal(polyfit([1, 2], [3, 5], 1).length, 2);
});

test("median of each element across arrays, as np.median(axis=0)", () => {
  assert.deepEqual(median([[1, 5], [3, 2], [2, 9]]), [2, 5]);
  assert.deepEqual(median([[1, 4], [3, 2]]), [2, 3]);
  assert.equal(median([7, 1, 3]), 3);
});
