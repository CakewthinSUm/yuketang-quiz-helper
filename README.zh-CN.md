# yuketang-quiz-helper

[English](README.md) | **简体中文**

一个 **Hermes Agent 技能**，用来完成雨课堂（`changjiang.yuketang.cn`）里「题目全是 PPT 切图」的在线练习与课件练习。

这类页面的 **DOM 里没有题干文字**：题干和每个选项都是 `background-image` 切图，`page_info()` / `get_page_text` 只能读到 "A B C D"。所以「读页面文本然后作答」这条路是不通的。本技能把真正能跑通的那条链路固定下来：

```
读 DOM 结构  →  下载切图  →  拼成可读长图
   →  从图上解题  →  按节奏点击选项  →  校验  →  交卷
```

## 这个页面难在哪

它会在几个具体环节上卡住天真的自动化，每一步都有对应的解法：

- `click_at_xy(x, y)` 收的是 **视口 CSS 像素**（CDP `Input.dispatchMouseEvent`），不是 0–1000 的归一化坐标。按百分比换算会静默点错位置。
- `scrollIntoView` 必须用 `behavior: 'instant'`，否则量到的矩形在你点击时已经过期，答案会落到相邻题上。
- 节奏要按**两次点击之间**的间隔算，而不是「每题 sleep 7 秒」——测量、校验本身要吃掉 1–2 秒，无脑 sleep 会把 7 秒的节奏拉成约 9 秒。
- 切图文件名必须逐题从 `data-background` 读；`k` 的起始值每题不同（4 或 5），手工拼 URL 必然错位。
- 切图来自 CDN，不带会话 cookie 会返回 403，所以下载脚本支持 `--cookie-json`，直接喂 `cdp('Network.getCookies', urls=[...])` 的原始输出。
- 有些部署把试卷放在跨源 `<iframe>` 里，技能里写了 `Page.getFrameTree` → `createIsolatedWorld` → `Runtime.evaluate(contextId=...)` 的兜底路线。

## 依赖

- Hermes Agent，且带 `browser_exec` 工具（独立 profile 的 headless Chromium）。
- Python 3 + Pillow（`pip install pillow`），给 `scripts/compose_pillow.py` 用。
  Windows 用户可以完全不装 Pillow，改用 `scripts/compose_windows.ps1`（走 System.Drawing）。
- **该浏览器 profile 里**有有效的雨课堂登录态。技能不碰任何凭证：一旦出现登录页，它会截图二维码交给人类用雨课堂 App 扫。

如果你用 Claude Code / Codex / OpenCode / Gemini CLI，见下面[兼容性](#兼容性)一节——只需要多装一个 `playwright`，其余不动。

## 安装

作为 Hermes 用户级技能：

```bash
git clone https://github.com/CakewthinSUm/yuketang-quiz-helper.git \
  ~/.hermes/skills/productivity/yuketang-quiz-helper
```

然后直接跟 agent 说：*「把雨课堂那份练习帮我做了」* / *「几秒一道题地刷完」*。触发词：`雨课堂` / `yuketang` / `studentQuiz` / `课件练习` / `随堂练习`。

也可以只当纯文档读：除了代码片段里用到的四个辅助函数（`js`、`click_at_xy`、`page_info`、`capture_screenshot`），整套流程不依赖 Hermes 特有实现——换成 Playwright / Puppeteer 的等价 API，DOM 知识部分仍然成立。

## 兼容性

`SKILL.md`、`references/`、`scripts/` 都是按 **Agent Skills 开放标准**写的，所以流程和 DOM 知识可以直接搬到别的 agent。真正跟 Hermes 绑定的只有四个浏览器辅助函数（`js`、`click_xy`、`page_info`、`capture_screenshot`）——`scripts/playwright_browser.py` 用 Playwright 实现了同名同语义的版本，代码片段可以原样照跑。

| Agent | 原生读 `SKILL.md`？ | 装到哪 | 自带浏览器 | 额外要做 |
|---|---|---|---|---|
| **Hermes Agent** | 是（原生格式） | `~/.hermes/skills/<分类>/yuketang-quiz-helper/` | 有（`browser_exec`） | 无 |
| **Claude Code** | 是（Agent Skills 标准） | `~/.claude/skills/`（个人）或 `.claude/skills/`（项目） | 无 | 装 Playwright shim 或浏览器 MCP |
| **Codex CLI / ChatGPT 桌面端** | 是（同一标准） | `$HOME/.agents/skills/` 或仓库内 `.agents/skills/` | 无 | 同上；仓库已带 `agents/openai.yaml`（显示名、调用策略） |
| **OpenCode** | 是 | `.opencode/skills/<id>/SKILL.md` | 无 | 同上 |
| **Gemini CLI** | 是 | `~/.gemini/skills/` 或 `~/.agents/skills/` | 无 | 同上 |
| **其他**（Cursor 规则、Aider、纯聊天） | 否 | 贴进 `AGENTS.md` / `CLAUDE.md` | 无 | 把四个辅助函数换成自己的 |

`~/.agents/skills/` 同时是 Codex 和 Gemini CLI 的用户级目录，克隆一次两边都能用。

```bash
pip install playwright && playwright install chromium
```

```python
from playwright_browser import Browser          # scripts/playwright_browser.py

with Browser(profile_dir="~/.cache/yuketang-profile") as b:
    b.goto("https://changjiang.yuketang.cn")
    b.js(JS_STRUCT); b.click_xy(412, 655); b.dump_cookies("cookies.json")
```

一个必须先知道的坑：这些选项是 `background-image` 的 div，而多数 MCP 浏览器服务是按元素引用来点的，不是按坐标——在这类页面上按元素点并不可靠。各 agent 的安装路径、辅助函数对照表和 MCP 方案的取舍，都在 [`references/other-agents.md`](references/other-agents.md)。

## 目录结构

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 主流程：取样 → 下载 → 拼图 → 解题 → 点击 → 校验 → 交卷 |
| `references/page-structure.md` | DOM 图谱、取样脚本、整张答题卡核对、交卷按钮探测 |
| `references/click-pacing.md` | 点击模板、节奏控制、重试与校验循环 |
| `references/other-agents.md` | Claude Code / Codex / OpenCode / Gemini CLI 的安装路径与辅助函数对照 |
| `scripts/fetch_quiz_images.py` | 并发下载切图（带 UA，可选带 cookie） |
| `scripts/compose_pillow.py` | 把切图拼成 2 题一张的可读图（跨平台） |
| `scripts/compose_windows.ps1` | 同上，走 System.Drawing，零依赖 |
| `scripts/playwright_browser.py` | 给非 Hermes agent 的 `js` / `click_xy` / `page_info` / `capture_screenshot` 便携实现 |
| `scripts/make_fixtures.py` | 生成复刻题库页面，用于无账号自测 |
| `agents/openai.yaml` | 可选的 Codex/ChatGPT 技能元数据（显示名、调用策略） |

## 已验证的行为

- 下载与拼图：20 张合成切图 → `downloaded 20 / 20`，拼出的图里 `No.N` 题号标记与选项清晰可读。
- 点击循环：在复刻真实 DOM 的页面（iframe + `.problem_item` + `data-background` + `[data-role=problembullet]`）上，像素坐标点击每次都命中目标选项，`chosen` 读回为 `[['C'],['A'],['B']]`，答题卡计数到 `(3 / 3)`。
- 可移植性：同样三段代码**未作任何修改**，改由 `scripts/playwright_browser.py`（Playwright 1.65，持久化 profile）执行，结果完全一致——流程并不绑死 Hermes。

## 无账号自测

`scripts/make_fixtures.py` 能生成一个复刻真实 DOM 的本地页面（iframe + `.problem_item` + `.pptimg[data-background]` + `[data-role=problembullet]` + 会实时更新的答题卡），题目是合成切图、答案就写在图里。这样不用登录、不用真试卷也能把整条链路跑一遍：

```bash
python3 scripts/make_fixtures.py ./fixture --questions 4
cd ./fixture && python3 -m http.server 8765 --bind 127.0.0.1   # 必须 HTTP，file:// 读不到 iframe 文档
# 然后拿 SKILL.md 的片段去跑 http://127.0.0.1:8765/host.html
```

实测：4 题 → 每题取到 5 张切图，`downloaded 20 / 20`，拼成两张可读图；从图上读出的答案（A/B/C/D）按坐标点击全部命中，答题卡到 `(4 / 4)`。

## 使用边界

为**自己的练习**和课件巩固而做。**不要**用在有监考的考试、计分考核，或任何规则禁止自动化的场合——技能本身在交卷前一定会停下来问，正因为最后那一下不可逆。用它产生的后果由你负责。

## 许可证

MIT，见 [LICENSE](LICENSE)。维护者 [@CakewthinSUm](https://github.com/CakewthinSUm)。
