# 点击、节奏与校验

> Hermes 版：代码跑在 `browser_exec` 里，`js()` / `click_at_xy()` / `page_info()` 已预导入。
> `click_at_xy(x, y)` 收的是**视口 CSS 像素**（CDP `Input.dispatchMouseEvent`），不做归一化。

## 为什么不能"点完就算"

雨课堂练习页每个 `.problem_item` 高 600px，一屏放不下两题，必须逐题滚动。滚动一旦是平滑动画，`getBoundingClientRect()` 量到的坐标在你点击时就已经过期，点击会落到相邻题上——表现为「刚校验成功的答案，几轮之后莫名变成别的选项」。因此固定四步：

1. 即时滚动到目标题；
2. 立刻量取选项矩形，加上 iframe 偏移换算成视口像素；
3. 点击；
4. 读回 `chosen` 校验，不符就重试。

## 单题模板

```python
SCROLL = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const it = d.querySelectorAll('.problem_item')[%d];
  it.scrollIntoView({block: 'center', behavior: 'instant'});
  return {ok: true};
})()"""

COORD = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const it = d.querySelectorAll('.problem_item')[%d];
  const b = it.querySelector('[data-role=problembullet][data-label="%s"]');
  if (!b) return {ok: false};
  const fr = f.getBoundingClientRect();      // iframe 在视口中的位置
  const r = b.getBoundingClientRect();       // 选项在 iframe 内的位置
  return {ok: true,
          x: fr.left + r.left + r.width / 2,
          y: fr.top + r.top + r.height / 2,
          vw: window.innerWidth, vh: window.innerHeight};
})()"""

CHECK = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const it = d.querySelectorAll('.problem_item')[%d];
  return [...it.querySelectorAll('[data-role=problembullet].chosen')]
    .map(b => b.getAttribute('data-label'));
})()"""
```

点击（像素直传）：

```python
js(SCROLL % (q - 1))
time.sleep(0.5)
c = js(COORD % (q - 1, label))
click_at_xy(round(c["x"]), round(c["y"]))
time.sleep(0.4)
assert js(CHECK % (q - 1)) == [label]
```

坐标若落在视口外（`y > vh` 或 `y < 0`），说明滚动没生效：重新 `SCROLL` 再量，别硬点。

## 节奏控制（几秒一道题）

用户说「7 秒一道」指的是**相邻两次点击的间隔**，不是「每题额外等 7 秒」。滚动、量坐标、校验本身消耗 1–2 秒，如果无脑 `sleep(7)`，实际间隔会被拉长到 9 秒以上。

```python
last = None
for q, label in pairs:
    if last is not None:
        gap = interval - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
    ... 滚动、点击 ...
    last = time.time()          # 以点击时刻为基准
```

- 保持间隔：`interval = 7`。
- 一批 8 题约 60–70 秒，落在 `browser_exec` 默认超时内；批量更大时显式调大 `timeout_s`。
- 需要重试时，重试本身也计入节奏基准，避免短时间连点。
- `browser_exec` 的 Python 变量不跨调用保留：答案表每批重新写进代码，或从 `$BH_AGENT_WORKSPACE` 的 JSON 读回。

## 推荐批量结构

```python
PAIRS = [(3, 'C'), (6, 'B')]             # 题号, 期望选项（本批 8 题左右）
out = []
last = None
for q, L in PAIRS:
    if last is not None:
        gap = interval - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
    ok, chosen = False, None
    for attempt in range(3):             # 最多重试 3 次
        js(SCROLL % (q - 1))
        time.sleep(0.5)
        c = js(COORD % (q - 1, L))
        if not c.get("ok"):
            continue
        click_at_xy(round(c["x"]), round(c["y"]))
        last = time.time()
        time.sleep(0.5)
        chosen = js(CHECK % (q - 1))
        if chosen == [L]:
            ok = True
            break
    out.append((q, L, ok, chosen))       # 逐题输出，异常一眼可见
print(out)
```

结束后务必跑 `references/page-structure.md` 里的整卡核对，而不是相信逐题返回值——偏差通常出现在"当时校验通过、后续批次被误点"的题上。

## 常见异常对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 校验通过但最终状态变了 | 后续批次滚动未结束，坐标过期 | 全部改 `behavior:'instant'`，末轮整卡复核并定点修正 |
| `chosen` 有两个标签 | 一题两个选项被点 | 重新点目标选项，另一个会自动取消 |
| 坐标 `ok:false` | 该题没有这个标号（可能多选/填空） | 停下来看该题结构，不要盲点 |
| 点击无反应 | 页面被浮层遮挡（如提示条） | 先 `capture_screenshot()` 看遮挡，必要时点空白处关闭浮层 |
| `js()` 返回 null / 报跨域 | iframe 跨源，拿不到 `contentDocument` | 用 `cdp('Page.getFrameTree')` 取 frameId，`cdp('Page.createIsolatedWorld', frameId=...)` 拿 executionContextId，再 `cdp('Runtime.evaluate', expression=..., contextId=...)` |
