/* Chọn bộ suy luận trên điện thoại. CPU dùng model FP32 để tránh phụ thuộc các toán tử FP16 của WASM. */
const GPU_MODEL = "/ortweb/gr14VinAI.mixed.onnx";
const CPU_MODEL = "/ortweb/gr14VinAI.fp32.onnx";

export async function loadPhoneModel(load, mode = "auto", onFallback = () => {}, gpuModel = GPU_MODEL) {
  if (mode === "wasm") return { session: await load("wasm", CPU_MODEL), ep: "wasm" };
  if (mode !== "auto") throw new Error(`Bộ chạy không hợp lệ: ${mode}`);
  try { return { session: await load("webgpu", gpuModel), ep: "webgpu" }; }
  catch (e) {
    onFallback(`WebGPU không nạp được (${e.message || e}); đang thử CPU…`);
    return { session: await load("wasm", CPU_MODEL), ep: "wasm" };
  }
}
