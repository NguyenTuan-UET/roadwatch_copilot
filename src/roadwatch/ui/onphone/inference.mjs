/* Trả dữ liệu đã tách khỏi ONNX Runtime và tensor trạng thái kế tiếp.
   Tensor đầu vào và đầu ra không còn dùng được giải phóng ngay mỗi khung. */
export async function inferFrame(session, image, previousState, parse) {
  let outputs = null, nextState = null;
  try {
    outputs = await session.run({ new_img: image, state_img_q: previousState });
    if (!outputs.outputs || !outputs.next_state_img_q) throw new Error("Model thiếu đầu ra hoặc trạng thái kế tiếp");
    const parsed = parse(outputs.outputs.data);
    nextState = outputs.next_state_img_q;
    return { parsed, nextState };
  } finally {
    image.dispose();
    previousState.dispose();
    if (outputs) for (const tensor of Object.values(outputs)) if (tensor !== nextState) tensor.dispose();
  }
}
