const $ = (s) => document.querySelector(s);
const send = (msg) => new Promise((resolve) => chrome.runtime.sendMessage(msg, resolve));
function status(node, text, state = '') { node.className = `status${state ? ` ${state}` : ''}`; node.textContent = text; }
$('#check-local').onclick = async () => {
  const box = $('#local-status'); status(box, '正在检查…'); const r = await send({ type: 'local:check' });
  if (r?.ok && r.data?.ok) {
    const d = r.data;
    if (d.version_ok === false) return status(box, `本地组件版本 ${d.version || '?'} 与当前扩展不一致，请重新运行 SETUP。`, 'bad');
    const model = d.ollama?.has_model ? d.ollama.selected_model : '未找到兼容模型';
    const whisper = d.transcription_available === false ? '依赖缺失' : '就绪';
    return status(box, `本地组件 ${d.version || ''} 正常；整理模型：${model}；Whisper：${whisper}。`, 'ok');
  }
  status(box, `本地组件未就绪：${r?.error || r?.data?.reason || '请运行对应系统的 SETUP。'}`, 'bad');
};
$('#check-bili').onclick = async () => {
  const box = $('#bili-status'); status(box, '正在检查…'); const r = await send({ type: 'bili:nav' });
  if (r?.ok) return status(box, r.data.isLogin ? `B 站接口正常，已登录${r.data.uname ? `：${r.data.uname}` : ''}。` : 'B 站接口正常；当前未显示登录，部分字幕或音轨可能受限。', r.data.isLogin ? 'ok' : '');
  status(box, r?.error || 'B 站接口失败', 'bad');
};
$('#open-options').onclick = () => chrome.runtime.openOptionsPage();
