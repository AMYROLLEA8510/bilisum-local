const defaults = {
  model: 'auto', scanDelayMs: 1400, batchConcurrency: 'auto', modelParallelism: 'auto', autoSummarize: true, autoOpenPanel: false,
  summaryMode: 'auto', autoSaveNotes: false, autoSaveBatch: false,
  asrEnabled: true, asrModel: 'auto', asrDevice: 'auto', asrLanguage: '', asrMaxMinutes: 240,
  updateMode: 'notify'
};
const $ = (s) => document.querySelector(s);
const send = (msg) => new Promise((resolve) => chrome.runtime.sendMessage(msg, resolve));

function setStatus(node, text, state = '') {
  node.className = `status${state ? ` ${state}` : ''}`;
  node.textContent = text;
}

async function load() {
  const s = await chrome.storage.local.get(defaults);
  $('#model').value = s.model || 'auto';
  $('#delay').value = Number(s.scanDelayMs || 1400);
  $('#batch-concurrency').value = String(s.batchConcurrency || 'auto');
  $('#auto').checked = !!s.autoSummarize;
  $('#auto-open').checked = !!s.autoOpenPanel;
  $('#auto-save-note').checked = !!s.autoSaveNotes;
  $('#auto-save-batch').checked = !!s.autoSaveBatch;
  $('#summary-mode').value = s.summaryMode || 'auto';
  $('#asr-enabled').checked = !!s.asrEnabled;
  $('#asr-model').value = s.asrModel || 'auto';
  $('#asr-device').value = s.asrDevice || 'auto';
  $('#asr-language').value = s.asrLanguage || '';
  $('#asr-max').value = Number(s.asrMaxMinutes ?? 240);
  $('#update-mode').value = s.updateMode || 'notify';
  await refreshSaveStatus();
  const cached = await chrome.storage.local.get(['updateInfo', 'updateCheckedAt', 'updateError']);
  if (cached.updateInfo || cached.updateError) renderUpdate(cached.updateInfo, cached.updateError, cached.updateCheckedAt);
}

async function save() {
  const settings = {
    model: $('#model').value.trim() || 'auto',
    scanDelayMs: Math.max(600, Number($('#delay').value) || 1400),
    batchConcurrency: $('#batch-concurrency').value || 'auto',
    modelParallelism: 'auto',
    autoSummarize: $('#auto').checked,
    autoOpenPanel: $('#auto-open').checked,
    autoSaveNotes: $('#auto-save-note').checked,
    autoSaveBatch: $('#auto-save-batch').checked,
    summaryMode: $('#summary-mode').value || 'auto',
    asrEnabled: $('#asr-enabled').checked,
    asrModel: $('#asr-model').value || 'auto',
    asrDevice: $('#asr-device').value || 'auto',
    asrLanguage: $('#asr-language').value || '',
    asrMaxMinutes: Math.max(0, Number($('#asr-max').value) || 0),
    updateMode: $('#update-mode').value || 'notify'
  };
  await chrome.storage.local.set(settings);
  return settings;
}

$('#save').onclick = async () => {
  await save();
  $('#saved').textContent = '已保存';
  setTimeout(() => { $('#saved').textContent = ''; }, 1200);
};

$('#local-test').onclick = async () => {
  const box = $('#local-status'); setStatus(box, '正在检测…'); await save();
  const r = await send({ type: 'local:check' });
  if (r?.ok && r.data?.ok) {
    const d = r.data;
    if (d.version_ok === false) return setStatus(box, `本地组件版本为 ${d.version || '?'}，与当前扩展不一致。请重新运行本版本 SETUP。`, 'bad');
    const model = d.ollama?.has_model ? d.ollama.selected_model : '未找到兼容模型';
    const whisper = d.transcription_available === false ? '依赖缺失' : (d.transcription_model?.loaded ? `${d.transcription_model.model}/${d.transcription_model.device}` : '按需加载');
    const parallel = d.parallelism?.notes_limit || d.parallelism?.recommended || 1;
    return setStatus(box, `本地组件 ${d.version || ''} 正常；整理模型：${model}；Whisper：${whisper}；模型并发上限：${parallel}；队列：整理 ${d.queues?.notes ?? 0} / 听写 ${d.queues?.transcription ?? 0}。`, 'ok');
  }
  setStatus(box, `本地组件不可用：${r?.error || r?.data?.reason || '请重新运行对应系统的 SETUP。'}`, 'bad');
};

async function refreshSaveStatus() {
  const box = $('#save-status'); const r = await send({ type: 'save:status' });
  if (r?.ok && r.data?.available) setStatus(box, `当前目录：${r.data.directory}`, 'ok');
  else setStatus(box, '尚未选择笔记保存目录。');
}

$('#choose-dir').onclick = async () => {
  const box = $('#save-status'); setStatus(box, '正在打开系统目录选择器…');
  const r = await send({ type: 'save:choose' });
  if (!r?.ok || !r.data?.job_id) return setStatus(box, r?.error || '目录选择失败', 'bad');
  while (true) {
    await new Promise((x) => setTimeout(x, 700));
    const j = await send({ type: 'local:job', jobId: r.data.job_id });
    if (!j?.ok) return setStatus(box, j?.error || '目录选择状态读取失败', 'bad');
    if (j.data.status === 'done') { await refreshSaveStatus(); return; }
    if (j.data.status === 'error') return setStatus(box, j.data.error || '目录选择失败', 'bad');
    setStatus(box, '请在系统窗口中选择保存文件夹…');
  }
};
$('#clear-dir').onclick = async () => { await send({ type: 'save:clear' }); await refreshSaveStatus(); };
$('#set-dir').onclick = async () => {
  const box = $('#save-status'); const directory = $('#manual-dir').value.trim();
  if (!directory) return setStatus(box, '请输入目录路径。', 'bad');
  const r = await send({ type: 'save:set', directory });
  if (!r?.ok) return setStatus(box, r?.error || '路径设置失败', 'bad');
  $('#manual-dir').value = ''; await refreshSaveStatus();
};

$('#bili-test').onclick = async () => {
  const box = $('#bili-status'); setStatus(box, '正在检查…');
  const r = await send({ type: 'bili:nav' });
  if (!r?.ok) return setStatus(box, `B 站接口失败：${r?.error || '未知错误'}`, 'bad');
  setStatus(box, r.data.isLogin ? `B 站接口正常，已登录${r.data.uname ? `：${r.data.uname}` : ''}。` : 'B 站接口正常；当前请求显示未登录，部分字幕或音轨可能受限。', r.data.isLogin ? 'ok' : '');
};

function renderUpdate(info, error = '', checkedAt = 0) {
  const box = $('#update-status');
  if (error) return setStatus(box, `更新检查失败：${error}`, 'bad');
  if (!info) return setStatus(box, '尚未检查');
  const when = checkedAt ? `；${new Date(checkedAt).toLocaleString()}` : '';
  if (info.unconfigured) return setStatus(box, `更新源尚未配置${when}。`);
  if (info.disabled) return setStatus(box, `内置更新已禁用${when}。`);
  if (info.available) return setStatus(box, `有新版本 ${info.latest_version}（当前 ${info.current_version}）${when}。`, 'ok');
  setStatus(box, `已是最新版本 ${info.current_version || ''}${when}。`, 'ok');
}

$('#update-check').onclick = async () => {
  const box = $('#update-status'); setStatus(box, '正在检查更新…'); await save();
  const r = await send({ type: 'update:check' });
  if (!r?.ok) return setStatus(box, r?.error || '更新检查失败', 'bad');
  const checkedAt = Date.now(); await chrome.storage.local.set({ updateInfo: r.data, updateCheckedAt: checkedAt, updateError: '' });
  renderUpdate(r.data, '', checkedAt);
};

$('#update-install').onclick = async () => {
  const box = $('#update-status'); setStatus(box, '正在获取并校验更新…'); await save();
  const r = await send({ type: 'update:install' });
  if (!r?.ok) return setStatus(box, r?.error || '安装更新失败', 'bad');
  if (!r.data?.staged) return renderUpdate(r.data, '', Date.now());
  setStatus(box, '更新已校验，正在替换程序文件。扩展将自动重新加载。', 'ok');
};

load();
