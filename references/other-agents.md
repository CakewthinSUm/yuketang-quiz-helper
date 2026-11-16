# Running this skill in other agents (Claude Code, Codex, OpenCode, Gemini CLI…)

`SKILL.md` + `references/` + `scripts/` follow the **Agent Skills open standard**, so the
procedure and the DOM knowledge travel. The only thing that does not travel is the four
browser helper functions, which come from Hermes's `browser_exec`. This page covers both.

## Compatibility matrix

| Agent | Reads `SKILL.md`? | Install location | Built-in browser? | Notes |
|---|---|---|---|---|
| **Hermes Agent** | yes, this repo's native format | `~/.hermes/skills/<category>/yuketang-quiz-helper/` | yes (`browser_exec`) | Zero changes. Reference implementation. |
| **Claude Code** | yes — Agent Skills open standard | `~/.claude/skills/yuketang-quiz-helper/` (personal, all projects) or `.claude/skills/` (per project) | no | Frontmatter `name` + `description`; can also use `allowed-tools` to pre-approve tools and `disable-model-invocation: true` for manual-only. Invoke with `/yuketang-quiz-helper`. |
| **Codex CLI / ChatGPT desktop** | yes — same standard | `$HOME/.agents/skills/` (user) or `.agents/skills/` in the repo (scanned from CWD up to repo root) | no | `SKILL.md` must carry `name` + `description`; optional `agents/openai.yaml` (shipped here) sets display name, invocation policy and tool dependencies. Invoke with `/skills` or `$yuketang-quiz-helper`. |
| **OpenCode** | yes | `.opencode/skills/yuketang-quiz-helper/SKILL.md` | no | Directory form keeps `references/` and `scripts/` private to the skill, exactly like this repo lays them out. Loaded through its `skill` tool. |
| **Gemini CLI** | yes | `~/.gemini/skills/` or the `~/.agents/skills/` alias; workspace `.gemini/skills/` or `.agents/skills/` | no | `activate_skill` tool asks for consent per activation; within one tier the `.agents/skills/` alias wins. Heads-up: Gemini CLI was superseded by Antigravity CLI for unpaid/Google One tiers (Jun 2026). |
| **Anything else** (Cursor rules, Aider, plain chat) | no | paste `SKILL.md` into `AGENTS.md` / `CLAUDE.md` / the system prompt | no | Keep the DOM facts and the verification loop; rename the helper calls per the mapping below. |

**One install, two agents:** `~/.agents/skills/` is the user-scope location for both Codex
and Gemini CLI, so a single `git clone` there serves both.

## The only non-portable part: four helper functions

The snippets in `SKILL.md` call exactly four things. Every other line is plain JS or plain
Python and runs unchanged anywhere.

| Hermes `browser_exec` | Playwright (shim / raw API) | Playwright MCP server |
|---|---|---|
| `js(expr)` | `page.evaluate(expr)` | `browser_evaluate` |
| `click_at_xy(x, y)` — viewport CSS px | `page.mouse.click(x, y)` | needs a coordinate-capable click; most MCP servers click element refs — see caveat |
| `page_info()` | `page.url` / `page.title()` / `page.inner_text("body")` | `browser_snapshot` |
| `capture_screenshot()` | `page.screenshot(path=...)` | `browser_take_screenshot` |

### Option A — `scripts/playwright_browser.py` (tested, recommended)

The repo ships a ~150-line shim with the **same helper names**, so `SKILL.md` runs verbatim:

```bash
pip install playwright
playwright install chromium
```

```python
import sys; sys.path.insert(0, "scripts")
from playwright_browser import Browser

with Browser(profile_dir="~/.cache/yuketang-profile") as b:
    b.goto("https://changjiang.yuketang.cn")
    print(b.page_info())              # url / title / text
    print(b.js(JS_STRUCT))            # same expression as in SKILL.md
    b.click_xy(412, 655)              # viewport CSS pixels, same semantics
    b.dump_cookies("cookies.json")    # feeds fetch_quiz_images.py --cookie-json
```

It uses `launch_persistent_context`, so the Yuketang login survives between runs — the same
behaviour as Hermes's own Chromium profile. Verified against a page that reproduces the real
DOM: the unmodified click loop landed `[['C'],['A'],['B']]` and the answer card reached
`(3 / 3)`.

### Option B — a browser MCP server

Playwright MCP (`npx @playwright/mcp@latest`) or Chrome DevTools MCP give Claude Code / Codex
/ OpenCode a browser over MCP. Rough mapping: `browser_evaluate` covers `js()`,
`browser_take_screenshot` covers `capture_screenshot()`, `browser_snapshot` replaces
`page_info()`.

**Caveat that matters here:** these PPT bullets need *coordinate* clicks, and most MCP browser
servers click by element ref, not raw viewport coordinates. Pointing them at
`[data-role=problembullet][data-label="C"]` works only if the element is a real clickable
target in the accessibility tree — on this page the clickable thing is a background-image
div, so element-ref clicking is unreliable. Use option A for anything beyond a smoke test.

## Login stays a human step, everywhere

No agent may type the user's password. In every environment the rule is the same: if the page
shows a login screen, screenshot it, hand the QR code to the human, wait, then re-check with
`page_info()`. The persistent profile keeps the resulting cookie.

## What is identical across all agents

- The DOM map: `.problem_item`, `.pptimg[data-background]`,
  `[data-role=problembullet][data-label]`, `chosen`, `答题卡 (n / total)`, `去交卷`.
- `behavior: 'instant'` before measuring, and reading back `chosen` after every click.
- Pacing measured click-to-click, not per-question sleeps.
- Whole-card verification before offering to submit, and **never** submitting without the
  user's explicit go-ahead.
