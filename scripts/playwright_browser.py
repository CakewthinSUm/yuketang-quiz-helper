#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable browser shim for agents without Hermes's `browser_exec`.

Provides the same four helpers the skill's snippets use — `js()`, `click_xy()`,
`page_info()`, `capture_screenshot()` — on top of Playwright's persistent
context, so the DOM procedure in SKILL.md works unchanged outside Hermes.

Requires:  pip install playwright && playwright install chromium

Usage:
    from playwright_browser import Browser

    with Browser(profile_dir="~/.cache/yuketang-profile") as b:
        b.goto("https://changjiang.yuketang.cn")
        print(b.page_info())
        b.js("document.title")
        b.click_xy(400, 512)
        b.capture_screenshot("shot.png")

The persistent profile keeps the Yuketang login cookie between runs, mirroring
how Hermes's own Chromium profile behaves. The shim never types credentials:
when the login page appears, screenshot the QR code and let the human scan it.
"""
import json
import os
import time

from playwright.sync_api import sync_playwright


class Browser:
    def __init__(self, profile_dir="~/.cache/yuketang-profile", headless=True,
                 viewport=(1280, 900), slow_mo=0, timeout_ms=30000):
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            os.path.expanduser(profile_dir),
            headless=headless,
            viewport={"width": viewport[0], "height": viewport[1]},
            slow_mo=slow_mo,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._ctx.set_default_timeout(timeout_ms)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    # ---- navigation -------------------------------------------------------
    def goto(self, url, wait="load"):
        self.page.goto(url, wait_until=wait)
        return self.page.url

    def wait_load(self, timeout_ms=30000):
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:  # noqa: BLE001 - networkidle is best-effort on busy SPAs
            self.page.wait_for_load_state("load", timeout=timeout_ms)
        return self.page.url

    # ---- the four helpers the skill calls --------------------------------
    def js(self, expression):
        """Evaluate an expression in the main frame and return its value."""
        return self.page.evaluate(expression)

    def click_xy(self, x, y, button="left", clicks=1):
        """Click at viewport CSS pixels — same semantics as Hermes click_at_xy."""
        self.page.mouse.click(x, y, button=button, click_count=clicks)

    def page_info(self):
        try:
            text = self.page.inner_text("body")[:1500]
        except Exception:  # noqa: BLE001
            text = ""
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "text": text,
        }

    def capture_screenshot(self, path="screenshot.png", full_page=False):
        self.page.screenshot(path=path, full_page=full_page)
        return os.path.abspath(path)

    # ---- extras -----------------------------------------------------------
    def scroll_into_view(self, selector, block="center"):
        self.page.eval_on_selector(
            selector,
            "(el, block) => el.scrollIntoView({block, behavior: 'instant'})",
            block,
        )

    def cookies_header(self, urls=None):
        """Serialize cookies into an 'a=1; b=2' header for fetch-based downloads."""
        jar = self._ctx.cookies(urls) if urls else self._ctx.cookies()
        return "; ".join("%s=%s" % (c["name"], c["value"]) for c in jar)

    def dump_cookies(self, path, urls=None):
        """Write cookies as the JSON shape fetch_quiz_images.py --cookie-json expects."""
        jar = self._ctx.cookies(urls) if urls else self._ctx.cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"name": c["name"], "value": c["value"], "domain": c["domain"]}
                       for c in jar], f)
        return path

    def sleep(self, seconds):
        time.sleep(seconds)

    # ---- lifecycle --------------------------------------------------------
    def close(self):
        try:
            self._ctx.close()
        finally:
            self._pw.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Quick smoke test of the portable shim")
    ap.add_argument("url")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--shot", default="screenshot.png")
    a = ap.parse_args()

    with Browser(headless=not a.headed) as b:
        b.goto(a.url)
        info = b.page_info()
        print("url:", info["url"])
        print("title:", info["title"])
        print("text:", info["text"][:200].replace("\n", " "))
        print("shot:", b.capture_screenshot(a.shot))
