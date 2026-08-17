# BiliSum

BiliSum 是一个面向 Bilibili 课程与长视频的本地笔记工具。它优先读取 B 站字幕；字幕缺失时可调用本机 Whisper 听写，再由本机 Ollama 模型整理成结构化笔记。

## 功能

- 普通视频、合集页与 UP 主空间页浮窗
- B 站字幕优先，无字幕时自动 Whisper 听写
- 课程笔记：概览、知识框架、核心内容、定义、逻辑、例子、易混点、时间轴与复习点
- 视频内问答，仅基于当前字幕/听写文本
- UP 主与合集批量整理，支持稳定的双流水线、暂停、断点续跑、失败重试与缓存
- 同一批次合并为一个 TXT
- 一键复制；可选择并记住本地保存目录
- Windows / macOS / Linux 自检式安装：已有组件直接复用，缺什么补什么
- 便携版可选更新：关闭 / 仅提示 / 自动安装；活动批次期间不会应用更新

## 本地架构

浏览器扩展不开放 BiliSum 自己的 HTTP 服务。扩展通过 Chrome Native Messaging 与本机 host 使用 stdin/stdout 通信；Native Messaging manifest 只允许登记的扩展 ID 连接。

本地 host 负责：

1. 调度笔记整理与 Whisper 听写；
2. 调用本机 Ollama；
3. 缓存听写与整理结果；
4. 保存 TXT；
5. 检查、校验和应用便携版更新。

批量任务默认最多同时推进两条视频流水线；Whisper 仍使用独立队列，本地整理模型的真实并发会依据机器资源保守限制。每完成一条视频都会写入批次断点，浏览器重启后可继续。

`.runtime/` 保存运行环境、模型缓存、配置和用户缓存，不进入 Git，也不会被便携版更新覆盖。

## 兼容性

- 浏览器：Chrome / Edge / Chromium 系浏览器（Manifest V3 + Native Messaging）。
- Whisper 依赖的 CTranslate2 预编译 Python wheel 覆盖 Windows x86-64、macOS x86-64/ARM64、Linux x86-64/AArch64。Windows ARM64 目前不作为保证可用的平台。
- 安装器按内存自动选择 qwen3.5:0.8b / 2b / 4b，也会优先复用本机已有的兼容模型。

## 安装

### Windows

1. 解压发布包到固定目录，例如 `D:\BiliSum`。
2. 双击 `SETUP_WINDOWS.cmd`。
3. Chrome / Edge 打开扩展管理页并启用开发者模式。
4. 选择“加载已解压的扩展程序”，加载 `extension/` 目录。

### macOS

1. 解压到固定目录。
2. 运行 `SETUP_MACOS.command`。
3. 在 Chromium 系浏览器中加载 `extension/`。

若尚未安装 Ollama，macOS 安装器会提示先安装官方应用后重跑。

### Linux

```bash
./SETUP_LINUX.sh
```

随后在 Chromium 系浏览器中加载 `extension/`。

## 备份与旧版迁移

设置页可以导出/导入本地备份，覆盖设置、单课笔记、批次断点和索引。导入采用合并方式。由于早期 5.0.x 开发版没有固定扩展 ID，首次迁移到 5.2.x 前应先保存正在运行的批次 TXT；若还需要保留旧版缓存，可在旧版扩展的设置页 DevTools Console 中执行：

```js
chrome.storage.local.get(null).then(d => { const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([JSON.stringify(d)],{type:'application/json'})); a.download='BiliSum-legacy-backup.json'; a.click(); });
```

随后在新版本“备份与迁移”中导入该 JSON。正常的 5.2.x 以后内置更新不需要这样迁移。

## 更新

设置页提供三种便携版更新策略：

- `不检查`
- `仅提示`（默认）
- `自动安装`

更新器读取 GitHub Release，下载对应便携包并校验发布资产的 SHA-256 digest。更新只替换程序文件，保留 `.runtime/`。源码 Git checkout 会拒绝内置覆盖，开发环境应使用正常的 Git 工作流。

Chrome Web Store 版本可在后续发布；商店版应使用浏览器原生更新，不使用便携版文件覆盖机制。源码版本更新后，`VERSION` 变更会触发 GitHub Actions 自动构建并发布对应 Release。

## 开发

```bash
python scripts/security_check.py
python -m unittest discover -s tests -v
python scripts/build_release.py
```

JS 静态检查：

```bash
node --check extension/background.js
node --check extension/content.js
node --check extension/options.js
node --check extension/setup.js
```

架构与发布细节见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 和 [`docs/RELEASING.md`](docs/RELEASING.md)。

## 数据与隐私

- 不需要 OpenAI / Gemini / Groq API Key。
- 字幕、听写缓存、整理缓存和保存的笔记默认位于本机。
- BiliSum 不采集分析数据，不内置遥测。
- Bilibili 请求使用当前浏览器会话；不要把 Cookie、账号密码或 `.runtime/` 提交到仓库。

## 许可

当前仓库使用保留所有权利的许可证。若未来计划接受外部分发或二次开发，可再切换到明确的开源许可证。
