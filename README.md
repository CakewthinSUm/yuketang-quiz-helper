# yuketang-quiz-helper

**English** | [简体中文](README.zh-CN.md)

A **Hermes Agent skill** for completing 雨课堂 (Yuketang / `changjiang.yuketang.cn`) online quizzes and practice papers where every question is rendered as a cropped PNG from a lecture deck.

The page has **no question text in the DOM** — the stem and each option are `background-image` crops, and `page_info()` / `get_page_text` only ever returns "A B C D". So "read the page, answer it" does not work. This skill pins down the pipeline that does:

```
read DOM structure  →  download slide crops  →  tile them into readable long images
   →  solve from the images  →  click options on a paced rhythm  →  verify  →  submit
```

## What makes this page hard

The page fights naive automation in a handful of specific ways, and each one has a fix baked into the procedure:

- `click_at_xy(x, y)` takes **viewport CSS pixels** (CDP `Input.dispatchMouseEvent`), not 0–1000 normalized coordinates. Converting to a percentage-based scheme silently misclicks.
- `scrollIntoView` must use `behavior: 'instant'`, otherwise the rect you measured is stale by the time you click and answers land on neighbouring questions.
- Pacing is measured between **clicks**, not "sleep 7 s per question" — the bookkeeping steps eat 1–2 s each, so naive sleeps stretch a 7 s rhythm into ~9 s.
- Slide crop filenames must be read per question from `data-background`; the `k` index start differs between questions (4 or 5), so constructing URLs by hand breaks.
- The crops come from a CDN that answers 403 without the session cookie, so the downloader accepts the raw output of `cdp('Network.getCookies', urls=[...])` via `--cookie-json`.
- Some deployments nest the quiz in a cross-origin `<iframe>`; the skill documents the `Page.getFrameTree` → `createIsolatedWorld` → `Runtime.evaluate(contextId=...)` route for that case.

## Requirements

- Hermes Agent with the `browser_exec` tool (headless Chromium with its own profile).
- Python 3 with Pillow (`pip install pillow`) for `scripts/compose_pillow.py`.
  Windows users can skip Pillow and use `scripts/compose_windows.ps1` (System.Drawing).
- A logged-in Yuketang session in **that** browser profile. The skill never handles credentials: if the login page appears, it screenshots the QR code for the human to scan with the Yuketang app.

Using Claude Code, Codex, OpenCode or Gemini CLI instead? See [Compatibility](#compatibility) — you add `pip install playwright` and the shipped shim, nothing else changes.

## Install

As a Hermes skill (user-local):

```bash
git clone https://github.com/CakewthinSUm/yuketang-quiz-helper.git \
  ~/.hermes/skills/productivity/yuketang-quiz-helper
```

Then just talk to the agent: *"把雨课堂那份练习帮我做了"* / *"finish the Yuketang quiz in the browser"*. The skill triggers on `雨课堂` / `yuketang` / `studentQuiz` / `课件练习`.

Or read `SKILL.md` and its references as a standalone playbook — swap the four helper calls for your own browser and the DOM knowledge still applies.

## Compatibility

`SKILL.md`, `references/` and `scripts/` follow the **Agent Skills open standard**, so the DOM
knowledge and the procedure run in other agents too. Only four browser helper calls are
Hermes-specific (`js`, `click_at_xy`, `page_info`, `capture_screenshot`) — `scripts/playwright_browser.py`
provides them on top of Playwright with identical names, so the snippets work verbatim.

| Agent | Native `SKILL.md`? | Install to | Browser | Extra step |
|---|---|---|---|---|
| **Hermes Agent** | yes (native) | `~/.hermes/skills/<category>/yuketang-quiz-helper/` | built in | none |
| **Claude Code** | yes (Agent Skills standard) | `~/.claude/skills/` or `.claude/skills/` | none | Playwright shim or a browser MCP server |
| **Codex CLI / ChatGPT desktop** | yes (same standard) | `$HOME/.agents/skills/` or repo `.agents/skills/` | none | same; `agents/openai.yaml` is included for UI metadata and invocation policy |
| **OpenCode** | yes | `.opencode/skills/<id>/SKILL.md` | none | same |
| **Gemini CLI** | yes | `~/.gemini/skills/` or `~/.agents/skills/` | none | same |
| **Anything else** | no | paste into `AGENTS.md` / `CLAUDE.md` | none | rename the four helpers |

`~/.agents/skills/` is the user-scope location for both Codex and Gemini CLI — one clone serves both.

```bash
pip install playwright && playwright install chromium
```

```python
from playwright_browser import Browser          # scripts/playwright_browser.py

with Browser(profile_dir="~/.cache/yuketang-profile") as b:
    b.goto("https://changjiang.yuketang.cn")
    b.js(JS_STRUCT); b.click_xy(412, 655); b.dump_cookies("cookies.json")
```

One caveat worth knowing before you reach for an MCP browser instead: these PPT bullets are
background-image divs, and most MCP browser servers click by element ref rather than raw
coordinates — element-ref clicking is unreliable here. Details, per-agent install paths and the
full helper mapping: [`references/other-agents.md`](references/other-agents.md).

## Layout

| Path | What |
|---|---|
| `SKILL.md` | The procedure: sample → download → tile → solve → click → verify → submit |
| `references/page-structure.md` | DOM map, sampling scripts, full answer-sheet verification, submit-button probe |
| `references/click-pacing.md` | Click template, rhythm control, retry/verification loop |
| `references/other-agents.md` | Claude Code / Codex / OpenCode / Gemini CLI install paths and helper mapping |
| `scripts/fetch_quiz_images.py` | Concurrent crop downloader (UA + optional cookies) |
| `scripts/compose_pillow.py` | Tiles crops into 2-question readable images (any platform) |
| `scripts/compose_windows.ps1` | Same, via System.Drawing, no dependencies |
| `scripts/playwright_browser.py` | Portable `js` / `click_xy` / `page_info` / `capture_screenshot` shim for non-Hermes agents |
| `scripts/make_fixtures.py` | Generates a local replica of the quiz page for testing without an account |
| `agents/openai.yaml` | Optional Codex/ChatGPT skill metadata (display name, invocation policy) |

## Verified behaviour

- Crop download and tiling: 20 synthetic crops → `downloaded 20 / 20`, tiled groups keep the `No.N` question markers legible.
- Click loop: against a page reproducing the real DOM (iframe + `.problem_item` + `data-background` + `[data-role=problembullet]`), pixel-coordinate clicks hit the intended option every time, `chosen` read-back matched `[['C'],['A'],['B']]`, and the answer-card counter went to `(3 / 3)`.
- Portability: the same three snippets, unmodified, run through `scripts/playwright_browser.py` (Playwright 1.65, persistent profile) with identical results — so the procedure is not tied to Hermes.

## Self-test without an account

`scripts/make_fixtures.py` generates a local page that reproduces the real DOM (iframe +
`.problem_item` + `.pptimg[data-background]` + `[data-role=problembullet]` + a live answer
card) with synthetic crops whose answers are written into the images. That lets the whole
pipeline run with no login and no real paper:

```bash
python3 scripts/make_fixtures.py ./fixture --questions 4
cd ./fixture && python3 -m http.server 8765 --bind 127.0.0.1   # HTTP, not file:// — iframe docs need it
# then run the SKILL.md snippets against http://127.0.0.1:8765/host.html
```

Verified: 4 questions → sampling returned 5 crops per question, `downloaded 20 / 20`, tiling
produced two readable groups, the answers read off the tiles (A/B/C/D) were clicked at
coordinates that all registered, and the card reached `(4 / 4)`.

## Scope and ethics

Built for your own practice quizzes and courseware drills. **Do not** point it at proctored exams, credit-bearing assessments, or anything where the rules forbid automation — the skill itself stops and asks before submitting precisely because the final click is irreversible. You are responsible for the accounts and courses you use it on.

## License

MIT — see [LICENSE](LICENSE). Maintained by [@CakewthinSUm](https://github.com/CakewthinSUm).
