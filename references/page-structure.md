# 雨课堂练习页 DOM 结构与取样

> Hermes 版：代码在 `browser_exec` 里跑，`js()` / `click_at_xy()` 已预导入；`click_at_xy` 收视口 CSS 像素。

## 页面拓扑

```
顶层文档
└── iframe                      ← 题目渲染在这里
    └── div#quiz_cont
        ├── header             "剩余答题时间 62:5x"  "答题卡 (n / 总数)"
        └── div#problem_cont
            ├── .problem_item (data-index, data-problemid, style height:600px)   ← 每题一个
            │   ├── .ptype          "单选题   第1题   2分"
            │   ├── .pptimg[data-background]   ← 题干（多带 notBullet）+ 选项切图，绝对定位百分比
            │   └── [data-role=problembullet][data-label=A..D]  ← 可点击的选项标号
            └── ...共 N 个 .problem_item
```

要点：

- 题干和选项都是 `background-image` 的切图，`innerText` 里只有「A B C D」和题号，**没有任何题干文字**。
- 选项的 `.chosen` class 表示当前选中项；历史作答同样带 `chosen`，不可当正确答案。
- 切图文件名形如 `slide_{n}_{k}_20261112130015.png`，同一份练习里时间戳相同、`k` 起点随题变化，必须逐题取 `data-background`。
- 页面整体可滚动，`iframe` 本身高度等于全部题目高度（数十万 px），滚动由外层文档承担。

## 一次取全所有题

```python
JS_STRUCT = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const items = [...d.querySelectorAll('.problem_item')];
  return {
    header: d.body.innerText.slice(0, 40).replace(/\\n/g, ' '),
    items: items.map((it, i) => ({
      idx: i + 1,
      type: it.className.trim(),
      imgs: [...it.querySelectorAll('.pptimg')].map(e => e.getAttribute('data-background')),
      bullets: [...it.querySelectorAll('[data-role=problembullet]')].map(b => ({
        label: b.getAttribute('data-label'),
        chosen: b.className.includes('chosen')
      }))
    }))
  };
})()"""
res = js(JS_STRUCT)
print(res["header"])
print([it["imgs"] for it in res["items"]][:2])
```

把 `res["items"]` 直接 `json.dump` 成 `urls.json` 交给 `scripts/fetch_quiz_images.py`。

## 量渲染矩形（拼图用）

```python
JS_RECT = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const it = d.querySelectorAll('.problem_item')[0];
  const r = it.getBoundingClientRect();
  const rects = [...it.querySelectorAll('.pptimg')].map(e => {
    const b = e.getBoundingClientRect();
    return {label: e.getAttribute('data-label') || 'img',
            w: Math.round(b.width), h: Math.round(b.height),
            x: Math.round(b.left - r.left), y: Math.round(b.top - r.top)};
  });
  return {itemW: Math.round(r.width), itemH: Math.round(r.height), rects: rects};
})()"""
print(js(JS_RECT))
```

360×600 容器的实测值：

| 元素 | 尺寸 | 位置 |
|---|---|---|
| 题干切图 | 288×188 | (36, 42) |
| 选项切图 A/B/C/D | 252×56 | x=72，y=244 / 319 / 394 / 469 |
| 标号 A/B/C/D | ~35×36 | x=34，y=254 / 329 / 404 / 479 |

拼图缩放取 1.6 时（容器 576×960），题干切图 461×301 ≈ 原生 486×300，选项 403×90 ≈ 原生 422×90，正好不失真。

## 核对整张答题卡

```python
JS_CHECK = """(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  const items = [...d.querySelectorAll('.problem_item')];
  return {
    header: d.body.innerText.slice(0, 40).replace(/\\n/g, ' '),
    chosen: items.map(x => [...x.querySelectorAll('[data-role=problembullet].chosen')]
                       .map(b => b.getAttribute('data-label')))
  };
})()"""
res = js(JS_CHECK)
got = [c[0] if len(c) == 1 else 'X' for c in res["chosen"]]
print(res["header"])                       # 期望 答题卡 (总数/总数)
print([(i + 1, got[i], EXPECT[i]) for i in range(len(got)) if got[i] != EXPECT[i]])
```

要求：每题恰好一个 `chosen`（多于一个说明点到了相邻题），不一致清单必须为空才收尾。

## 交卷入口

```python
print(js("""(() => {
  const f = document.querySelector('iframe');
  const d = f.contentDocument || f.contentWindow.document;
  return [...d.querySelectorAll('button, div, span, a')]
    .filter(e => /交卷|提交/.test((e.textContent || '').trim()) && (e.textContent || '').trim().length < 12)
    .map(e => ({tag: e.tagName, cls: e.className, txt: (e.textContent || '').trim()}));
})()"""))
```

`去交卷` 是不可逆动作，必须先取得用户确认再点。
