#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把雨课堂题目切图拼成可读长图（非 Windows 平台用这个，Windows 用 compose_windows.ps1）。

用法:
    python3 compose_pillow.py ./imgs ./composed [--scale 1.6] [--per-group 2]

输入文件名约定 q01_k1.png ... q01_k5.png（k1 为题干切图，k2~k5 为 A~D 选项）。
布局比例来自页面实测（见 references/page-structure.md），这里用占位比例而非绝对像素，
所以容器尺寸变化时只需改 --item-w/--item-h。
"""
import argparse
import glob
import os
import re
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    print("need Pillow: pip install pillow", file=sys.stderr)
    raise

# 相对 .problem_item 的比例（x, y, w, h）
STEM = (0.10, 0.06944, 0.80, 0.3125)
OPTS = [(0.20, 0.40625, 0.70, 0.09375),
        (0.20, 0.53125, 0.70, 0.09375),
        (0.20, 0.65625, 0.70, 0.09375),
        (0.20, 0.78125, 0.70, 0.09375)]
BULLETS = [(0.09444, 0.42312), (0.09444, 0.54812),
           (0.09444, 0.67312), (0.09444, 0.79812)]
LABELS = ["A", "B", "C", "D"]


def collect(src):
    files = {}
    for path in glob.glob(os.path.join(src, "q*_k*.png")):
        m = re.search(r"q(\d+)_k(\d+)\.png$", path)
        if not m:
            continue
        q, k = int(m.group(1)), int(m.group(2))
        files.setdefault(q, {})[k] = path
    return dict(sorted(files.items()))


def place(canvas, path, box):
    if not path or not os.path.exists(path):
        return
    try:
        img = Image.open(path).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        print("skip %s: %s" % (path, e), file=sys.stderr)
        return
    x, y, w, h = box
    canvas.alpha_composite(img.resize((max(1, w), max(1, h)), Image.LANCZOS), (x, y))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.6)
    ap.add_argument("--per-group", type=int, default=2)
    ap.add_argument("--item-w", type=float, default=360.0)
    ap.add_argument("--item-h", type=float, default=600.0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    qs = collect(args.src)
    if not qs:
        print("no qNN_kK.png found in %s" % args.src, file=sys.stderr)
        return 1

    iw = int(args.item_w * args.scale)
    ih = int(args.item_h * args.scale)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(14, int(18 * args.scale)))
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()

    nums = list(qs.keys())
    made = 0
    for start in range(0, len(nums), args.per_group):
        group = nums[start:start + args.per_group]
        canvas = Image.new("RGBA", (iw, ih * len(group)), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        for row, q in enumerate(group):
            oy = row * ih
            draw.text((int(6 * args.scale), oy + 4), "No.%d" % q, fill=(0, 0, 0, 255), font=font)
            parts = qs[q]
            place(canvas, parts.get(1),
                  (int(STEM[0] * iw), oy + int(STEM[1] * ih),
                   int(STEM[2] * iw), int(STEM[3] * ih)))
            for j, (ox, oy2, ow, oh) in enumerate(OPTS):
                place(canvas, parts.get(j + 2),
                      (int(ox * iw), oy + int(oy2 * ih), int(ow * iw), int(oh * ih)))
                bx, by = BULLETS[j]
                draw.text((int(bx * iw), oy + int(by * ih)), LABELS[j],
                          fill=(120, 120, 120, 255), font=font)
        out_path = os.path.join(args.out, "grp_%02d.png" % group[0])
        canvas.convert("RGB").save(out_path)
        made += 1
    print("composed %d images -> %s" % (made, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
