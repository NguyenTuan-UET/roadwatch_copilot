/* gr14VinAI chạy từng khung bằng session.run thường (CPU WebAssembly, hoặc WebGPU không ghi lại), như model.Gr14VinAI
   của laptop: hàng đợi trạng thái (state_*) của lần trước đưa vào lần sau; model có nhánh policy thì desire = 0,
   traffic_convention = [1, 0] (đi bên phải). Tensor không còn dùng được giải phóng ngay mỗi khung (bộ nhớ của Safari).
   Cùng giao diện run / reset / release với CapturedModel (captured.mjs). */
import { INPUTS, toF16 } from "./captured.mjs";

const count = (dims) => dims.reduce((a, b) => a * b, 1);

export class FrameModel {
  /** f16: model nhận ảnh và hàng đợi khung bằng float16 (gr14VinAI.capture.onnx), còn lại uint8. */
  constructor(ort, session, { f16 = false } = {}) {
    Object.assign(this, { ort, session, f16 });
    this.names = session.inputNames || ["new_img", "state_img_q"];
    this.feeds = {};
    if (this.names.includes("desire")) this.feeds.desire = new ort.Tensor("float32", new Float32Array(8), INPUTS.desire[1]);
    if (this.names.includes("traffic_convention"))
      this.feeds.traffic_convention = new ort.Tensor("float32", new Float32Array([1, 0]), INPUTS.traffic_convention[1]);
    this.reset();
  }

  _tensor(name, data = null) {   // hàng đợi khung: uint8 (đổi sang float16 nếu f16); hàng đợi policy: float32
    const dims = INPUTS[name][1];
    if (name === "state_img_q" || name === "new_img") {
      const u8 = data || new Uint8Array(count(dims));
      if (!this.f16) return new this.ort.Tensor("uint8", u8, dims);
      const bits = toF16(u8);   // trình duyệt có Float16Array: onnxruntime-web chỉ nhận kiểu đó cho float16 (cùng bit)
      return new this.ort.Tensor("float16", globalThis.Float16Array ? new Float16Array(bits.buffer) : bits, dims);
    }
    return new this.ort.Tensor("float32", data || new Float32Array(count(dims)), dims);
  }

  /** Hàng đợi về 0 (phiên mới), hoặc lấy giá trị cho trong init {state_img_q: Uint8Array, ...}. */
  reset(init = {}) {
    for (const name of this.names.filter((n) => n.startsWith("state_"))) {
      if (this.feeds[name]) this.feeds[name].dispose();
      this.feeds[name] = this._tensor(name, init[name]);
    }
  }

  /** input: đầu vào đã nắn (Uint8Array 2*6*128*256, như prep.mjs) -> Float32Array `outputs`. */
  async run(input) {
    const image = this._tensor("new_img", input);
    let out = null;
    try {
      out = await this.session.run({ ...this.feeds, new_img: image });
      if (!out.outputs) throw new Error("Model thiếu đầu ra");
      const outputs = Float32Array.from(out.outputs.data);
      for (const name of this.names.filter((n) => n.startsWith("state_"))) {
        if (!out["next_" + name]) throw new Error(`Model thiếu ${"next_" + name}`);
        this.feeds[name].dispose();
        this.feeds[name] = out["next_" + name];
      }
      return outputs;
    } finally {
      image.dispose();
      if (out) for (const [k, t] of Object.entries(out)) if (!(k.startsWith("next_") && this.feeds[k.slice(5)] === t)) t.dispose();
    }
  }

  async release() {
    for (const t of Object.values(this.feeds)) t.dispose();
    this.feeds = {};
    await this.session.release();
  }
}
