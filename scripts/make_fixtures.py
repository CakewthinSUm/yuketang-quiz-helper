#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成雨课堂练习页的自测夹具：合成切图 + 复刻 DOM 的本地页。

用法:
    python3 make_fixtures.py ./fixture [--questions 4]
    cd ./fixture && python3 -m http.server 8765 --bind 127.0.0.1   # 必须走 HTTP，file:// 读不到 iframe 文档

然后用浏览器打开 http://127.0.0.1:8765/host.html，把 SKILL.md 的取样/点击模板原样跑一遍。
夹具的正确答案就在图片里（题干 `2+N = ?`，选项 3/4/5/6 里只有一个对），
所以整条「下载 → 拼图 → vision 读题 → 点击 → 校验」可以在没有真试卷、没有账号的情况下验证。
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

LABELS = "ABCD"
OPTION_TOP = [40.625, 53.125, 65.625, 78.125]   # 相对 .problem_item 的百分比，和真页对齐


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size)
    except Exception:  # noqa: BLE001 - 缺字体就退化成位图字体，夹具仍然可用
        return ImageFont.load_default()


def draw_crops(out_dir, questions):
    os.makedirs(out_dir, exist_ok=True)
    for q in range(1, questions + 1):
        stem = Image.new("RGB", (486, 300), (255, 255, 255))
        ImageDraw.Draw(stem).text((12, 12), "Q%d: 2 + %d = ?" % (q, q),
                                  fill=(0, 0, 0), font=font(26, bold=True))
        stem.save(os.path.join(out_dir, "stem%d.png" % q))
        for i, label in enumerate(LABELS):
            opt = Image.new("RGB", (422, 90), (255, 255, 255))
            ImageDraw.Draw(opt).text((8, 28), "%s. %d" % (label, i + 3),
                                     fill=(0, 0, 0), font=font(20))
            opt.save(os.path.join(out_dir, "q%d_%s.png" % (q, label)))


def build_html(questions):
    items = []
    for q in range(1, questions + 1):
        blocks = ('<div class="pptimg notBullet" data-background="img/stem%d.png" '
                  'style="position:absolute;left:10%%;top:6.944%%;width:80%%;height:31.25%%;'
                  'background-size:100%% 100%%"></div>') % q
        for i, label in enumerate(LABELS):
            top = OPTION_TOP[i]
            blocks += ('<div class="pptimg" data-label="%s" data-background="img/q%d_%s.png" '
                       'style="position:absolute;left:20%%;top:%s%%;width:70%%;height:9.375%%;'
                       'background-size:100%% 100%%"></div>'
                       % (label, q, label, top))
            blocks += ('<div data-role="problembullet" data-label="%s" '
                       'style="position:absolute;left:6%%;top:%s%%;width:8%%;height:6%%;'
                       'text-align:center">%s</div>' % (label, top + 1.5, label))
        items.append('<div class="problem_item" data-index="%d" '
                     'style="position:relative;width:360px;height:600px;margin:0 auto">%s</div>'
                     % (q, blocks))

    inner = """<!doctype html><html><meta charset="utf-8"><body style="margin:0">
<div id="quiz_cont">
  <header>剩余答题时间 62:50   答题卡 (0 / %d)</header>
  <div id="problem_cont">%s</div>
  <button id="submit">去交卷</button>
</div>
<script>
// 只有真实点击才会落到这里，JS 改 class 造假不会触发——所以夹具也能验证「是不是真点到了」
document.querySelectorAll('[data-role=problembullet]').forEach(function (b) {
  b.addEventListener('click', function () {
    var item = b.closest('.problem_item');
    item.querySelectorAll('[data-role=problembullet]').forEach(function (x) { x.classList.remove('chosen'); });
    b.classList.add('chosen');
    var n = document.querySelectorAll('.problem_item [data-role=problembullet].chosen').length;
    document.querySelector('header').textContent = '剩余答题时间 62:50   答题卡 (' + n + ' / %d)';
  });
});
</script></body></html>""" % (questions, "".join(items), questions)

    host = ('<!doctype html><html><meta charset="utf-8"><body style="margin:0">'
            '<iframe src="inner.html" style="width:420px;height:900px;border:0"></iframe></body></html>')
    return inner, host


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--questions", type=int, default=4)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    draw_crops(os.path.join(args.out_dir, "img"), args.questions)
    inner, host = build_html(args.questions)
    with open(os.path.join(args.out_dir, "inner.html"), "w", encoding="utf-8") as f:
        f.write(inner)
    with open(os.path.join(args.out_dir, "host.html"), "w", encoding="utf-8") as f:
        f.write(host)
    print("fixtures in %s — serve with: cd %s && python3 -m http.server 8765 --bind 127.0.0.1"
          % (args.out_dir, args.out_dir))
    print("then open http://127.0.0.1:8765/host.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
