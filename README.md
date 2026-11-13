# Moyu Anki Overlay / 摸鱼复习条

A minimal always-on-top review pill for the desktop, powered by Anki’s official scheduler — quiet card review while you work or sit in meetings.

桌面极简胶囊复习条，用 Anki 官方调度刷卡——开会、写代码时也能「低调」复习。

By default only the **question** is shown. Hover or press a shortcut to reveal the answer, then grade with number keys / Space. Reviews are written into your current Anki collection and sync normally to AnkiWeb.

默认只显示**问题**；悬停或快捷键显示答案；再用数字键 / 空格评分。复习写入当前集合，可正常同步 AnkiWeb。

> **Requires Anki to be running** (main window may be minimized). Primarily tested on **macOS**; Windows works too (change the font in Settings).
>
> **需要 Anki 保持运行**（主窗口可最小化）。以 **macOS** 为主；Windows 也可使用（请在设置里改成系统字体）。

---

## Features / 功能

| | English | 中文 |
| --- | --- | --- |
| Overlay | Frameless, always-on-top, translucent white pill | 无边框、置顶、半透明白胶囊 |
| Question-first | Collapsed state shows front-side plain text only | 收起时只显示正面纯文本 |
| Reveal | Hover, or keyboard shortcuts | 悬停或快捷键看答案 |
| Grading | Digits / Space after reveal (configurable) | 显示答案后用数字键 / 空格评分（可配置） |
| Deck | Follows the deck currently selected in Anki | 跟 Anki 里当前选中的牌组 |
| Plain text | Strips HTML, `[[type:…]]`, ruby tags, etc. | 去掉 HTML、`[[type:…]`、音标标签等 |
| Settings | Appearance, fonts, shortcuts in a GUI | 外观、字体、快捷键图形设置 |

**Not in v1 / 首版不做：** images / audio, cloze highlighting, full template rendering, standalone app without Anki.

---

## Requirements / 环境

- Anki **25.09+** (verified on **Anki 26.09** / macOS)
- No extra Python/Qt install — use Anki’s bundled runtime
- Prefer exiting the main Reviewer before using the overlay (avoids dual scheduling; overlay auto-pauses when you enter main review)

- Anki **25.09+**（在 **Anki 26.09** / macOS 验证）
- 无需额外依赖
- 建议先退出主界面「复习」再使用悬浮条（进入主界面复习时会自动暂停）

---

## Install / 安装

### A. From AnkiWeb（推荐，上架后）

1. Open Anki → **Tools → Add-ons → Get Add-ons…**
2. Paste the code from the add-on’s AnkiWeb page
3. Restart Anki

1. Anki → **工具 → 插件 → 获取插件…**
2. 粘贴 AnkiWeb 页面上的插件代码
3. 重启 Anki

### B. From this repo / 从本仓库

1. Download ZIP from GitHub → unzip (e.g. `moyu-anki-overlay`)
2. Anki → **Tools → Add-ons → View Files** → opens `addons21`
3. Copy the folder in as `moyu_anki_overlay` (must contain `__init__.py` at the top level):

1. GitHub 下载 ZIP 并解压
2. **工具 → 插件 → 查看文件**，打开 `addons21`
3. 放入并命名为 `moyu_anki_overlay`（顶层要有 `__init__.py`）：

```text
addons21/moyu_anki_overlay/
  __init__.py
  overlay.py
  review_controller.py
  config_dialog.py
  config.json
  manifest.json
  ...
```

4. Fully quit and restart Anki  
5. Under **Tools** you should see **Show/Hide Moyu Overlay** and **Moyu Overlay Settings…**

4. **完全退出再打开 Anki**  
5. **工具** 菜单应出现「显示/隐藏摸鱼复习条」「摸鱼复习条设置…」

### C. Symlink (dev) / 符号链接（开发）

```bash
ln -sfn /path/to/moyu-anki-overlay \
  "$HOME/Library/Application Support/Anki2/addons21/moyu_anki_overlay"
```

Windows (admin PowerShell):

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\Anki2\addons21\moyu_anki_overlay" `
  -Target "D:\path\to\moyu-anki-overlay"
```

---

## Usage / 使用

1. Start Anki and select a deck with due cards  
2. If auto-show is on, a pill appears near the top; otherwise **Tools → Show/Hide Moyu Overlay** (default `Ctrl+Shift+M` / `⌃⇧M`)  
3. **Reveal answer:** hover, or press reveal shortcuts (default Space / Enter), or a grade digit (also reveals when hidden)  
4. **Grade** (answer visible): `1` Again · `2` Hard · `3` Good · `4` Easy; Space/Enter grades per “After reveal” setting (default Good)  
5. After grading, if the cursor stays on the pill, the next answer stays hidden until you **leave and re-enter**  
6. Drag the pill to reposition (saved in config)

1. 打开 Anki，选中有到期卡的牌组  
2. 若开启自动显示，顶部附近会出现胶囊；否则用 **工具 → 显示/隐藏摸鱼复习条**  
3. **看答案：** 悬停，或按显示答案快捷键，或按评分数字键（未显示时也会先显示）  
4. **评分：** `1` 重来 · `2` 困难 · `3` 良好 · `4` 简单；空格/回车按「显示后再按」执行（默认良好）  
5. 答完后若鼠标还在条上，下一题不会立刻露答案；**移开再移回来**后恢复  
6. 可拖动改位置（写入配置）

```text
Question → Space/hover to reveal → 1–4 to grade → move mouse away → next card
看到问题 → 空格/悬停看答案 → 1–4 评分 → 移开鼠标 → 下一题
```

---

## Settings / 设置

**Tools → Moyu Overlay Settings…** or **Tools → Add-ons → Moyu → Config**

**工具 → 摸鱼复习条设置…** 或 **工具 → 插件 → 摸鱼复习条 → 配置**

| Group / 分组 | Option / 选项 | Meaning / 含义 |
| --- | --- | --- |
| Appearance | Opacity | Pill transparency / 透明度 |
| Appearance | Max chars / max width | Truncate long text / 限制过长文本 |
| Appearance | Show/Hide hotkey | Global toggle / 全局显示隐藏 |
| Appearance | Hug content width | Frame shrinks to text / 外框随文字收缩 |
| Appearance | Auto-show on start | Show after profile load / 启动后自动显示 |
| Font | Family / size | On Windows prefer a system CJK font / Windows 建议系统中文字体 |
| Reveal | Shortcuts A / B | Default Space, Enter / 默认空格、回车 |
| Reveal | After reveal | Grade when A/B pressed while answer shown / 答案已显示时 A/B 的评分 |
| Grade | Again/Hard/Good/Easy | Digit (etc.) shortcuts / 数字键等 |

---

## Notes / 注意事项

1. Anki must be running for reviews to be saved and synced. / Anki 必须在运行。  
2. Shortcuts only work when Anki can receive keys; hovering the pill grabs focus when possible. / 快捷键需 Anki 能收到按键；悬停条上时会尽量抓取焦点。  
3. Don’t run main Reviewer and overlay together; overlay hides during main review. / 不要与主界面复习同时进行。  
4. Content is plain text of rendered front/back — no full templates, images, or audio. / 仅为渲染后的正背面纯文本。

---

## Publish to AnkiWeb / 发布到 AnkiWeb

Official docs: [Sharing Add-ons](https://docs.ankiweb.net/addons/sharing)

1. Build a `.ankiaddon` (zip of **folder contents**, not the folder itself; no `__pycache__`):

```bash
cd /path/to/moyu-anki-overlay
./pack-ankiaddon.sh
# → dist/moyu_anki_overlay.ankiaddon
```

2. Log in at [AnkiWeb](https://ankiweb.net/)  
3. Open [Share Add-on](https://ankiweb.net/shared/upload)  
4. Fill **Title** (≤80 chars), optional tags / support URL, supported Anki version branches, and a **Description** (Markdown/HTML OK — you can paste CN+EN)  
5. Upload the `.ankiaddon` file  
6. After approval listing, users install via **Get Add-ons…** with the numeric code on your add-on page  

Updates: upload a new `.ankiaddon` on the same add-on page (same code). There is **no public upload API** — use the website.

中文摘要：用脚本打出 `.ankiaddon` → 登录 AnkiWeb → [上传页](https://ankiweb.net/shared/upload) 填标题与说明并上传 → 用户用插件代码安装。更新时在同一插件页重新上传即可。

---

## Project layout / 项目结构

```text
moyu-anki-overlay/
├── __init__.py
├── overlay.py
├── review_controller.py
├── config_dialog.py
├── config.json
├── config.md
├── manifest.json
├── pack-ankiaddon.sh      # build .ankiaddon for AnkiWeb
└── README.md
```

---

## Dev / 开发

- Restart Anki after code changes  
- `moyu_debug.log` may appear locally (gitignored)  
- Do not commit `meta.json` (user config / position)

---

## License / 许可

Personal/learning tool. Free to modify and use; if you redistribute, please keep attribution.

个人学习工具，可自由修改使用；公开分发请保留来源说明。

---

## Feedback / 反馈

Issues welcome: install failures, shortcut issues, text-cleaning edge cases.

欢迎提 Issue。
