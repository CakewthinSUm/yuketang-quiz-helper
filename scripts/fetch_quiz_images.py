#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发下载雨课堂练习页的题目切图。

用法:
    python3 fetch_quiz_images.py urls.json ./imgs [--workers 16] [--cookie-json cookies.json]

urls.json 由 SKILL.md 里的 JS_STRUCT 输出落盘得到，形如:
    {"items": [{"idx": 1, "imgs": ["https://.../slide_2_5_...png", ...]}, ...]}

cookies.json 来自 browser_exec 里的
    cdp('Network.getCookies', urls=[<一个切图URL>])["cookies"]
存的就是 [{"name": ..., "value": ..., "domain": ...}, ...] 原样 JSON。
切图拿 403 时必须带上它。

输出文件命名为 q01_k1.png ... q01_k5.png（k 从 1 开始按列表顺序编号），
与 compose_pillow.py / compose_windows.ps1 的预期一致。
"""
import argparse
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# 部分沙箱环境的 ssl 会读取一个不存在的 keylog 文件，先清掉
os.environ.pop("SSLKEYLOGFILE", None)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def load_cookies(path):
    """返回 (cookie_header, referer)。cookie 文件既可以是 CDP cookies 列表，也可以是 'a=1; b=2' 字符串。"""
    if not path:
        return None, None
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if raw.startswith("[") or raw.startswith("{"):
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("cookies", [])
        header = "; ".join("%s=%s" % (c["name"], c["value"]) for c in data
                           if c.get("name") and c.get("value"))
        domains = [c.get("domain", "") for c in data if c.get("domain")]
        referer = None
        for d in domains:
            d = d.lstrip(".")
            if d:
                referer = "https://%s/" % d
                break
        return header or None, referer
    return raw or None, None


def load_items(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    tasks = []
    for item in data:
        idx = item["idx"]
        for seq, url in enumerate(item["imgs"], start=1):
            tasks.append((idx, seq, url))
    return tasks


def download(task, out_dir, headers, retries=3):
    idx, seq, url = task
    name = "q%02d_k%d.png" % (idx, seq)
    path = os.path.join(out_dir, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return name, os.path.getsize(path), None
    last_err = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                blob = r.read()
            if not blob:
                raise ValueError("empty response")
            with open(path, "wb") as f:
                f.write(blob)
            return name, len(blob), None
        except Exception as e:  # noqa: BLE001 - 需要把失败地址回报给调用方
            last_err = "%s -> %s" % (url, e)
    return name, 0, last_err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls_json")
    ap.add_argument("out_dir")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--cookie-json", default=None,
                    help="CDP Network.getCookies 输出的 JSON（或 'a=1; b=2' 字符串文件）")
    args = ap.parse_args()

    headers = {"User-Agent": UA}
    cookie, referer = load_cookies(args.cookie_json)
    if cookie:
        headers["Cookie"] = cookie
    if referer:
        headers["Referer"] = referer

    os.makedirs(args.out_dir, exist_ok=True)
    tasks = load_items(args.urls_json)
    if not tasks:
        print("no image urls found", file=sys.stderr)
        return 1

    ok, failed = 0, []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for name, size, err in ex.map(lambda t: download(t, args.out_dir, headers), tasks):
            if err:
                failed.append(err)
            else:
                ok += 1
    print("downloaded %d / %d -> %s" % (ok, len(tasks), args.out_dir))
    if failed:
        print("FAILED:")
        for line in failed:
            print("  " + line)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
