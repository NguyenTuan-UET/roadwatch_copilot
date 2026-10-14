/* Nắn ảnh camera vào khung model ngay trên GPU (WebGPU compute), thay cho prepFromRGBA trên CPU.
   Trên iPhone (13/10/2026), vẽ khung camera lên canvas rồi đọc về CPU (getImageData) mất 45–60 ms/khung và tab bị Safari
   đóng sau 10–45 s; ở đây khung camera được chép thẳng vào texture GPU, shader nắn + đổi màu + xếp 6 kênh như
   prep.mjs (cùng công thức: Y làm tròn từng điểm rồi nội suy, U/V lấy điểm toạ độ chẵn, ngoài ảnh = 0), và kết quả
   (2*6*128*256 byte, 393 KB) được đọc về CPU qua một buffer trung gian cấp phát một lần. Không đưa buffer GPU thẳng vào
   model được: các phép đầu của gr14VinAI trên đầu vào uint8 chạy ở CPU, onnxruntime-web 1.30 cố tải buffer về và lỗi
   (thử trên Chrome 13/10/2026).
   GPU tính float32 nên có thể lệch 1 mức ở vài điểm so với bản JS (float64); kiểm bằng so sánh trực tiếp trên trình duyệt. */
const OUT_BYTES = 2 * 6 * 128 * 256;
const SHADER = /* wgsl */ `
struct P { n0: vec4f, n1: vec4f, n2: vec4f, w0: vec4f, w1: vec4f, w2: vec4f, size: vec4f };  // ma trận theo hàng; size = (w, h, dup, 0)
@group(0) @binding(0) var src: texture_2d<f32>;
@group(0) @binding(1) var<uniform> p: P;
@group(0) @binding(2) var<storage, read_write> outBuf: array<u32>;

fn rgb(x: i32, y: i32) -> vec3f { return textureLoad(src, vec2i(x, y), 0).rgb * 255.0; }
fn rnd(v: f32) -> f32 { return floor(v + 0.5); }   // như Math.round (round() của WGSL làm tròn về số chẵn)
fn yOf(c: vec3f) -> f32 { return rnd(16.0 + 0.257 * c.r + 0.504 * c.g + 0.098 * c.b); }
fn uOf(c: vec3f) -> f32 { return clamp(rnd(128.0 - 0.148 * c.r - 0.291 * c.g + 0.439 * c.b), 0.0, 255.0); }
fn vOf(c: vec3f) -> f32 { return clamp(rnd(128.0 + 0.439 * c.r - 0.368 * c.g - 0.071 * c.b), 0.0, 255.0); }

// một byte của đầu vào model: slot (hẹp/rộng), kênh, hàng, cột của mặt phẳng 128x256
fn sample(slot: u32, ch: u32, rr: u32, cc: u32) -> f32 {
  var m0 = p.n0.xyz; var m1 = p.n1.xyz; var m2 = p.n2.xyz;
  if (slot == 1u && p.size.z < 0.5) { m0 = p.w0.xyz; m1 = p.w1.xyz; m2 = p.w2.xyz; }
  let w = i32(p.size.x); let h = i32(p.size.y);
  if (ch < 4u) {   // Y: điểm (r, col) của khung 512x256; kênh = (r & 1) + 2 * (col & 1)
    let r = f32(2u * rr + (ch & 1u)); let col = f32(2u * cc + (ch >> 1u));
    let z = m2.x * col + m2.y * r + m2.z;
    if (z <= 0.0) { return 0.0; }
    let x = (m0.x * col + m0.y * r + m0.z) / z; let y = (m1.x * col + m1.y * r + m1.z) / z;
    let x0 = i32(floor(x)); let y0 = i32(floor(y));
    if (x0 < -1 || y0 < -1 || x0 >= w || y0 >= h) { return 0.0; }
    let fx = x - f32(x0); let fy = y - f32(y0);
    var q = vec4f(0.0);
    if (x0 >= 0 && y0 >= 0) { q.x = yOf(rgb(x0, y0)); }
    if (x0 + 1 < w && y0 >= 0) { q.y = yOf(rgb(x0 + 1, y0)); }
    if (x0 >= 0 && y0 + 1 < h) { q.z = yOf(rgb(x0, y0 + 1)); }
    if (x0 + 1 < w && y0 + 1 < h) { q.w = yOf(rgb(x0 + 1, y0 + 1)); }
    return rnd((q.x * (1.0 - fx) + q.y * fx) * (1.0 - fy) + (q.z * (1.0 - fx) + q.w * fx) * fy);
  }
  // U (ch 4), V (ch 5): lưới màu nửa độ phân giải, điểm màu (xx, yy) = điểm ảnh (2xx, 2yy)
  let r = f32(rr); let col = f32(cc);
  let z = 2.0 * m2.x * col + 2.0 * m2.y * r + m2.z;
  if (z <= 0.0) { return 0.0; }
  let x = (m0.x * col + m0.y * r + m0.z / 2.0) / z; let y = (m1.x * col + m1.y * r + m1.z / 2.0) / z;
  let cw = w / 2; let chh = h / 2;
  let x0 = i32(floor(x)); let y0 = i32(floor(y));
  if (x0 < -1 || y0 < -1 || x0 >= cw || y0 >= chh) { return 0.0; }
  let fx = x - f32(x0); let fy = y - f32(y0);
  var q = vec4f(0.0);
  let isU = ch == 4u;
  if (x0 >= 0 && y0 >= 0) { let c = rgb(2 * x0, 2 * y0); q.x = select(vOf(c), uOf(c), isU); }
  if (x0 + 1 < cw && y0 >= 0) { let c = rgb(2 * x0 + 2, 2 * y0); q.y = select(vOf(c), uOf(c), isU); }
  if (x0 >= 0 && y0 + 1 < chh) { let c = rgb(2 * x0, 2 * y0 + 2); q.z = select(vOf(c), uOf(c), isU); }
  if (x0 + 1 < cw && y0 + 1 < chh) { let c = rgb(2 * x0 + 2, 2 * y0 + 2); q.w = select(vOf(c), uOf(c), isU); }
  return rnd((q.x * (1.0 - fx) + q.y * fx) * (1.0 - fy) + (q.z * (1.0 - fx) + q.w * fx) * fy);
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3u) {
  let word = gid.x;
  if (word >= ${OUT_BYTES / 4}u) { return; }
  var packed = 0u;
  for (var k = 0u; k < 4u; k++) {   // 4 byte liên tiếp: cùng slot, kênh, hàng (256 cột chia hết cho 4)
    let o = 4u * word + k;
    let slot = o / ${6 * 128 * 256}u; let rest = o % ${6 * 128 * 256}u;
    let ch = rest / ${128 * 256}u; let pix = rest % ${128 * 256}u;
    let v = u32(clamp(sample(slot, ch, pix / 256u, pix % 256u), 0.0, 255.0));
    packed = packed | (v << (8u * k));
  }
  outBuf[word] = packed;
}`;

const row = (m, i) => (m ? [m[i][0], m[i][1], m[i][2], 0] : [0, 0, 0, 0]);

/** device: GPUDevice của onnxruntime-web (ort.env.webgpu.device) để buffer kết quả đưa thẳng vào model. */
export class GpuPrep {
  constructor(device, w, h) {
    this.device = device; this.w = w; this.h = h;
    this.texture = device.createTexture({ size: [w, h], format: "rgba8unorm",
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT });
    this.params = device.createBuffer({ size: 7 * 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    this.out = device.createBuffer({ size: OUT_BYTES, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    this.staging = device.createBuffer({ size: OUT_BYTES, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST });
    this.pipeline = device.createComputePipeline({ layout: "auto", compute: { module: device.createShaderModule({ code: SHADER }), entryPoint: "main" } });
    this.bind = device.createBindGroup({ layout: this.pipeline.getBindGroupLayout(0), entries: [
      { binding: 0, resource: this.texture.createView() }, { binding: 1, resource: { buffer: this.params } }, { binding: 2, resource: { buffer: this.out } }] });
  }

  /** source: video (hoặc canvas) cỡ w x h; warps: [narrow, wide|null] (điểm khung model -> điểm camera).
      Ghi kết quả vào out (Uint8Array 2*6*128*256) và trả về out. */
  async run(source, warps, out = new Uint8Array(OUT_BYTES)) {
    const [n, wd] = warps;
    this.device.queue.copyExternalImageToTexture({ source }, { texture: this.texture }, [this.w, this.h]);
    this.device.queue.writeBuffer(this.params, 0, new Float32Array([...row(n, 0), ...row(n, 1), ...row(n, 2),
      ...row(wd, 0), ...row(wd, 1), ...row(wd, 2), this.w, this.h, wd ? 0 : 1, 0]));
    const enc = this.device.createCommandEncoder(), pass = enc.beginComputePass();
    pass.setPipeline(this.pipeline); pass.setBindGroup(0, this.bind);
    pass.dispatchWorkgroups(Math.ceil(OUT_BYTES / 4 / 64));
    pass.end();
    enc.copyBufferToBuffer(this.out, 0, this.staging, 0, OUT_BYTES);
    this.device.queue.submit([enc.finish()]);
    await this.staging.mapAsync(GPUMapMode.READ);
    out.set(new Uint8Array(this.staging.getMappedRange()));
    this.staging.unmap();
    return out;
  }

  destroy() { for (const b of [this.texture, this.params, this.out, this.staging]) b.destroy(); }
}
