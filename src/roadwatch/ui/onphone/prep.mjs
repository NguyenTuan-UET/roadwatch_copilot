/* Ảnh camera -> đầu vào model gr14VinAI, bản JS (CPU) của model.frame_to_model_input / pack_frame:
   nắn phối cảnh các mặt phẳng Y (512x256) và U, V (256x128) bằng nội suy song tuyến (cv2.INTER_LINEAR với
   WARP_INVERSE_MAP; điểm ngoài ảnh là 0 như cv2.BORDER_CONSTANT), rồi xếp 6 kênh
   Y[0::2,0::2], Y[1::2,0::2], Y[0::2,1::2], Y[1::2,1::2], U, V. cv2 dùng số cố định 5 bit cho toạ độ nên kết quả lệch
   tối đa vài mức xám so với bản này; kiểm ở tests/roadwatch/js/prep.test.mjs.
   rgbaToI420: RGB -> YUV 4:2:0 như cv2.COLOR_RGB2YUV_I420 (đo 13/10/2026: BT.601 dải hẹp, U, V lấy điểm trên-trái
   của mỗi ô 2x2), là cách đường gửi ảnh JPEG cũ đưa ảnh vào model. */
import { MODEL_H, MODEL_W } from "./geometry.mjs";

/** Ảnh RGBA (Uint8ClampedArray w*h*4) -> {y, u, v} mặt phẳng Uint8Array; w, h chẵn. */
export function rgbaToI420(rgba, w, h) {
  const y = new Uint8Array(w * h), u = new Uint8Array((w >> 1) * (h >> 1)), v = new Uint8Array(u.length);
  for (let j = 0, p = 0, q = 0; j < h; j++) {
    for (let i = 0; i < w; i++, p += 4, q++) {
      const R = rgba[p], G = rgba[p + 1], B = rgba[p + 2];
      y[q] = Math.round(16 + 0.257 * R + 0.504 * G + 0.098 * B);
      if (!(j & 1) && !(i & 1)) {
        const c = (j >> 1) * (w >> 1) + (i >> 1);
        u[c] = Math.min(255, Math.max(0, Math.round(128 - 0.148 * R - 0.291 * G + 0.439 * B)));
        v[c] = Math.min(255, Math.max(0, Math.round(128 + 0.439 * R - 0.368 * G - 0.071 * B)));
      }
    }
  }
  return { y, u, v };
}

/** Nắn một mặt phẳng: out[r][c] = src(M @ [c, r, 1]) song tuyến; ngoài ảnh = 0. */
function warpPlane(src, sw, sh, m, ow, oh, out, outOffset, stride, pick) {
  const [[a, b, c], [d, e, f], [g, hh, k]] = m;
  for (let r = 0; r < oh; r++) {
    for (let col = 0; col < ow; col++) {
      const z = g * col + hh * r + k;
      let val = 0;
      if (z > 0) {
        const x = (a * col + b * r + c) / z, y = (d * col + e * r + f) / z;
        const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
        if (x0 >= -1 && y0 >= -1 && x0 < sw && y0 < sh) {
          const at = (xx, yy) => (xx >= 0 && yy >= 0 && xx < sw && yy < sh ? src[yy * sw + xx] : 0);
          val = (at(x0, y0) * (1 - fx) + at(x0 + 1, y0) * fx) * (1 - fy) + (at(x0, y0 + 1) * (1 - fx) + at(x0 + 1, y0 + 1) * fx) * fy;
        }
      }
      if (pick) pick(r, col, val);
      else out[outOffset + r * stride + col] = Math.round(val);
    }
  }
}

/** Một khung -> Uint8Array 6*128*256 (thứ tự kênh như Python) với ma trận nắn m (điểm khung model -> điểm camera). */
export function frameToModelInput({ y, u, v }, w, h, m, out = new Uint8Array(6 * 128 * 256), offset = 0) {
  const H2 = MODEL_H >> 1, W2 = MODEL_W >> 1, plane = H2 * W2;
  warpPlane(y, w, h, m, MODEL_W, MODEL_H, null, 0, 0, (r, col, val) => {   // Y -> 4 kênh xen kẽ
    const ch = (r & 1) + 2 * (col & 1);   // [0::2,0::2]=0, [1::2,0::2]=1, [0::2,1::2]=2, [1::2,1::2]=3
    out[offset + ch * plane + (r >> 1) * W2 + (col >> 1)] = Math.round(val);
  });
  const muv = [[m[0][0], m[0][1], m[0][2] / 2], [m[1][0], m[1][1], m[1][2] / 2], [m[2][0] * 2, m[2][1] * 2, m[2][2]]];
  warpPlane(u, w >> 1, h >> 1, muv, W2, H2, out, offset + 4 * plane, W2);
  warpPlane(v, w >> 1, h >> 1, muv, W2, H2, out, offset + 5 * plane, W2);
  return out;
}

/** pack_frame: [narrow, wide] -> Uint8Array 2*6*128*256; wide null = nhân đôi ảnh hẹp. */
export function packFrame(planes, w, h, warps) {
  const one = 6 * 128 * 256, out = new Uint8Array(2 * one);
  frameToModelInput(planes, w, h, warps[0], out, 0);
  if (warps[1]) frameToModelInput(planes, w, h, warps[1], out, one);
  else out.copyWithin(one, 0, one);
  return out;
}

/* Nắn thẳng từ RGBA (ảnh camera trên trình duyệt), không đổi cả ảnh sang YUV trước: chỉ tính màu ở các điểm model cần.
   Kết quả như rgbaToI420 + packFrame (lệch tối đa 1 mức do làm tròn; kiểm ở prep.test.mjs):
   Y: nội suy song tuyến Y của 4 điểm lân cận; U, V: lưới màu là các điểm trên-trái của ô 2x2 (toạ độ chẵn). */
const yOf = (d, i) => Math.round(16 + 0.257 * d[i] + 0.504 * d[i + 1] + 0.098 * d[i + 2]);
const clamp8 = (x) => (x < 0 ? 0 : x > 255 ? 255 : Math.round(x));
const uOf = (d, i) => clamp8(128 - 0.148 * d[i] - 0.291 * d[i + 1] + 0.439 * d[i + 2]);
const vOf = (d, i) => clamp8(128 + 0.439 * d[i] - 0.368 * d[i + 1] - 0.071 * d[i + 2]);

function warpRGBA(rgba, w, h, m, out, offset) {
  const plane = 128 * 256, [[a, b, c], [d, e, f], [g, hh, k]] = m;
  for (let r = 0; r < MODEL_H; r++) {   // Y, xếp thẳng vào 4 kênh xen kẽ
    for (let col = 0; col < MODEL_W; col++) {
      const z = g * col + hh * r + k;
      let val = 0;
      if (z > 0) {
        const x = (a * col + b * r + c) / z, y = (d * col + e * r + f) / z, x0 = Math.floor(x), y0 = Math.floor(y);
        if (x0 >= -1 && y0 >= -1 && x0 < w && y0 < h) {
          const fx = x - x0, fy = y - y0, inX0 = x0 >= 0, inX1 = x0 + 1 < w, inY0 = y0 >= 0, inY1 = y0 + 1 < h;
          const p00 = inX0 && inY0 ? yOf(rgba, 4 * (y0 * w + x0)) : 0, p10 = inX1 && inY0 ? yOf(rgba, 4 * (y0 * w + x0 + 1)) : 0;
          const p01 = inX0 && inY1 ? yOf(rgba, 4 * ((y0 + 1) * w + x0)) : 0, p11 = inX1 && inY1 ? yOf(rgba, 4 * ((y0 + 1) * w + x0 + 1)) : 0;
          val = (p00 * (1 - fx) + p10 * fx) * (1 - fy) + (p01 * (1 - fx) + p11 * fx) * fy;
        }
      }
      out[offset + ((r & 1) + 2 * (col & 1)) * plane + (r >> 1) * 256 + (col >> 1)] = Math.round(val);
    }
  }
  // U, V trên lưới màu nửa độ phân giải. Không tạo hàm trong vòng lặp: trên iPhone bản có hàm lồng mất ~50 ms/khung
  const cw = w >> 1, chh = h >> 1, uOff = offset + 4 * plane, vOff = offset + 5 * plane;
  for (let r = 0; r < MODEL_H >> 1; r++) {
    for (let col = 0; col < MODEL_W >> 1; col++) {
      const z = 2 * g * col + 2 * hh * r + k;
      let uv = 0, vv = 0;
      if (z > 0) {
        const x = (a * col + b * r + c / 2) / z, y = (d * col + e * r + f / 2) / z, x0 = Math.floor(x), y0 = Math.floor(y);
        if (x0 >= -1 && y0 >= -1 && x0 < cw && y0 < chh) {
          const fx = x - x0, fy = y - y0, x1 = x0 + 1, y1 = y0 + 1;
          const okx0 = x0 >= 0, okx1 = x1 < cw, oky0 = y0 >= 0, oky1 = y1 < chh;
          // điểm màu (xx, yy) = điểm ảnh (2xx, 2yy) của RGBA
          const i00 = okx0 && oky0 ? 8 * (y0 * w + x0) : -1, i10 = okx1 && oky0 ? 8 * (y0 * w + x1) : -1;
          const i01 = okx0 && oky1 ? 8 * (y1 * w + x0) : -1, i11 = okx1 && oky1 ? 8 * (y1 * w + x1) : -1;
          const u00 = i00 < 0 ? 0 : uOf(rgba, i00), u10 = i10 < 0 ? 0 : uOf(rgba, i10), u01 = i01 < 0 ? 0 : uOf(rgba, i01), u11 = i11 < 0 ? 0 : uOf(rgba, i11);
          const v00 = i00 < 0 ? 0 : vOf(rgba, i00), v10 = i10 < 0 ? 0 : vOf(rgba, i10), v01 = i01 < 0 ? 0 : vOf(rgba, i01), v11 = i11 < 0 ? 0 : vOf(rgba, i11);
          uv = (u00 * (1 - fx) + u10 * fx) * (1 - fy) + (u01 * (1 - fx) + u11 * fx) * fy;
          vv = (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy;
        }
      }
      out[uOff + r * 256 + col] = Math.round(uv);
      out[vOff + r * 256 + col] = Math.round(vv);
    }
  }
}

/** Như packFrame nhưng từ ảnh RGBA (Uint8ClampedArray w*h*4). */
export function prepFromRGBA(rgba, w, h, warps, out = new Uint8Array(2 * 6 * 128 * 256)) {
  const one = 6 * 128 * 256;
  warpRGBA(rgba, w, h, warps[0], out, 0);
  if (warps[1]) warpRGBA(rgba, w, h, warps[1], out, one);
  else out.copyWithin(one, 0, one);
  return out;
}

/* Chỉ đọc vùng ảnh model lấy mẫu (trên iPhone, đọc cả ảnh 1280x960 mỗi khung tốn ~5 MB bộ nhớ tạm, 13/10/2026).
   Phép nắn phối cảnh biến khung model chữ nhật thành tứ giác, nên vùng cần đọc là hình chữ nhật bao 4 góc (+1 điểm
   cho nội suy song tuyến; U, V ở toạ độ chẵn nên làm tròn ra số chẵn). */
export function sampleRect(warps, w, h) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const m of warps) {
    if (!m) continue;
    for (const [c, r] of [[0, 0], [MODEL_W - 1, 0], [0, MODEL_H - 1], [MODEL_W - 1, MODEL_H - 1]]) {
      const z = m[2][0] * c + m[2][1] * r + m[2][2];
      if (!(z > 0)) return [0, 0, w, h];   // khung model chạm sau camera: đọc cả ảnh
      const x = (m[0][0] * c + m[0][1] * r + m[0][2]) / z, y = (m[1][0] * c + m[1][1] * r + m[1][2]) / z;
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
    }
  }
  const ax = Math.max(0, (Math.floor(x0) - 2) & ~1), ay = Math.max(0, (Math.floor(y0) - 2) & ~1);
  const bx = Math.min(w, (Math.ceil(x1) + 4) & ~1), by = Math.min(h, (Math.ceil(y1) + 4) & ~1);
  return bx > ax && by > ay ? [ax, ay, bx - ax, by - ay] : [0, 0, w, h];
}

/** Ma trận nắn cho ảnh đã cắt từ (x0, y0): điểm camera trừ đi gốc vùng cắt. */
export const shiftWarps = (warps, x0, y0) => warps.map((m) => m && [m[0].map((v, i) => v - x0 * m[2][i]), m[1].map((v, i) => v - y0 * m[2][i]), [...m[2]]]);
