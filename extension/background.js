const DEFAULT_SETTINGS = {
  model: 'auto',
  scanDelayMs: 1400,
  batchConcurrency: 'auto',
  modelParallelism: 'auto',
  maxTranscriptChunkChars: 26000,
  autoSummarize: true,
  autoOpenPanel: false,
  summaryMode: 'auto',
  autoSaveNotes: false,
  autoSaveBatch: false,
  asrEnabled: true,
  asrModel: 'auto',
  asrDevice: 'auto',
  asrLanguage: '',
  asrMaxMinutes: 240,
  jobPollMs: 1200,
  updateMode: 'notify'
};

const MIXIN_KEY_ENC_TAB = [
  46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,
  29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,
  22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function getSettings() {
  const saved = await chrome.storage.local.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...saved };
}

function add32(a, b) { return (a + b) & 0xffffffff; }
function cmn(q, a, b, x, s, t) { a = add32(add32(a, q), add32(x, t)); return add32((a << s) | (a >>> (32 - s)), b); }
function md5cycle(x, k) {
  let [a,b,c,d] = x;
  const ff=(a,b,c,d,x,s,t)=>cmn((b&c)|((~b)&d),a,b,x,s,t);
  const gg=(a,b,c,d,x,s,t)=>cmn((b&d)|(c&(~d)),a,b,x,s,t);
  const hh=(a,b,c,d,x,s,t)=>cmn(b^c^d,a,b,x,s,t);
  const ii=(a,b,c,d,x,s,t)=>cmn(c^(b|(~d)),a,b,x,s,t);
  a=ff(a,b,c,d,k[0],7,-680876936); d=ff(d,a,b,c,k[1],12,-389564586); c=ff(c,d,a,b,k[2],17,606105819); b=ff(b,c,d,a,k[3],22,-1044525330);
  a=ff(a,b,c,d,k[4],7,-176418897); d=ff(d,a,b,c,k[5],12,1200080426); c=ff(c,d,a,b,k[6],17,-1473231341); b=ff(b,c,d,a,k[7],22,-45705983);
  a=ff(a,b,c,d,k[8],7,1770035416); d=ff(d,a,b,c,k[9],12,-1958414417); c=ff(c,d,a,b,k[10],17,-42063); b=ff(b,c,d,a,k[11],22,-1990404162);
  a=ff(a,b,c,d,k[12],7,1804603682); d=ff(d,a,b,c,k[13],12,-40341101); c=ff(c,d,a,b,k[14],17,-1502002290); b=ff(b,c,d,a,k[15],22,1236535329);
  a=gg(a,b,c,d,k[1],5,-165796510); d=gg(d,a,b,c,k[6],9,-1069501632); c=gg(c,d,a,b,k[11],14,643717713); b=gg(b,c,d,a,k[0],20,-373897302);
  a=gg(a,b,c,d,k[5],5,-701558691); d=gg(d,a,b,c,k[10],9,38016083); c=gg(c,d,a,b,k[15],14,-660478335); b=gg(b,c,d,a,k[4],20,-405537848);
  a=gg(a,b,c,d,k[9],5,568446438); d=gg(d,a,b,c,k[14],9,-1019803690); c=gg(c,d,a,b,k[3],14,-187363961); b=gg(b,c,d,a,k[8],20,1163531501);
  a=gg(a,b,c,d,k[13],5,-1444681467); d=gg(d,a,b,c,k[2],9,-51403784); c=gg(c,d,a,b,k[7],14,1735328473); b=gg(b,c,d,a,k[12],20,-1926607734);
  a=hh(a,b,c,d,k[5],4,-378558); d=hh(d,a,b,c,k[8],11,-2022574463); c=hh(c,d,a,b,k[11],16,1839030562); b=hh(b,c,d,a,k[14],23,-35309556);
  a=hh(a,b,c,d,k[1],4,-1530992060); d=hh(d,a,b,c,k[4],11,1272893353); c=hh(c,d,a,b,k[7],16,-155497632); b=hh(b,c,d,a,k[10],23,-1094730640);
  a=hh(a,b,c,d,k[13],4,681279174); d=hh(d,a,b,c,k[0],11,-358537222); c=hh(c,d,a,b,k[3],16,-722521979); b=hh(b,c,d,a,k[6],23,76029189);
  a=hh(a,b,c,d,k[9],4,-640364487); d=hh(d,a,b,c,k[12],11,-421815835); c=hh(c,d,a,b,k[15],16,530742520); b=hh(b,c,d,a,k[2],23,-995338651);
  a=ii(a,b,c,d,k[0],6,-198630844); d=ii(d,a,b,c,k[7],10,1126891415); c=ii(c,d,a,b,k[14],15,-1416354905); b=ii(b,c,d,a,k[5],21,-57434055);
  a=ii(a,b,c,d,k[12],6,1700485571); d=ii(d,a,b,c,k[3],10,-1894986606); c=ii(c,d,a,b,k[10],15,-1051523); b=ii(b,c,d,a,k[1],21,-2054922799);
  a=ii(a,b,c,d,k[8],6,1873313359); d=ii(d,a,b,c,k[15],10,-30611744); c=ii(c,d,a,b,k[6],15,-1560198380); b=ii(b,c,d,a,k[13],21,1309151649);
  a=ii(a,b,c,d,k[4],6,-145523070); d=ii(d,a,b,c,k[11],10,-1120210379); c=ii(c,d,a,b,k[2],15,718787259); b=ii(b,c,d,a,k[9],21,-343485551);
  x[0]=add32(a,x[0]); x[1]=add32(b,x[1]); x[2]=add32(c,x[2]); x[3]=add32(d,x[3]);
}
function md5blk(s){const out=[];for(let i=0;i<64;i+=4){out[i>>2]=s.charCodeAt(i)+(s.charCodeAt(i+1)<<8)+(s.charCodeAt(i+2)<<16)+(s.charCodeAt(i+3)<<24);}return out;}
function md51(s){let n=s.length,state=[1732584193,-271733879,-1732584194,271733878],i;for(i=64;i<=n;i+=64)md5cycle(state,md5blk(s.substring(i-64,i)));s=s.substring(i-64);const tail=new Array(16).fill(0);for(i=0;i<s.length;i++)tail[i>>2]|=s.charCodeAt(i)<<((i%4)<<3);tail[i>>2]|=0x80<<((i%4)<<3);if(i>55){md5cycle(state,tail);tail.fill(0);}tail[14]=n*8;md5cycle(state,tail);return state;}
function rhex(n){let s='';for(let j=0;j<4;j++)s+=('0'+((n>>(j*8))&0xff).toString(16)).slice(-2);return s;}
function md5(s){return md51(unescape(encodeURIComponent(s))).map(rhex).join('');}

async function fetchJson(url, options = {}, retries = 2) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 18000);
    try {
      const res = await fetch(url, {
        credentials: 'include',
        cache: 'no-store',
        signal: controller.signal,
        ...options,
        headers: {
          'Accept': 'application/json, text/plain, */*',
          ...(options.headers || {})
        }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (error) {
      lastError = error;
      if (attempt < retries) await sleep(700 * (attempt + 1));
    } finally {
      clearTimeout(timer);
    }
  }
  throw new Error(`网络请求失败：${lastError?.message || 'unknown error'}`);
}

let wbiCache = null;
async function getWbiKeys(force = false) {
  if (!force && wbiCache && Date.now() - wbiCache.at < 15 * 60 * 1000) return wbiCache;
  const nav = await fetchJson('https://api.bilibili.com/x/web-interface/nav', {}, 1);
  const wbi = nav?.data?.wbi_img;
  if (!wbi?.img_url || !wbi?.sub_url) throw new Error(`无法取得 B 站 WBI 参数：${nav?.message || nav?.code || 'unknown'}`);
  const basename = (url) => url.split('/').pop().split('.')[0];
  const raw = basename(wbi.img_url) + basename(wbi.sub_url);
  const mixinKey = MIXIN_KEY_ENC_TAB.map((i) => raw[i] || '').join('').slice(0, 32);
  wbiCache = { mixinKey, at: Date.now() };
  return wbiCache;
}

async function signWbi(params, force = false) {
  const { mixinKey } = await getWbiKeys(force);
  const clean = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    clean[key] = String(value).replace(/[!'()*]/g, '');
  }
  clean.wts = Math.floor(Date.now() / 1000);
  const query = Object.keys(clean).sort().map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(clean[key])}`).join('&');
  return `${query}&w_rid=${md5(query + mixinKey)}`;
}

function biliError(data) {
  const error = new Error(`B站接口 ${data?.code}: ${data?.message || '未知错误'}`);
  error.code = data?.code;
  return error;
}

async function biliWbi(path, params) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const qs = await signWbi(params, attempt > 0);
    const data = await fetchJson(`https://api.bilibili.com${path}?${qs}`, {}, 1);
    if (data.code === 0) return data.data;
    if ([-352, -412].includes(data.code) && attempt === 0) {
      wbiCache = null;
      await sleep(2200);
      continue;
    }
    throw biliError(data);
  }
  throw new Error('B站接口暂时不可用。');
}

async function getNavStatus() {
  const nav = await fetchJson('https://api.bilibili.com/x/web-interface/nav', {}, 1);
  return {
    code: nav.code,
    message: nav.message,
    isLogin: !!nav.data?.isLogin,
    uname: nav.data?.uname || '',
    mid: nav.data?.mid || 0
  };
}

async function getAllVideos(mid) {
  const out = [];
  const seen = new Set();
  let pn = 1;
  let total = Number.POSITIVE_INFINITY;
  while (out.length < total && pn <= 500) {
    const data = await biliWbi('/x/space/wbi/arc/search', {
      mid,
      ps: 30,
      tid: 0,
      pn,
      keyword: '',
      order: 'pubdate',
      platform: 'web',
      web_location: 1550101,
      order_avoided: 'true'
    });
    total = Number(data?.page?.count || 0);
    const items = data?.list?.vlist || [];
    for (const v of items) {
      if (!v.bvid || seen.has(v.bvid)) continue;
      seen.add(v.bvid);
      out.push({
        bvid: v.bvid,
        aid: v.aid,
        title: v.title,
        description: v.description || '',
        duration: v.length || '',
        created: v.created,
        play: v.play,
        pic: v.pic,
        author: v.author,
        mid: v.mid
      });
    }
    if (!items.length || out.length >= total) break;
    pn += 1;
    await sleep(550);
  }
  return out;
}

async function getVideoInfo(bvid) {
  const data = await fetchJson(`https://api.bilibili.com/x/web-interface/view?bvid=${encodeURIComponent(bvid)}`, {}, 1);
  if (data.code !== 0) throw biliError(data);
  return data.data;
}

function chooseSubtitle(list) {
  if (!Array.isArray(list) || !list.length) return null;
  const score = (s) => {
    const lan = String(s.lan || '').toLowerCase();
    const doc = String(s.lan_doc || '').toLowerCase();
    let value = 0;
    if (lan.includes('zh-cn') || lan.includes('zh-hans')) value += 100;
    if (doc.includes('简体') || doc.includes('中文') || doc.includes('汉语')) value += 80;
    if (lan.startsWith('zh')) value += 60;
    if (Number(s.ai_type) === 0) value += 8;
    return value;
  };
  return [...list].sort((a, b) => score(b) - score(a))[0];
}

function cleanSubtitleLines(body) {
  const out = [];
  let previous = '';
  for (const x of body || []) {
    const content = String(x.content || '').replace(/\s+/g, ' ').trim();
    if (!content) continue;
    const normalized = content.replace(/[，。！？、,.!?\s]/g, '');
    if (normalized && normalized === previous) continue;
    previous = normalized;
    out.push({ from: Number(x.from || 0), to: Number(x.to || 0), content });
  }
  return out;
}

async function getPageTranscript(bvid, aid, page, partIndex) {
  let player;
  try {
    player = await biliWbi('/x/player/wbi/v2', { bvid, aid, cid: page.cid });
  } catch (error) {
    const fallback = await fetchJson(`https://api.bilibili.com/x/player/v2?bvid=${encodeURIComponent(bvid)}&aid=${aid}&cid=${page.cid}`, {}, 1);
    if (fallback.code !== 0) throw error;
    player = fallback.data;
  }
  const selected = chooseSubtitle(player?.subtitle?.subtitles || []);
  if (!selected?.subtitle_url) {
    return { partIndex, partTitle: page.part || `P${partIndex}`, cid: page.cid, duration: Number(page.duration || 0), subtitle: null, lines: [] };
  }
  const subtitleUrl = selected.subtitle_url.startsWith('//') ? `https:${selected.subtitle_url}` : selected.subtitle_url;
  const payload = await fetchJson(subtitleUrl, {}, 2);
  return {
    partIndex,
    partTitle: page.part || `P${partIndex}`,
    cid: page.cid,
    duration: Number(page.duration || 0),
    subtitle: { lan: selected.lan, lanDoc: selected.lan_doc, aiType: selected.ai_type, source: 'bilibili' },
    lines: cleanSubtitleLines(payload.body)
  };
}

async function getVideoTranscript(bvid) {
  const info = await getVideoInfo(bvid);
  const pages = info.pages?.length ? info.pages : [{ cid: info.cid, page: 1, part: info.title, duration: info.duration }];
  const parts = [];
  for (let i = 0; i < pages.length; i++) {
    parts.push(await getPageTranscript(bvid, info.aid, pages[i], i + 1));
    await sleep(140);
  }
  return {
    bvid,
    aid: info.aid,
    title: info.title,
    desc: info.desc || '',
    duration: info.duration || 0,
    owner: info.owner || {},
    pubdate: Number(info.pubdate || 0),
    ctime: Number(info.ctime || 0),
    stat: info.stat || {},
    pages,
    parts,
    hasSubtitle: parts.some((part) => part.lines.length > 0)
  };
}

function normalizeMediaUrl(url) {
  if (!url) return '';
  return String(url).startsWith('//') ? `https:${url}` : String(url);
}

function collectDashAudio(data) {
  const list = [];
  const add = (item, kind = 'dash') => {
    if (!item) return;
    const url = normalizeMediaUrl(item.baseUrl || item.base_url || item.url);
    if (!url) return;
    const backups = (item.backupUrl || item.backup_url || []).map(normalizeMediaUrl).filter(Boolean);
    list.push({
      url,
      backupUrls: backups,
      bandwidth: Number(item.bandwidth || 0),
      id: Number(item.id || 0),
      codecs: item.codecs || '',
      kind
    });
  };
  for (const item of data?.dash?.audio || []) add(item, 'dash');
  for (const item of data?.dash?.dolby?.audio || []) add(item, 'dolby');
  add(data?.dash?.flac?.audio, 'flac');
  return list;
}

async function getAudioSource(bvid, cid) {
  const params = { bvid, cid, qn: 64, fnver: 0, fnval: 4048, fourk: 1, platform: 'pc' };
  let data = null;
  let signedError = null;
  try {
    data = await biliWbi('/x/player/wbi/playurl', params);
  } catch (error) {
    signedError = error;
  }
  if (!data) {
    const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
    const fallback = await fetchJson(`https://api.bilibili.com/x/player/playurl?${qs}`, {}, 1);
    if (fallback.code !== 0) throw signedError || biliError(fallback);
    data = fallback.data;
  }

  const audio = collectDashAudio(data)
    .filter((x) => x.url)
    .sort((a, b) => {
      const aa = a.bandwidth > 0 ? a.bandwidth : Number.MAX_SAFE_INTEGER;
      const bb = b.bandwidth > 0 ? b.bandwidth : Number.MAX_SAFE_INTEGER;
      return aa - bb;
    });
  if (audio.length) {
    return {
      bvid,
      cid: Number(cid),
      url: audio[0].url,
      backupUrls: audio[0].backupUrls,
      bandwidth: audio[0].bandwidth,
      codec: audio[0].codecs,
      kind: audio[0].kind,
      duration: Number(data?.timelength || 0) / 1000
    };
  }

  const durl = data?.durl || [];
  if (durl.length && durl[0]?.url) {
    return {
      bvid,
      cid: Number(cid),
      url: normalizeMediaUrl(durl[0].url),
      backupUrls: (durl[0].backup_url || []).map(normalizeMediaUrl).filter(Boolean),
      bandwidth: 0,
      codec: '',
      kind: 'muxed',
      duration: Number(durl[0].length || data?.timelength || 0) / 1000
    };
  }
  throw new Error('没有取得可用于 Whisper 的视频音轨。该视频可能受地区、会员或版权限制。');
}


const NATIVE_HOST = 'com.bilisum.local';
const EXPECTED_HOST_VERSION = chrome.runtime.getManifest().version;
let nativePort = null;
let nativeSeq = 0;
const nativePending = new Map();

function disconnectNative(reason = '本地组件已断开') {
  nativePort = null;
  for (const { reject, timer } of nativePending.values()) {
    clearTimeout(timer);
    reject(new Error(reason));
  }
  nativePending.clear();
}

function connectNative() {
  if (nativePort) return nativePort;
  const port = chrome.runtime.connectNative(NATIVE_HOST);
  nativePort = port;
  port.onMessage.addListener((message) => {
    const id = String(message?.id ?? '');
    const pending = nativePending.get(id);
    if (!pending) return;
    nativePending.delete(id);
    clearTimeout(pending.timer);
    if (message?.ok) pending.resolve(message.result);
    else pending.reject(new Error(message?.error || '本地组件返回错误'));
  });
  port.onDisconnect.addListener(() => {
    const reason = chrome.runtime.lastError?.message || '本地组件连接已关闭';
    if (nativePort === port) disconnectNative(reason);
  });
  return port;
}

function nativeRequest(method, params = {}, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    let port;
    try { port = connectNative(); }
    catch (error) { reject(new Error(`无法启动 BiliSum 本地组件：${error.message || error}`)); return; }
    const id = String(++nativeSeq);
    const timer = setTimeout(() => {
      nativePending.delete(id);
      reject(new Error('本地处理超时，请在设置页运行环境检测。'));
    }, timeoutMs);
    nativePending.set(id, { resolve, reject, timer });
    try { port.postMessage({ id, method, params }); }
    catch (error) {
      clearTimeout(timer); nativePending.delete(id);
      reject(new Error(`无法连接 BiliSum 本地组件：${error.message || error}`));
    }
  });
}

async function checkBackend() {
  try {
    const data = await nativeRequest('health', {}, 8000);
    return { ok: true, ...data, version_ok: String(data.version || '') === EXPECTED_HOST_VERSION };
  } catch (error) {
    return { ok: false, reason: error.message || String(error) };
  }
}

async function startBackendJob(kind, payload) {
  const settings = await getSettings();
  const params = kind === 'notes'
    ? { ...payload, model: payload?.model || settings.model || 'auto', parallelism: payload?.parallelism || settings.modelParallelism || 'auto' }
    : { ...payload, model: payload?.model || settings.asrModel || 'auto', device: payload?.device || settings.asrDevice || 'auto', language: payload?.language ?? settings.asrLanguage ?? '' };
  const method = kind === 'notes' ? 'jobs.start.notes' : 'jobs.start.transcription';
  return await nativeRequest(method, params, 15000);
}

async function getBackendJob(jobId) { return await nativeRequest('jobs.get', { job_id: jobId }, 10000); }
async function getBackendJobResultPage(jobId, offset = 0, limit = 400) { return await nativeRequest('jobs.result.page', { job_id: jobId, offset, limit }, 10000); }
async function beginBatchLease(leaseId = '') { return await nativeRequest('batch.begin', { lease_id: leaseId, ttl_sec: 180 }, 10000); }
async function heartbeatBatchLease(leaseId) { return await nativeRequest('batch.heartbeat', { lease_id: leaseId, ttl_sec: 180 }, 10000); }
async function endBatchLease(leaseId) { return await nativeRequest('batch.end', { lease_id: leaseId }, 10000); }
async function saveStatus() { return await nativeRequest('save.status', {}, 10000); }
async function chooseSaveDirectory() { return await nativeRequest('save.choose', {}, 10000); }
async function saveNote(payload) { return await nativeRequest('save.note', payload || {}, 30000); }
async function setSaveDirectory(directory) { return await nativeRequest('save.set', { directory }, 10000); }
async function clearSaveDirectory() { return await nativeRequest('save.clear', {}, 10000); }
async function checkUpdate() { return await nativeRequest('updates.check', {}, 20000); }
async function stageUpdate() { return await nativeRequest('updates.stage', {}, 120000); }
async function applyUpdate(stagingPath) { return await nativeRequest('updates.apply', { staging_path: stagingPath }, 15 * 60 * 1000); }

async function surfaceUpdateInfo(info) {
  if (info?.available) {
    await chrome.action.setBadgeText({ text: 'NEW' });
    await chrome.action.setBadgeBackgroundColor({ color: '#303033' });
    await chrome.action.setTitle({ title: `BiliSum · 可更新到 ${info.latest_version || ''}` });
  } else {
    await chrome.action.setBadgeText({ text: '' });
    await chrome.action.setTitle({ title: 'BiliSum' });
  }
}

async function runScheduledUpdateCheck() {
  const settings = await getSettings();
  if (settings.updateMode === 'off') { await surfaceUpdateInfo(null); return; }
  try {
    const info = await checkUpdate();
    await chrome.storage.local.set({ updateInfo: info, updateCheckedAt: Date.now(), updateError: '' });
    await surfaceUpdateInfo(info);
    if (settings.updateMode === 'auto' && info?.available) {
      const local = await checkBackend();
      if (local?.batch_active || Number(local?.queues?.notes || 0) > 0 || Number(local?.queues?.transcription || 0) > 0 || Number(local?.parallelism?.notes_active || 0) > 0) return;
      const staged = await stageUpdate();
      if (staged?.staged && staged?.staging_path) {
        await applyUpdate(staged.staging_path);
        setTimeout(() => chrome.runtime.reload(), 1200);
      }
    }
  } catch (error) {
    await chrome.storage.local.set({ updateError: error.message || String(error), updateCheckedAt: Date.now() });
  }
}

chrome.runtime.onInstalled.addListener((details) => {
  chrome.alarms.create('bilisum-update-check', { delayInMinutes: 10, periodInMinutes: 24 * 60 });
  if (details.reason === 'install') chrome.tabs.create({ url: chrome.runtime.getURL('setup.html') });
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create('bilisum-update-check', { delayInMinutes: 10, periodInMinutes: 24 * 60 });
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'bilisum-update-check') runScheduledUpdateCheck();
});
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());

function notifySoftNavigation(details) {
  if (!details || details.frameId !== 0) return;
  const url = String(details.url || '');
  if (!/^https:\/\/(?:www|space)\.bilibili\.com\//i.test(url)) return;
  chrome.tabs.sendMessage(details.tabId, { type: 'bilisum:navigation', url }).catch(() => {});
}

chrome.webNavigation.onHistoryStateUpdated.addListener(notifySoftNavigation);
chrome.webNavigation.onReferenceFragmentUpdated.addListener(notifySoftNavigation);

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === 'settings:get') return sendResponse({ ok: true, data: await getSettings() });
      if (msg.type === 'settings:set') { await chrome.storage.local.set(msg.settings || {}); return sendResponse({ ok: true, data: await getSettings() }); }
      if (msg.type === 'local:check') return sendResponse({ ok: true, data: await checkBackend() });
      if (msg.type === 'local:notes:start') return sendResponse({ ok: true, data: await startBackendJob('notes', msg.payload || {}) });
      if (msg.type === 'local:asr:start') return sendResponse({ ok: true, data: await startBackendJob('asr', msg.payload || {}) });
      if (msg.type === 'local:job') return sendResponse({ ok: true, data: await getBackendJob(String(msg.jobId || '')) });
      if (msg.type === 'local:jobResultPage') return sendResponse({ ok: true, data: await getBackendJobResultPage(String(msg.jobId || ''), Number(msg.offset || 0), Number(msg.limit || 400)) });
      if (msg.type === 'local:batchBegin') return sendResponse({ ok: true, data: await beginBatchLease(String(msg.leaseId || '')) });
      if (msg.type === 'local:batchHeartbeat') return sendResponse({ ok: true, data: await heartbeatBatchLease(String(msg.leaseId || '')) });
      if (msg.type === 'local:batchEnd') return sendResponse({ ok: true, data: await endBatchLease(String(msg.leaseId || '')) });
      if (msg.type === 'save:status') return sendResponse({ ok: true, data: await saveStatus() });
      if (msg.type === 'save:choose') return sendResponse({ ok: true, data: await chooseSaveDirectory() });
      if (msg.type === 'save:set') return sendResponse({ ok: true, data: await setSaveDirectory(String(msg.directory || '')) });
      if (msg.type === 'save:note') return sendResponse({ ok: true, data: await saveNote(msg.payload || {}) });
      if (msg.type === 'save:clear') return sendResponse({ ok: true, data: await clearSaveDirectory() });
      if (msg.type === 'update:check') { const info = await checkUpdate(); await surfaceUpdateInfo(info); return sendResponse({ ok: true, data: info }); }
      if (msg.type === 'update:install') {
        const staged = await stageUpdate();
        if (!staged?.staged || !staged?.staging_path) return sendResponse({ ok: true, data: staged });
        const applied = await applyUpdate(staged.staging_path);
        setTimeout(() => chrome.runtime.reload(), 1200);
        return sendResponse({ ok: true, data: { ...staged, ...applied } });
      }
      if (msg.type === 'bili:nav') return sendResponse({ ok: true, data: await getNavStatus() });
      if (msg.type === 'bili:allVideos') return sendResponse({ ok: true, data: await getAllVideos(String(msg.mid)) });
      if (msg.type === 'bili:transcript') return sendResponse({ ok: true, data: await getVideoTranscript(String(msg.bvid)) });
      if (msg.type === 'bili:audioSource') return sendResponse({ ok: true, data: await getAudioSource(String(msg.bvid), Number(msg.cid)) });
      if (msg.type === 'bili:videoInfo') return sendResponse({ ok: true, data: await getVideoInfo(String(msg.bvid)) });
      return sendResponse({ ok: false, error: 'Unknown message type' });
    } catch (error) {
      return sendResponse({ ok: false, error: error.message || String(error), code: error.code });
    }
  })();
  return true;
});
