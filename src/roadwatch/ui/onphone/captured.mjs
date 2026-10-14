/* gr14VinAI trên GPU của điện thoại bằng graph capture (onnxruntime-web 1.20.1, JSEP, enableGraphCapture): lần chạy đầu
   ghi lại chuỗi lệnh GPU, các lần sau phát lại trên đúng các bộ đệm đó. Trên iPhone 13 (14/10/2026; docs/roadwatch-operations.md): chỉ
   cách này chạy hết 12000 lần mà Safari không đóng tab; chạy thường, mỗi lần tạo một bind group cho mỗi phép và WebGPU
   của Safari hỏng sau vài chục nghìn bind group; bản 1.30 thì tab bị đóng sau khoảng 3450 lần cả khi ghi lại (lỗi
   biên dịch WebAssembly của WebKit, onnxruntime #26827).
   Model là gr14VinAI.capture.onnx (scripts/roadwatch/make_phone_models.py): đầu vào và hàng đợi 5 khung float16, vì
   các phép uint8 chạy ở CPU và JSEP không cho ghi lại. Mỗi khung: đổi ảnh đã nắn (uint8) sang float16, ghi lên GPU,
   chạy, chép mọi next_state_* sang bộ đệm trạng thái ngay trên GPU, đọc `outputs` về CPU.
   Model có nhánh policy (như laptop: model.Gr14VinAI) còn có desire = 0, traffic_convention = [1, 0] (đi bên phải),
   các hàng đợi state_desire_q, state_feat_q, và 1961 số đầu ra (thêm road_edges, plan); bản cũ không có: 707 số. */

/* đầu vào của gr14VinAI.capture.onnx: kiểu, kích thước; hàng đợi trạng thái X có đầu ra next_X cùng cỡ */
export const INPUTS = {
  new_img: ["float16", [2, 6, 128, 256]], state_img_q: ["float16", [2, 5, 6, 128, 256]],
  desire: ["float32", [8]], traffic_convention: ["float32", [1, 2]],
  state_desire_q: ["float32", [100, 1, 8]], state_feat_q: ["float32", [96, 1, 512]],
};
const BYTES = { float16: 2, float32: 4 };
const count = (dims) => dims.reduce((a, b) => a * b, 1);

/** Bit float16 của 0..255 (số nguyên nhỏ hơn 2048 biểu diễn đúng trong float16). */
export const F16 = Uint16Array.from({ length: 256 }, (_, v) => {
  if (!v) return 0;
  const e = Math.floor(Math.log2(v));
  return ((e + 15) << 10) | ((v / 2 ** e - 1) * 1024);
});

export function toF16(u8, out = new Uint16Array(u8.length)) {
  for (let i = 0; i < u8.length; i++) out[i] = F16[u8[i]];
  return out;
}

export class CapturedModel {
  /** ort: onnxruntime-web; session tạo với enableGraphCapture và preferredOutputLocation "gpu-buffer";
      device: GPUDevice của chính onnxruntime-web (ort.env.webgpu.device). */
  constructor(ort, session, device = ort.env.webgpu.device) {
    Object.assign(this, { session, device });
    const U = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
    const buffer = (bytes, usage = U) => device.createBuffer({ size: Math.ceil(bytes / 16) * 16, usage });
    const gpu = (b, dataType, dims) => ort.Tensor.fromGpuBuffer(b, { dataType, dims });
    const names = session.inputNames || ["new_img", "state_img_q"];
    this.outN = names.includes("desire") ? 1961 : 707; this.outBytes = 4 * this.outN;
    this.buffers = []; this.states = [];   // states: [đầu vào, đầu ra next_*, số byte]
    // cùng các đối tượng này cho mọi lần chạy: lần phát lại dùng đúng bộ đệm của lần ghi
    this.feeds = {}; this.fetches = {};
    for (const name of names) {
      const [type, dims] = INPUTS[name], bytes = BYTES[type] * count(dims), b = buffer(bytes);
      this.buffers.push(b); this.feeds[name] = gpu(b, type, dims);
      if (name.startsWith("state_")) {
        const next = buffer(bytes);
        this.buffers.push(next); this.fetches["next_" + name] = gpu(next, type, dims); this.states.push([b, next, bytes]);
      }
    }
    this.img = this.feeds.new_img.gpuBuffer;
    if (this.feeds.traffic_convention) device.queue.writeBuffer(this.feeds.traffic_convention.gpuBuffer, 0, new Float32Array([1, 0]));
    const out = buffer(this.outBytes);
    this.staging = buffer(this.outBytes, GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST);
    this.buffers.push(out, this.staging);
    this.fetches.outputs = gpu(out, "float32", [1, this.outN]);
    this.half = new Uint16Array(count(INPUTS.new_img[1]));
  }

  /** Bắt đầu một lần đo mới: mọi hàng đợi về 0 như phiên mới của model trên CPU. */
  reset() { for (const [b, , bytes] of this.states) this.device.queue.writeBuffer(b, 0, new Uint8Array(bytes)); }

  /** input: đầu vào đã nắn (Uint8Array 2*6*128*256, như prep.mjs) -> Float32Array `outputs` (707 hoặc 1961 số). */
  async run(input) {
    this.device.queue.writeBuffer(this.img, 0, toF16(input, this.half));
    await this.session.run(this.feeds, this.fetches);
    const enc = this.device.createCommandEncoder();
    for (const [b, next, bytes] of this.states) enc.copyBufferToBuffer(next, 0, b, 0, bytes);
    enc.copyBufferToBuffer(this.fetches.outputs.gpuBuffer, 0, this.staging, 0, this.outBytes);
    this.device.queue.submit([enc.finish()]);
    await this.staging.mapAsync(GPUMapMode.READ);
    const outputs = new Float32Array(this.staging.getMappedRange(0, this.outBytes)).slice();
    this.staging.unmap();
    return outputs;
  }

  async release() {
    for (const b of this.buffers) b.destroy();
    await this.session.release();
  }
}
