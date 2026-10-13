/** Run createFeedbackForm in Google Apps Script while signed in to Google. */
function createFeedbackForm() {
  const properties = PropertiesService.getScriptProperties();
  const existingId = properties.getProperty('ROADWATCH_FEEDBACK_FORM_ID');
  if (existingId) {
    const existing = FormApp.openById(existingId);
    Logger.log('Chỉnh sửa: ' + existing.getEditUrl());
    Logger.log('Gửi khảo sát: ' + existing.getPublishedUrl());
    return existing;
  }

  const form = FormApp.create('Khảo sát trải nghiệm RoadWatch Copilot', false);
  form.setDescription(
    'RoadWatch Copilot là trợ lý cảnh báo hỗ trợ tài xế mới trên cao tốc. ' +
    'Vui lòng trả lời sau khi trực tiếp dùng sản phẩm. ' +
    'Chấm theo trải nghiệm của bạn; nhóm không chấm thay. ' +
    'Nếu không có điều gì khiến bạn bực, hãy ghi “Không có”. ' +
    'Chỉ gửi phiếu khi xe đã dừng ở nơi an toàn.'
  );
  form.setCollectEmail(false);
  form.setConfirmationMessage('Đã nhận phản hồi của bạn. Cảm ơn bạn đã dùng thử RoadWatch Copilot!');
  form.setPublishingSummary(false);
  form.addTextItem().setTitle('Tên của bạn.').setRequired(true);
  form.addScaleItem()
    .setTitle('Sản phẩm có đạt mong đợi của bạn không?')
    .setBounds(1, 5).setLabels('Hoàn toàn không', 'Hoàn toàn đạt').setRequired(true);
  form.addScaleItem()
    .setTitle('Bạn có dùng lại sản phẩm không?')
    .setBounds(1, 5).setLabels('Chắc chắn không', 'Chắc chắn có').setRequired(true);
  form.addScaleItem()
    .setTitle('Bạn có giới thiệu sản phẩm cho bạn bè không?')
    .setBounds(1, 5).setLabels('Chắc chắn không', 'Chắc chắn có').setRequired(true);
  form.addParagraphTextItem().setTitle('Điều gì khiến bạn bực nhất khi dùng?').setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('Nhóm có được trích câu trả lời của bạn trong báo cáo không?')
    .setChoiceValues(['Có, kèm tên', 'Có, nhưng ẩn tên', 'Không đồng ý trích dẫn'])
    .setRequired(true);
  form.setPublished(true);
  form.setAcceptingResponses(true);
  properties.setProperty('ROADWATCH_FEEDBACK_FORM_ID', form.getId());
  Logger.log('Chỉnh sửa: ' + form.getEditUrl());
  Logger.log('Gửi khảo sát: ' + form.getPublishedUrl());
  return form;
}
