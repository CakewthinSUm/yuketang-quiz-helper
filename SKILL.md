---
name: yuketang-quiz-helper
description: "Answer 雨课堂 PPT-image quizzes with paced browser clicks."
version: 0.2.0
author: CakewthinSUm, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [yuketang, 雨课堂, quiz, browser, vision]
    related_skills: [computer-use]
---

# 雨课堂答题助手

自动完成雨课堂（`changjiang.yuketang.cn`、`v2/web/studentQuiz`）的在线练习与试卷。题目是 PPT 切图、DOM 里没有文字，必须走「读结构 → 下载切图 → 拼可读图 → 识别作答 → 按节奏点击 → 校验 → 交卷」。本技能把这条链路和踩过的坑固定下来。**不负责登录**：浏览器里没有有效会话时停下问用户。

## When to Use

- 用户提到雨课堂 / yuketang / `studentQuiz` / 课件练习 / 随堂练习 / 试卷
- 「把浏览器里这份试卷做完」「几秒一道题地刷完」

不要用于：需要用户登录、上传作业、需要摄像头监考的考试（这类要先确认规则，别自动作答）。

## 核心事实（先看这段，它决定后面所有做法）

- 页面在 `iframe` 内，题目容器是 `.problem_item`（每题一个，默认 360×600）。
- 题干与选项都是 `.pptimg`（题干通常还带 `notBullet`，选项不一定，所以选择器只认 `.pptimg`，按 DOM 顺序取：第 1 张是题干，其后是 A–D），地址取自 `data-background`，**不要自己拼文件名**：`slide_{n}_{k}_<时间戳>.png` 里 k 的起点每题不同（4 或 5），必须逐题从页面取。
- 选项标号是 `[data-role=problembullet][data-label="A"]`，已选中项 class 含 `chosen`。
- 顶部文本含 `剩余答题时间` 与 `答题卡 (已答/总数)`；底部按钮 `去交卷`。
- 只读结构允许用 `js()`（这类页面 `page_info()` 读不出题干）；**选项必须真实点击** `click_at_xy(x, y)`，不要用 JS 改 class 造假。
- `click_at_xy` 吃的是**视口 CSS 像素**，不是 0–1000 归一化坐标；换算只到 `iframe rect + 选项 rect` 为止。
- 题图原分辨率低（题干约 486×300、选项约 422×90），拼图放 1.6 倍正好贴近原生像素，别盲目放大。

## Procedure

### 1. 打开页面并确认已登录

用 `browser_exec`（同一 `session` 名贯穿整个任务，变量不跨调用保留，把中间结果写进 `$BH_AGENT_WORKSPACE` 下的 JSON）。

```python
# 打开雨课堂练习页
try:
    info = page_info()
except Exception:
    new_tab("https://changjiang.yuketang.cn")
    wait_for_load()
    info = page_info()
print(info)
```

**完成判据**：`page_info()` 显示的是练习页而不是登录页；是登录页就停下，让用户自己扫码登录（密码/验证码永远由用户输入）。

登录这事有个前提：我自己的浏览器是**独立的 headless Chromium**（profile 在 `~/.hermes/cache/browser/chromium/<hash>`），不是用户本机上的浏览器（本机 Chrome 的登录态不在这个 profile 里）。所以第一次跑雨课堂要现场登录，做法是：

```python
# 提供登录二维码给用户扫
print(capture_screenshot())
```

把截图路径用 `MEDIA:<path>` 发给用户，让他用雨课堂 App 扫码；扫完再 `wait_for_load()` + `page_info()` 复核。cookie 存在该 profile 里，只要不清理 `~/.hermes/cache/browser/` 就一直有效。

### 2. 取样：切图地址、选项、已选状态

```python
JS_STRUCT = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const items = [...d.querySelectorAll('.problem_item')];
  return {
    header: d.body.innerText.slice(0, 40).replace(/\\n/g, ' '),
    count: items.length,
    items: items.map((it, i) => ({
      idx: i + 1,
      imgs: [...it.querySelectorAll('.pptimg')].map(e => e.getAttribute('data-background')),
      bullets: [...it.querySelectorAll('[data-role=problembullet]')].map(b => ({
        label: b.getAttribute('data-label'),
        chosen: b.className.includes('chosen')
      }))
    }))
  };
})()"""
res = js(JS_STRUCT)
print(res["header"], res["count"])
```

把 `res` 落成 `urls.json`（`json.dump` 到 `$BH_AGENT_WORKSPACE`，本技能脚本按 `{"items": [{idx, imgs}]}` 读取）。

再量一次渲染矩形（拼图比例校对用）：

```python
JS_RECT = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const it = d.querySelectorAll('.problem_item')[0];
  const r = it.getBoundingClientRect();
  return {itemW: Math.round(r.width), itemH: Math.round(r.height),
    rects: [...it.querySelectorAll('.pptimg')].map(e => {
      const b = e.getBoundingClientRect();
      return {label: e.getAttribute('data-label') || 'img',
              w: Math.round(b.width), h: Math.round(b.height),
              x: Math.round(b.left - r.left), y: Math.round(b.top - r.top)};
    })};
})()"""
print(js(JS_RECT))
```

实测参考（360×600 容器）：题干 `288×188 @ (36,42)`；四个选项 `252×56 @ x=72, y=244/319/394/469`；标号 `A–D` 在 `x=34, y=254/329/404/479`。容器尺寸不同就按比例换算，别硬编码。

**完成判据**：`count` 与答题卡总数一致，每题 `imgs` 非空、`bullets` 是 A–D。

### 3. 下载切图

```bash
python3 scripts/fetch_quiz_images.py urls.json ./imgs
```

有 403 就带浏览器 cookie 重下：先用 `print(cdp('Network.getCookies', urls=[<一个切图URL>]))` 取 cookie，存成 JSON，再 `--cookie-json cookies.json`。

**完成判据**：脚本打印 `downloaded N / N`，没有 `FAILED:` 行。

### 4. 拼成可读长图

```bash
python3 scripts/compose_pillow.py ./imgs ./composed --scale 1.6 --per-group 2
```

（Windows 且有 PowerShell 时可用 `scripts/compose_windows.ps1`，免装 Pillow。）

每组 2 题（576×1920）是清晰度与读取次数的平衡点；一组 4 题会糊。拼图在题干左上角画了 `No.N`，用来对题号。

### 5. 识别作答

用 `vision_analyze(image_url=<composed/grp_XX.png>, question="逐题读出题干和选项，给出答案")` 读每一张拼图，按课程常识推理（多为计算机基础、Python 基础），**能算的算到唯一值再对选项**。

- 题干下标与符号分辨率低，先确认是 H、B、D 还是八进制再动笔（例如 `(D)H` = 13）。
- 页面里已有的 `chosen` 历史答案一律视为不可信，要复核；改了哪几题要在汇报里说。
- 两个选项都「像」时，回到该题原始切图再看一遍，别猜。

**完成判据**：得到 `[(题号, 选项), ...]` 完整答案表，题数 = `count`。

### 6. 按节奏点击并逐题校验

每题固定动作：**即时滚动 → 取当前矩形 → 点击 → 读回 `chosen` 校验**，失败重试。模板与节奏算法见 `references/click-pacing.md`，三个要点：

1. `scrollIntoView({block:'center', behavior:'instant'})`，必须显式 `instant`。
2. 点击坐标 = `iframe.getBoundingClientRect()` + 选项矩形中心，直接传给 `click_at_xy(x, y)`（像素，无归一化）。
3. 节奏按「距上一次点击的耗时」补差 `sleep(7 - elapsed)`，别固定 `sleep(7)`，否则实际间隔会拉成 ~9 秒。

一次 `browser_exec` 处理 8 题左右（约 60–70 秒），批量更大就显式调大 `timeout_s`。

**完成判据**：每批输出 `(题号, 期望, ok, 实际选中)` 全为 `ok=True`。

### 7. 收尾核对与交卷

- 全量核对：`items.length` 等于答题卡总数；每题恰有 1 个 `chosen`，并与答案表逐字比对，输出不一致清单（脚本见 `references/page-structure.md`）。
- 答题卡 `(已答/总数)` 已答=总数才算填完。
- `去交卷` 不可逆：**先向用户确认**；用户没回应就保留已填未交并明确告知，绝不擅自提交。

**完成判据**：不一致清单为空；交卷前有用户明确同意。

## Pitfalls

| 现象 | 原因 | 处理 |
|---|---|---|
| 点到相邻题 | 平滑滚动未结束，坐标过期 | 改 `behavior:'instant'`；点击后立刻读 `chosen` 校验并重试 |
| `js()` 读不到题干、`page_info()` 只有 A B C D | 题干在 iframe 内且是图片——这是设计，不是 bug | 用 `js()` 取 `data-background` + `click_at_xy` |
| `js()` 报跨域 / `contentDocument` 为 null | iframe 跨源 | 用 `cdp('Page.getFrameTree')` 找 frameId，`cdp('Page.createIsolatedWorld', frameId=...)` 拿 executionContextId，再 `cdp('Runtime.evaluate', expression=..., contextId=...)` |
| 答题卡数量不涨 | 点在了标号块而不是选项图片上 | 按选项矩形中心取坐标 |
| 下载 403/超时 | CDN 校验 cookie/UA | 脚本已带 UA；再不行加 `--cookie-json` |
| 拼接图模糊、认不出下标 | 一次拼了 4 题被工具侧缩放 | `--per-group 2` |

## Verification

- `downloaded N / N` 且无失败行；`composed` 目录每组一张图。
- 逐题批次输出全 `ok=True`，之后整卡核对的不一致清单为空。
- 答题卡 `(已答/总数)` 数字相等；交卷动作只在用户同意后发生。

## 参考

- `references/page-structure.md`：DOM 字段、取样、整卡核对、交卷入口脚本全文
- `references/click-pacing.md`：点击模板、节奏控制、校验与重试
- `references/other-agents.md`：在 Claude Code / Codex / OpenCode / Gemini CLI 里跑本技能（四个辅助函数的替换与安装路径）
