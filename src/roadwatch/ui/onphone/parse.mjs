/* Vector đầu ra (707 số) của gr14VinAI -> các đầu ra đã đọc, bản JS của Parser (vendor/.../parse_model_outputs.py)
   cho đúng các đầu ra của model đã tỉa (bảng output_slices trong metadata):
   pose 0..12, road_transform 12..24, lane_lines 24..552, lane_lines_prob 552..560, lead 560..704, lead_prob 704..707.
   MDN không nhiều giả thuyết: nửa đầu là trung bình, nửa sau là log độ lệch (safe_exp: exp(min(x, 11))).
   lead có 144 = 2 x (3 x 6 x 4) số nên không phải dạng nhiều giả thuyết (is_mhp sai). Mảng trả về không có chiều batch:
   Python p['lead'][0] tương ứng JS p.lead. */
export const SLICES = { pose: [0, 12], road_transform: [12, 24], lane_lines: [24, 552], lane_lines_prob: [552, 560],
                        lead: [560, 704], lead_prob: [704, 707] };

const safeExp = (x) => Math.exp(Math.min(x, 11));
const sigmoid = (x) => 1 / (1 + safeExp(-x));

function reshape(flat, shape) {   // mảng phẳng -> mảng lồng theo shape
  if (shape.length === 1) return Array.from(flat);
  const step = flat.length / shape[0], out = [];
  for (let i = 0; i < shape[0]; i++) out.push(reshape(flat.slice(i * step, (i + 1) * step), shape.slice(1)));
  return out;
}

function mdn(raw, shape) {
  const n = raw.length / 2;
  return [reshape(raw.slice(0, n), shape), reshape(Array.from(raw.slice(n, 2 * n), safeExp), shape)];
}

/** raw: Float32Array/Array 707 số -> {pose, pose_stds, road_transform, ..., lead [3][6][4], lead_stds, lead_prob [3]}. */
export function parseOutputs(raw) {
  const part = (k) => Array.from(raw.slice(SLICES[k][0], SLICES[k][1]));
  const out = {};
  [out.pose, out.pose_stds] = mdn(part("pose"), [6]);
  [out.road_transform, out.road_transform_stds] = mdn(part("road_transform"), [6]);
  [out.lane_lines, out.lane_lines_stds] = mdn(part("lane_lines"), [4, 33, 2]);
  out.lane_lines_prob = part("lane_lines_prob").map(sigmoid);
  [out.lead, out.lead_stds] = mdn(part("lead"), [3, 6, 4]);
  out.lead_prob = part("lead_prob").map(sigmoid);
  return out;
}
